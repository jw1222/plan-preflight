from dataclasses import dataclass
from datetime import date


@dataclass
class Coupon:
    code: str
    percent: int
    expires_on: date
    uses_left: int
    eligible_plans: tuple[str, ...]


def validate_coupon(coupon: Coupon, plan: str, today: date) -> None:
    """Raise ValueError if the coupon cannot be applied to the given plan."""
    if today > coupon.expires_on:
        raise ValueError("coupon expired")
    if coupon.uses_left <= 0:
        raise ValueError("coupon exhausted")
    if plan not in coupon.eligible_plans:
        raise ValueError("plan not eligible")
