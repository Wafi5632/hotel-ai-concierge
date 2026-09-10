"""LangGraph customer-service agent with deterministic fallback responses."""

from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, START, StateGraph

from .data import HotelDataStore
from .llm import build_optional_llm
from .memory import MemoryStore
from .models import AgentState
from .tools import HotelToolset

DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


class HotelAgent:
    def __init__(self, store: HotelDataStore, memory: MemoryStore | None = None, use_llm: bool = True):
        self.store = store
        self.tools = HotelToolset(store)
        self.memory = memory
        self.llm = build_optional_llm() if use_llm else None
        graph = StateGraph(AgentState)
        graph.add_node("understand", self._understand)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("respond", self._respond)
        graph.add_edge(START, "understand")
        graph.add_edge("understand", "retrieve")
        graph.add_edge("retrieve", "respond")
        graph.add_edge("respond", END)
        self.graph = graph.compile()

    def invoke(self, user_message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        state: AgentState = {
            "user_message": user_message.strip(),
            "history": history or [],
            "tool_results": {},
        }
        return self.graph.invoke(state)

    def _understand(self, state: AgentState) -> dict[str, Any]:
        text = state.get("user_message", "").lower()
        complaint_words = ("complaint", "broken", "dirty", "terrible", "refund", "unhappy", "problem", "issue")
        booking_words = ("book", "availability", "available", "room", "stay", "check in", "check-in", "rate")
        if any(word in text for word in complaint_words):
            intent = "complaint"
        elif any(word in text for word in booking_words) and len(DATE_RE.findall(text)) >= 2:
            intent = "availability"
        elif any(word in text for word in booking_words):
            intent = "booking_guidance"
        elif any(word in text for word in ("breakfast", "spa", "transfer", "upgrade", "package", "checkout")):
            intent = "upsell"
        else:
            intent = "faq"
        dates = DATE_RE.findall(text)
        guests_match = re.search(r"(\d+)\s*(?:guest|adult|people)", text)
        room_id = next((room["id"] for room in self.store.room_types if room["id"] in text), None)
        return {
            "intent": intent,
            "entities": {
                "check_in": dates[0] if len(dates) > 0 else None,
                "check_out": dates[1] if len(dates) > 1 else None,
                "guests": int(guests_match.group(1)) if guests_match else 2,
                "room_type": room_id,
            },
        }

    def _retrieve(self, state: AgentState) -> dict[str, Any]:
        intent = state["intent"]
        entities = state.get("entities", {})
        text = state.get("user_message", "")
        if intent == "availability":
            result = self.tools.check_availability(
                entities["check_in"], entities["check_out"], entities["guests"], entities["room_type"]
            )
            if result.get("success") and result["data"]["rooms"]:
                result["upsells"] = self.tools.recommend_package(
                    result["data"]["rooms"][0]["room_type"],
                    result["data"]["nights"],
                    result["data"]["guests"],
                )
            return {"tool_results": {"availability": result}}
        if intent == "upsell":
            room = entities.get("room_type") or self.store.room_types[0]["id"]
            return {"tool_results": {"upsells": self.tools.recommend_package(room, 2, entities.get("guests", 2))}}
        if intent in {"booking_guidance", "complaint"}:
            return {"tool_results": {"faq": self.tools.faq(text)}}
        return {"tool_results": {"faq": self.tools.faq(text)}}

    def _respond(self, state: AgentState) -> dict[str, Any]:
        response = self._deterministic_response(state)
        if self.llm:
            try:
                response = self._llm_response(state, response)
            except Exception:
                # Provider failures never block hotel operations.
                pass
        return {"response": response}

    def _deterministic_response(self, state: AgentState) -> str:
        intent = state["intent"]
        results = state.get("tool_results", {})
        if intent == "availability":
            result = results["availability"]
            if not result.get("success"):
                return f"I couldn't check that stay yet: {result['error']} Try dates shown in the booking panel."
            data = result["data"]
            if not data["rooms"]:
                return f"I’m sorry, we have no rooms for {data['check_in']}–{data['check_out']} for {data['guests']} guests. I can suggest nearby dates or you can contact reservations."
            lines = [f"Great news — I found availability for {data['check_in']}–{data['check_out']} ({data['nights']} nights):"]
            for room in data["rooms"]:
                lines.append(f"• **{room['name']}** · AED {room['rate_per_night']:,.0f}/night · up to {room['max_occupancy']} guests · {room['available_rooms']} left")
            upsells = results.get("availability", {}).get("upsells", {}).get("data", [])
            if upsells:
                lines.append("\nFor this stay, you may also like " + ", ".join(item["name"] for item in upsells) + ".")
            lines.append("\nUse **Book your stay** to confirm a room securely.")
            return "\n".join(lines)
        if intent == "booking_guidance":
            return "I can check rooms and rates when you share arrival and departure dates in YYYY-MM-DD format. You can also use the booking panel to compare rooms and confirm a stay."
        if intent == "complaint":
            return "I’m sorry something went wrong. Please use **Help & feedback** to open a case; our team will receive it with a tracking number. For urgent assistance, call " + self.store.hotel["contact"]["phone"] + "."
        if intent == "upsell":
            data = results.get("upsells", {}).get("data", [])
            if not data:
                return "Our reservations team can tailor extras to your stay. Call " + self.store.hotel["contact"]["phone"] + " for assistance."
            return "To make your stay more comfortable, I recommend:\n" + "\n".join(
                f"• **{item['name']}** — {item['reason']}" for item in data
            ) + "\n\nYou can add these in the booking panel."
        faq = results.get("faq", {})
        if not faq.get("success"):
            return "I’m having trouble accessing hotel information right now. Please call " + self.store.hotel["contact"]["phone"] + "."
        return "\n\n".join(f"**{item['topic'].replace('-', ' ').title()}**: {item['answer']}" for item in faq["data"])

    def _llm_response(self, state: AgentState, fallback: str) -> str:
        prompt = (
            "You are the Al Waha Grand Hotel concierge. Be concise, warm, and factual. "
            "Never invent prices, policies, or availability. Use the verified tool result below. "
            f"Verified response:\n{fallback}\nGuest message: {state['user_message']}"
        )
        result = self.llm.invoke(prompt)
        content = getattr(result, "content", "")
        return content.strip() if isinstance(content, str) and content.strip() else fallback
