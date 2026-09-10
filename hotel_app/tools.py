"""Hotel operations exposed as typed LangChain tools."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .data import HotelDataError, HotelDataStore
from .validators import ValidationError


class AvailabilityArgs(BaseModel):
    check_in: str = Field(description="Arrival date in YYYY-MM-DD format.")
    check_out: str = Field(description="Departure date in YYYY-MM-DD format.")
    guests: int = Field(default=2, ge=1, le=12, description="Number of guests.")
    room_type: str | None = Field(default=None, description="Optional room id to check.")


class QuoteArgs(BaseModel):
    room_type: str = Field(description="Room id from the hotel room catalogue.")
    check_in: str = Field(description="Arrival date in YYYY-MM-DD format.")
    check_out: str = Field(description="Departure date in YYYY-MM-DD format.")
    packages: list[str] = Field(default_factory=list, description="Package ids to include.")


class BookingArgs(AvailabilityArgs):
    guest_name: str = Field(description="Guest's full name.")
    email: str = Field(description="Guest email address.")
    phone: str = Field(description="Guest phone number.")
    packages: list[str] = Field(default_factory=list, description="Package ids to include.")
    room_type: str = Field(description="Room id to book.")


class FAQArgs(BaseModel):
    query: str = Field(description="Question about hotel policies, amenities, or contact details.")


class HotelInfoArgs(BaseModel):
    topic: str | None = Field(default=None, description="Optional topic such as amenities, policies, or contact.")


class UpsellArgs(BaseModel):
    room_type: str = Field(description="Room id being considered.")
    nights: int = Field(ge=1, le=30, description="Number of nights.")
    guests: int = Field(default=2, ge=1, le=12, description="Number of guests.")


class ComplaintArgs(BaseModel):
    guest_name: str = Field(description="Guest's full name.")
    email: str = Field(description="Guest email address.")
    category: str = Field(description="Complaint category.")
    message: str = Field(description="Description of the complaint.")


class HotelToolset:
    """A tool bundle bound to one data store, making testing and deployment simple."""

    def __init__(self, store: HotelDataStore):
        self.store = store

    @staticmethod
    def _error(exc: Exception) -> dict[str, Any]:
        return {"success": False, "error": str(exc), "error_type": type(exc).__name__}

    def check_availability(self, check_in: str, check_out: str, guests: int, room_type: str | None = None) -> dict[str, Any]:
        try:
            return {"success": True, "data": self.store.availability(check_in, check_out, guests, room_type)}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def quote(self, room_type: str, check_in: str, check_out: str, packages: list[str]) -> dict[str, Any]:
        try:
            return {"success": True, "data": self.store.quote(room_type, check_in, check_out, packages)}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def create_booking(
        self, guest_name: str, email: str, phone: str, room_type: str, check_in: str,
        check_out: str, guests: int, packages: list[str]
    ) -> dict[str, Any]:
        try:
            booking = self.store.create_booking(
                guest_name=guest_name, email=email, phone=phone, room_type=room_type,
                check_in=check_in, check_out=check_out, guests=guests, packages=packages,
            )
            return {"success": True, "data": booking}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def get_hotel_info(self, topic: str | None = None) -> dict[str, Any]:
        try:
            hotel = self.store.hotel
            if topic:
                faq = self.store.search_faq(topic)
                return {"success": True, "data": {"hotel": hotel, "topic": topic, "faq": faq}}
            return {"success": True, "data": {"hotel": hotel, "room_types": self.store.room_types, "packages": self.store.packages}}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def faq(self, query: str) -> dict[str, Any]:
        try:
            return {"success": True, "data": self.store.search_faq(query)}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def recommend_package(self, room_type: str, nights: int, guests: int) -> dict[str, Any]:
        try:
            selected = self.store.room(room_type)
            if not selected:
                raise ValidationError("Please select a valid room before viewing add-ons.")
            candidates = []
            for package in self.store.packages:
                # Recommendations are contextual, not hard-coded prices.
                if package["id"] == "breakfast_addon" and guests >= 1:
                    reason = "A convenient buffet breakfast for every morning of your stay."
                elif package["id"] == "airport_transfer":
                    reason = "A smooth arrival in Dubai, especially for late flights."
                elif package["id"] == "spa_package" and nights >= 2:
                    reason = "A relaxing complement to a multi-night stay."
                elif package["id"] == "late_checkout":
                    reason = "More time to enjoy the hotel before a late departure."
                elif package["id"] == "room_upgrade" and selected["id"] != "presidential_suite":
                    reason = "Elevate the room experience, subject to availability."
                else:
                    continue
                candidates.append({"id": package["id"], "name": package["name"], "description": package["description"], "reason": reason})
            return {"success": True, "data": candidates[:3]}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def log_complaint(self, guest_name: str, email: str, category: str, message: str) -> dict[str, Any]:
        try:
            return {"success": True, "data": self.store.create_complaint(
                guest_name=guest_name, email=email, category=category, message=message
            )}
        except (ValidationError, HotelDataError) as exc:
            return self._error(exc)

    def as_langchain_tools(self) -> list[StructuredTool]:
        """Return tools with JSON schemas suitable for LangGraph or an LLM."""
        return [
            StructuredTool.from_function(self.check_availability, name="check_availability", description="Check live room availability and rates.", args_schema=AvailabilityArgs),
            StructuredTool.from_function(self.quote, name="calculate_quote", description="Calculate a room and package quote.", args_schema=QuoteArgs),
            StructuredTool.from_function(self.create_booking, name="create_booking", description="Validate and confirm a hotel booking.", args_schema=BookingArgs),
            StructuredTool.from_function(self.recommend_package, name="recommend_package", description="Recommend relevant packages for a stay.", args_schema=UpsellArgs),
            StructuredTool.from_function(self.log_complaint, name="log_complaint", description="Open a customer-service complaint case.", args_schema=ComplaintArgs),
            StructuredTool.from_function(self.get_hotel_info, name="get_hotel_info", description="Retrieve verified hotel details, policies, rooms, and packages.", args_schema=HotelInfoArgs),
            StructuredTool.from_function(self.faq, name="answer_hotel_faq", description="Answer a hotel policy or amenity question.", args_schema=FAQArgs),
        ]
