from decimal import Decimal
from typing import Literal


def frequency_analyzer_raw(
    volume_shares: int | None,
    frequency: int | None,
    *,
    unit: Literal["shares", "lots"] = "shares",
) -> Decimal | None:
    """Return the research series Volume / Frequency^3 without display normalization."""
    if volume_shares is None or frequency is None:
        return None
    if volume_shares < 0 or frequency < 0:
        raise ValueError("volume and frequency cannot be negative")
    if frequency == 0:
        return None

    volume = Decimal(volume_shares)
    if unit == "lots":
        volume /= Decimal(100)
    return volume / (Decimal(frequency) ** 3)
