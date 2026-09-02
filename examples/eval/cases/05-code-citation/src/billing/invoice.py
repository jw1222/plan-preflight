from decimal import Decimal, ROUND_HALF_EVEN

MAX_DISCOUNT_PERCENT = Decimal("50")


def apply_discount(subtotal: Decimal, percent: Decimal) -> Decimal:
    """Return the subtotal after a percentage discount, rounded to cents.

    Rounding is banker's rounding (ROUND_HALF_EVEN), matching the ledger
    posting code in the finance service.
    """
    if percent < 0 or percent > MAX_DISCOUNT_PERCENT:
        raise ValueError("discount percent out of range")
    discounted = subtotal * (Decimal(1) - percent / Decimal(100))
    return discounted.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
