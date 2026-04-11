from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any

CHANNEL_ID_RE = re.compile(r"^channel_\d+$")


@dataclass(slots=True)
class CsvImportResult:
    ok: bool
    errors: list[dict[str, Any]]
    channels: list[dict[str, Any]]
    room_name: str | None = None
    pin: str | None = None
    target_capacity: int | None = None


def parse_room_csv(content: str) -> CsvImportResult:
    reader = csv.DictReader(io.StringIO(content))
    required_headers = {"channel_id", "channel_label", "listen"}
    headers = set(reader.fieldnames or [])
    errors: list[dict[str, Any]] = []
    channels: list[dict[str, Any]] = []
    room_name: str | None = None
    pin: str | None = None
    target_capacity: int | None = None

    missing = sorted(required_headers - headers)
    if missing:
        return CsvImportResult(False, [{"line": 1, "field": "header", "code": "MISSING_HEADER", "message": ",".join(missing)}], [])

    used_channel_ids: set[str] = set()
    for idx, row in enumerate(reader, start=2):
        channel_id = (row.get("channel_id") or "").strip()
        channel_label = (row.get("channel_label") or "").strip()
        listen = (row.get("listen") or "").strip()

        if not CHANNEL_ID_RE.match(channel_id):
            errors.append({"line": idx, "field": "channel_id", "code": "INVALID_CHANNEL_ID", "message": channel_id})
        if channel_id in used_channel_ids:
            errors.append({"line": idx, "field": "channel_id", "code": "DUPLICATE_CHANNEL_ID", "message": channel_id})
        used_channel_ids.add(channel_id)

        if not channel_label:
            errors.append({"line": idx, "field": "channel_label", "code": "EMPTY_CHANNEL_LABEL", "message": "label required"})

        if listen not in {"true", "false"}:
            errors.append({"line": idx, "field": "listen", "code": "INVALID_LISTEN_VALUE", "message": listen})

        row_room_name = row.get("room_name")
        if row_room_name:
            row_room_name = row_room_name.strip()
            if room_name is None:
                room_name = row_room_name
            elif room_name != row_room_name:
                errors.append({"line": idx, "field": "room_name", "code": "INCONSISTENT_ROOM_NAME", "message": row_room_name})

        row_pin = row.get("pin")
        if row_pin:
            row_pin = row_pin.strip()
            if pin is None:
                pin = row_pin
            elif pin != row_pin:
                errors.append({"line": idx, "field": "pin", "code": "INCONSISTENT_PIN", "message": row_pin})

        row_capacity = row.get("target_capacity")
        if row_capacity:
            try:
                row_capacity_int = int(row_capacity)
                if row_capacity_int <= 0:
                    raise ValueError
                if target_capacity is None:
                    target_capacity = row_capacity_int
                elif target_capacity != row_capacity_int:
                    errors.append({"line": idx, "field": "target_capacity", "code": "INVALID_TARGET_CAPACITY", "message": row_capacity})
            except ValueError:
                errors.append({"line": idx, "field": "target_capacity", "code": "INVALID_TARGET_CAPACITY", "message": row_capacity})

        channels.append({"channel_id": channel_id, "channel_label": channel_label, "listen": listen == "true"})

    if target_capacity is None:
        errors.append({"line": 1, "field": "target_capacity", "code": "MISSING_TARGET_CAPACITY", "message": "required"})

    return CsvImportResult(not errors, errors, channels, room_name, pin, target_capacity)
