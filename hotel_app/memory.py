"""Persistent, privacy-conscious conversation memory."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, path: str | Path, max_turns: int = 20):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, session_id: str) -> dict[str, Any]:
        return self._read().get(session_id, {"messages": [], "preferences": {}})

    def save_turn(self, session_id: str, role: str, content: str) -> None:
        payload = self._read()
        session = payload.setdefault(session_id, {"messages": [], "preferences": {}})
        session.setdefault("messages", []).append({"role": role, "content": content})
        session["messages"] = session["messages"][-self.max_turns * 2 :]
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def save_preferences(self, session_id: str, preferences: dict[str, Any]) -> None:
        payload = self._read()
        session = payload.setdefault(session_id, {"messages": [], "preferences": {}})
        session["preferences"] = {**session.get("preferences", {}), **preferences}
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex
