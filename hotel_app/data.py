"""Durable data access for the unchanged hotel_data.json schema.

The JSON file is the source of truth for hotel inventory, room descriptions,
policies, packages, and bookings. Auxiliary customer-service records live in
separate files so the supplied schema is never extended.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import Booking, Complaint
from .validators import (
    ValidationError,
    validate_email,
    validate_guests,
    validate_phone,
    validate_required_text,
    validate_stay,
)


class HotelDataError(RuntimeError):
    """Raised when the hotel source data cannot be read or persisted."""


class HotelDataStore:
    """Read and safely update hotel data while preserving its exact top-level schema."""

    REQUIRED_KEYS = {"hotel", "room_types", "availability", "packages", "bookings"}

    def __init__(self, data_path: str | Path, support_dir: str | Path | None = None):
        self.data_path = Path(data_path)
        self.support_dir = Path(support_dir) if support_dir else self.data_path.parent / "data"
        self.support_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._data: dict[str, Any] | None = None

    def load(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._data is not None and not refresh:
                return self._data
            try:
                payload = json.loads(self.data_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise HotelDataError(f"Hotel data file not found: {self.data_path}") from exc
            except json.JSONDecodeError as exc:
                raise HotelDataError(f"Hotel data file is invalid JSON: {exc}") from exc
            if not isinstance(payload, dict) or set(payload) != self.REQUIRED_KEYS:
                raise HotelDataError(
                    "hotel_data.json schema changed: expected exactly "
                    f"{sorted(self.REQUIRED_KEYS)}."
                )
            if not isinstance(payload["bookings"], list):
                raise HotelDataError("hotel_data.json bookings must be a list.")
            self._data = payload
            return payload

    @property
    def hotel(self) -> dict[str, Any]:
        return self.load()["hotel"]

    @property
    def room_types(self) -> list[dict[str, Any]]:
        return self.load()["room_types"]

    @property
    def packages(self) -> list[dict[str, Any]]:
        return self.load()["packages"]

    def room(self, room_type: str) -> dict[str, Any] | None:
        return next((r for r in self.room_types if r["id"] == room_type), None)

    def package(self, package_id: str) -> dict[str, Any] | None:
        return next((p for p in self.packages if p["id"] == package_id), None)

    def _nights(self, check_in: str, check_out: str) -> list[str]:
        arrival, departure = validate_stay(check_in, check_out)
        return [
            (arrival + timedelta(days=offset)).isoformat()
            for offset in range((departure - arrival).days)
        ]

    def _booked_count(self, room_type: str, night: str) -> int:
        count = 0
        for booking in self.load().get("bookings", []):
            if booking.get("status", "confirmed") != "confirmed":
                continue
            if booking.get("room_type") != room_type:
                continue
            try:
                booked_nights = self._nights(booking["check_in"], booking["check_out"])
            except (KeyError, ValidationError):
                continue
            if night in booked_nights:
                count += 1
        return count

    def availability(
        self, check_in: str, check_out: str, guests: int, room_type: str | None = None
    ) -> dict[str, Any]:
        nights = self._nights(check_in, check_out)
        guest_count = validate_guests(guests)
        candidates = self.room_types
        if room_type:
            selected = self.room(room_type)
            if not selected:
                raise ValidationError("That room type is not available at this hotel.")
            candidates = [selected]
        results: list[dict[str, Any]] = []
        source_availability = self.load()["availability"]
        for room in candidates:
            if guest_count > int(room["max_occupancy"]):
                continue
            by_night = source_availability.get(room["id"], {})
            remaining = {
                night: max(0, int(by_night.get(night, 0)) - self._booked_count(room["id"], night))
                for night in nights
            }
            if remaining and min(remaining.values()) > 0:
                results.append(
                    {
                        "room_type": room["id"],
                        "name": room["name"],
                        "description": room["description"],
                        "bed_type": room["bed_type"],
                        "size_sqm": room["size_sqm"],
                        "max_occupancy": room["max_occupancy"],
                        "rate_per_night": room["base_rate_per_night"],
                        "currency": room["currency"],
                        "available_rooms": min(remaining.values()),
                        "nights": len(nights),
                    }
                )
        return {
            "check_in": check_in,
            "check_out": check_out,
            "guests": guest_count,
            "nights": len(nights),
            "rooms": results,
            "available": bool(results),
        }

    def quote(self, room_type: str, check_in: str, check_out: str, packages: list[str] | None = None) -> dict[str, Any]:
        room = self.room(room_type)
        if not room:
            raise ValidationError("Please select a valid room type.")
        nights = len(self._nights(check_in, check_out))
        selected_packages = packages or []
        package_total = 0.0
        package_lines = []
        for package_id in selected_packages:
            package = self.package(package_id)
            if not package:
                raise ValidationError(f"Unknown package: {package_id}.")
            unit_price = float(package.get("price_per_night", package.get("price", 0)))
            quantity = nights if package.get("applies_to") in {"per_night", "per_room"} else 1
            line_total = unit_price * quantity
            package_total += line_total
            package_lines.append(
                {
                    "id": package_id,
                    "name": package["name"],
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "total": line_total,
                }
            )
        room_total = float(room["base_rate_per_night"]) * nights
        return {
            "room_type": room_type,
            "room_name": room["name"],
            "nights": nights,
            "room_total": room_total,
            "package_total": package_total,
            "total": room_total + package_total,
            "currency": room["currency"],
            "package_lines": package_lines,
        }

    def create_booking(
        self,
        *,
        guest_name: str,
        email: str,
        phone: str,
        room_type: str,
        check_in: str,
        check_out: str,
        guests: int,
        packages: list[str] | None = None,
    ) -> Booking:
        name = validate_required_text(guest_name, "guest_name")
        validated_email = validate_email(email)
        validated_phone = validate_phone(phone)
        guest_count = validate_guests(guests)
        with self._lock:
            availability = self.availability(check_in, check_out, guest_count, room_type)
            if not availability["available"]:
                raise ValidationError("That room is no longer available for all requested nights.")
            quote = self.quote(room_type, check_in, check_out, packages)
            booking: Booking = {
                "booking_id": f"AWG-{uuid.uuid4().hex[:8].upper()}",
                "guest_name": name,
                "email": validated_email,
                "phone": validated_phone,
                "room_type": room_type,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guest_count,
                "packages": list(packages or []),
                "total_amount": quote["total"],
                "currency": quote["currency"],
                "status": "confirmed",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            data = self.load()
            data["bookings"].append(booking)
            self._persist()
            return booking

    def _persist(self) -> None:
        if self._data is None:
            raise HotelDataError("Cannot persist before loading hotel data.")
        try:
            self.data_path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise HotelDataError(f"Could not save booking: {exc}") from exc

    def create_complaint(
        self, *, guest_name: str, email: str, category: str, message: str
    ) -> Complaint:
        complaint: Complaint = {
            "case_id": f"AWG-CS-{uuid.uuid4().hex[:8].upper()}",
            "guest_name": validate_required_text(guest_name, "guest_name"),
            "email": validate_email(email),
            "category": validate_required_text(category, "category", 60),
            "message": validate_required_text(message, "message", 2000),
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self.support_dir / "complaints.json"
        with self._lock:
            try:
                existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
                if not isinstance(existing, list):
                    existing = []
                existing.append(complaint)
                path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
            except (OSError, json.JSONDecodeError) as exc:
                raise HotelDataError(f"Could not save support case: {exc}") from exc
        return complaint

    def search_faq(self, query: str) -> list[dict[str, str]]:
        text = (query or "").lower()
        hotel = self.hotel
        entries = [
            ("check-in", f"Check-in is from {hotel['check_in_time']}; check-out is by {hotel['check_out_time']}."),
            ("cancellation", hotel["policies"]["cancellation"]),
            ("children", hotel["policies"]["children"]),
            ("pets", hotel["policies"]["pets"]),
            ("smoking", hotel["policies"]["smoking"]),
            ("amenities", "Our amenities include " + ", ".join(hotel["amenities"]) + "."),
            ("contact", f"Reservations: {hotel['contact']['phone']} · {hotel['contact']['email']}"),
        ]
        words = set(text.split())
        ranked = sorted(
            (
                {"topic": topic, "answer": answer, "score": sum(1 for word in words if word in topic or word in answer.lower())}
                for topic, answer in entries
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        return [item for item in ranked if item["score"] > 0][:3] or [
            {"topic": "contact", "answer": entries[-1][1], "score": 0}
        ]
