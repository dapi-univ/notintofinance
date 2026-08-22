from decimal import Decimal

import pytest

from app.analytics.frequency_analyzer import frequency_analyzer_raw


def test_frequency_analyzer_examples() -> None:
    assert frequency_analyzer_raw(3000, 2) == Decimal("375")
    assert frequency_analyzer_raw(3000, 10) == Decimal("3")


def test_frequency_analyzer_handles_zero_and_lots() -> None:
    assert frequency_analyzer_raw(3000, 0) is None
    assert frequency_analyzer_raw(3000, 10, unit="lots") == Decimal("0.03")


def test_frequency_analyzer_rejects_impossible_values() -> None:
    with pytest.raises(ValueError):
        frequency_analyzer_raw(-1, 3)
