import base64
import binascii
import json
from datetime import UTC, datetime


class InvalidTradeCursor(ValueError):
    pass


def encode_trade_cursor(executed_at: datetime, row_id: int) -> str:
    if executed_at.tzinfo is None or row_id <= 0:
        raise ValueError("trade cursor requires an aware timestamp and positive id")
    payload = json.dumps(
        {
            "v": 1,
            "executed_at": executed_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "id": row_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_trade_cursor(value: str) -> tuple[datetime, int]:
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding)
        payload = json.loads(decoded)
        if not isinstance(payload, dict) or set(payload) != {"v", "executed_at", "id"}:
            raise ValueError
        if payload["v"] != 1 or not isinstance(payload["id"], int) or payload["id"] <= 0:
            raise ValueError
        if not isinstance(payload["executed_at"], str):
            raise ValueError
        executed_at = datetime.fromisoformat(payload["executed_at"].replace("Z", "+00:00"))
        if executed_at.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError) as error:
        raise InvalidTradeCursor("invalid or incompatible trade cursor") from error
    return executed_at.astimezone(UTC), payload["id"]
