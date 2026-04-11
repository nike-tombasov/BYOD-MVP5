from __future__ import annotations

import time
import uuid
from typing import Any

SCHEMA_VERSION = 1

ERROR_INVALID_PIN = "INVALID_PIN"
ERROR_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_SCHEMA_VALIDATION = "SCHEMA_VALIDATION_ERROR"
ERROR_OWNER_MISMATCH = "ON_AIR_REJECTED_OWNER_MISMATCH"
ERROR_CHANNEL_NOT_FOUND = "CHANNEL_NOT_FOUND"
ERROR_RATE_LIMITED = "RATE_LIMITED"
ERROR_INTERNAL = "INTERNAL_ERROR"


class ProtocolValidationError(ValueError):
    pass


def make_envelope(message_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return {
        "type": message_type,
        "schema_version": SCHEMA_VERSION,
        "ts": int(time.time()),
        "request_id": request_id or str(uuid.uuid4()),
        "payload": payload,
    }


def parse_client_message(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolValidationError("message must be object")

    for required in ("type", "schema_version", "ts", "request_id", "payload"):
        if required not in raw:
            raise ProtocolValidationError(f"missing field: {required}")

    if raw["schema_version"] != SCHEMA_VERSION:
        raise ProtocolValidationError("unsupported schema_version")

    if not isinstance(raw["payload"], dict):
        raise ProtocolValidationError("payload must be object")

    return raw


def validate_connecting_payload(payload: dict[str, Any], expected_role: str) -> None:
    role = payload.get("client_role")
    if role != expected_role:
        raise ProtocolValidationError("invalid client_role")

    if expected_role == "publisher":
        if not isinstance(payload.get("pin"), str):
            raise ProtocolValidationError("pin required")
        if not isinstance(payload.get("hostname"), str):
            raise ProtocolValidationError("hostname required")
