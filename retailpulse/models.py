"""Strict parsing and normalization for incoming CSV transactions."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Mapping


REQUIRED_COLUMNS = (
    "transaction_id", "order_id", "customer_id", "ordered_at", "country",
    "category", "quantity", "unit_price_usd", "status",
)
VALID_STATUSES = frozenset({"PAID", "REFUNDED", "CANCELLED"})
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """The input row cannot safely be loaded."""


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    order_id: str
    customer_id: str
    ordered_at: str
    country: str
    category: str
    quantity: int
    unit_price_cents: int
    status: str


def _identifier(raw: Mapping[str, str | None], key: str) -> str:
    """Keeps incoming IDs in one safe format before writing them to SQLite."""
    value = (raw.get(key) or "").strip()
    if not IDENTIFIER.fullmatch(value):
        raise ValidationError(f"{key}: expected 2-64 alphanumeric characters, _ or -")
    return value


def parse_transaction(raw: Mapping[str, str | None]) -> Transaction:
    """Normalizes a CSV row and rejects values that could distort the reports."""
    transaction_id = _identifier(raw, "transaction_id")
    order_id = _identifier(raw, "order_id")
    customer_id = _identifier(raw, "customer_id")

    raw_date = (raw.get("ordered_at") or "").strip()
    if not ISO_DATE.fullmatch(raw_date):
        raise ValidationError("ordered_at: expected YYYY-MM-DD")
    try:
        ordered_at = date.fromisoformat(raw_date).isoformat()
    except ValueError as exc:
        raise ValidationError("ordered_at: invalid calendar date") from exc

    country = (raw.get("country") or "").strip().upper()
    if not COUNTRY_CODE.fullmatch(country):
        raise ValidationError("country: expected a two-letter code")

    category = (raw.get("category") or "").strip().title()
    if not (2 <= len(category) <= 60):
        raise ValidationError("category: expected 2-60 characters")

    raw_quantity = (raw.get("quantity") or "").strip()
    if not re.fullmatch(r"\d+", raw_quantity):
        raise ValidationError("quantity: expected a positive whole number")
    quantity = int(raw_quantity)
    if not 1 <= quantity <= 1000:
        raise ValidationError("quantity: expected 1-1000")

    raw_price = (raw.get("unit_price_usd") or "").strip()
    try:
        price = Decimal(raw_price)
    except InvalidOperation as exc:
        raise ValidationError("unit_price_usd: invalid decimal amount") from exc
    if not price.is_finite():
        raise ValidationError("unit_price_usd: expected a finite decimal amount")
    cents = price * 100
    if cents != cents.to_integral_value() or not 1 <= cents <= 10_000_000:
        raise ValidationError("unit_price_usd: expected a positive USD price with at most two decimals")

    status = (raw.get("status") or "").strip().upper()
    if status not in VALID_STATUSES:
        raise ValidationError("status: expected PAID, REFUNDED or CANCELLED")

    return Transaction(
        transaction_id=transaction_id, order_id=order_id, customer_id=customer_id,
        ordered_at=ordered_at, country=country, category=category,
        quantity=quantity, unit_price_cents=int(cents), status=status,
    )
