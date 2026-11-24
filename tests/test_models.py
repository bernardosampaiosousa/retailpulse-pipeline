"""Input normalization and rejection rules."""

import pytest

from retailpulse.models import ValidationError, parse_transaction


VALID = {
    "transaction_id": "TX-001",
    "order_id": "ORD-001",
    "customer_id": "CUST-001",
    "ordered_at": "2026-09-08",
    "country": "br",
    "category": "  home GOODS ",
    "quantity": "2",
    "unit_price_usd": "12.30",
    "status": " paid ",
}


def test_parses_valid_sale_without_float_money():
    parsed = parse_transaction(VALID)
    assert parsed.unit_price_cents == 1230
    assert parsed.quantity == 2
    assert parsed.country == "BR"
    assert parsed.category == "Home Goods"
    assert parsed.status == "PAID"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("transaction_id", ""),
        ("ordered_at", "2026-02-30"),
        ("ordered_at", "20260908"),
        ("country", "BRA"),
        ("quantity", "0"),
        ("quantity", "1.5"),
        ("unit_price_usd", "12.345"),
        ("unit_price_usd", "-10"),
        ("unit_price_usd", "NaN"),
        ("unit_price_usd", "sNaN"),
        ("unit_price_usd", "0"),
        ("status", "PENDING"),
    ],
)
def test_invalid_input_is_rejected(field, value):
    with pytest.raises(ValidationError):
        parse_transaction({**VALID, field: value})


def test_usd_amount_with_trailing_zeroes_is_exact():
    parsed = parse_transaction({**VALID, "unit_price_usd": "1.200"})
    assert parsed.unit_price_cents == 120
