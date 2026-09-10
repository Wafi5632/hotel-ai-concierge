"""Typed application models and validation schemas."""

from __future__ import annotations

from typing import Any, TypedDict


class Booking(TypedDict, total=False):
    booking_id: str
    guest_name: str
    email: str
    phone: str
    room_type: str
    check_in: str
    check_out: str
    guests: int
    packages: list[str]
    total_amount: float
    currency: str
    status: str
    created_at: str


class Complaint(TypedDict, total=False):
    case_id: str
    guest_name: str
    email: str
    category: str
    message: str
    status: str
    created_at: str


class AgentState(TypedDict, total=False):
    user_message: str
    history: list[dict[str, str]]
    intent: str
    entities: dict[str, Any]
    tool_results: dict[str, Any]
    response: str
