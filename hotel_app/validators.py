"""Input validation shared by the UI, data layer, and tools."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

DATE_FORMAT = "%Y-%m-%d"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,25}$")


class ValidationError(ValueError):
    """Raised for a user-correctable validation problem."""


def parse_date(value: str, field_name: str = "date") -> date:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name.replace('_', ' ').title()} is required.")
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).date()
    except ValueError as exc:
        raise ValidationError(
            f"{field_name.replace('_', ' ').title()} must use YYYY-MM-DD format."
        ) from exc


def validate_stay(check_in: str, check_out: str) -> tuple[date, date]:
    arrival = parse_date(check_in, "check_in")
    departure = parse_date(check_out, "check_out")
    if departure <= arrival:
        raise ValidationError("Check-out must be after check-in.")
    if (departure - arrival).days > 30:
        raise ValidationError("Stays longer than 30 nights need a reservations specialist.")
    return arrival, departure


def validate_guests(guests: Any) -> int:
    try:
        parsed = int(guests)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Number of guests must be a whole number.") from exc
    if not 1 <= parsed <= 12:
        raise ValidationError("Number of guests must be between 1 and 12.")
    return parsed


def validate_required_text(value: Any, field_name: str, max_length: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{field_name.replace('_', ' ').title()} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field_name.replace('_', ' ').title()} is too long.")
    return text


def validate_email(value: Any) -> str:
    email = validate_required_text(value, "email", 254).lower()
    if not EMAIL_RE.match(email):
        raise ValidationError("Please enter a valid email address.")
    return email


def validate_phone(value: Any) -> str:
    phone = validate_required_text(value, "phone", 25)
    if not PHONE_RE.match(phone):
        raise ValidationError("Please enter a valid phone number.")
    return phone
