from typing import Any


def make_envelope(msg_type: str, payload: dict[str, Any], schema_version: int, ts: int, request_id: str) -> dict[str, Any]:
    return {
        "type": msg_type,
        "schema_version": schema_version,
        "ts": ts,
        "request_id": request_id,
        "payload": payload,
    }


def get_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload")
    if isinstance(payload, dict):
        return payload
    return message


def validate_message_envelope(message: dict[str, Any], schema_version: int) -> str | None:
    if "payload" not in message:
        return None
    if not isinstance(message.get("type"), str):
        return "INVALID_TYPE"
    if message.get("schema_version") != schema_version:
        return "UNSUPPORTED_SCHEMA_VERSION"
    if not isinstance(message.get("request_id"), str):
        return "INVALID_REQUEST_ID"
    if not isinstance(message.get("payload"), dict):
        return "INVALID_PAYLOAD"
    return None
