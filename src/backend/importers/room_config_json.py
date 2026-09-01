from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.domain.models import ChannelConfig, I18NLibrary, ImportValidationError, RoomConfig

SUBSITE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.ASCII)
RESERVED_SUBSITE_NAMES = {
    "admin", "health", "ws", "listener.js", "vendor", "index.html", "favicon.ico",
}


@dataclass
class ImportParseResult:
    config: RoomConfig | None
    errors: list[ImportValidationError]


def _err(line: int, field: str, code: str, message: str) -> ImportValidationError:
    return ImportValidationError(line=line, field=field, code=code, message=message)


def parse_room_config_json_bytes(content: bytes) -> ImportParseResult:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ImportParseResult(None, [_err(1, "file", "INVALID_ENCODING", "JSON file must be UTF-8")])

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ImportParseResult(None, [_err(1, "file", "INVALID_JSON", "Invalid JSON")])

    if not isinstance(payload, dict):
        return ImportParseResult(None, [_err(1, "file", "INVALID_JSON", "Root JSON must be object")])

    errors = validate_import_payload(payload)
    if errors:
        return ImportParseResult(None, errors)

    i18n_library = I18NLibrary(
        room_name_i18n={str(k): str(v) for k, v in payload["i18n_library"]["room_name_i18n"].items()},
        custom_status_text_blocked_i18n={
            str(k): str(v) for k, v in payload["i18n_library"]["custom_status_text_blocked_i18n"].items()
        },
        custom_status_text_closed_i18n={
            str(k): str(v) for k, v in payload["i18n_library"]["custom_status_text_closed_i18n"].items()
        },
    )

    channels = [
        ChannelConfig(
            channel_id=str(channel["channel_id"]).strip(),
            channel_label=str(channel["channel_label"]).strip(),
            listen=bool(channel["listen"]),
        )
        for channel in payload["channels"]
    ]

    return ImportParseResult(
        config=RoomConfig(
            pin=str(payload["pin"]).strip(),
            target_capacity=int(payload["target_capacity"]),
            channels=channels,
            i18n_library=i18n_library,
            subsite_name=(str(payload.get("subsite_name") or "").strip() or None),
        ),
        errors=[],
    )


def validate_import_payload(payload: dict[str, Any]) -> list[ImportValidationError]:
    errors: list[ImportValidationError] = []
    required_fields = {"pin", "target_capacity", "channels", "i18n_library"}
    missing_fields = required_fields - set(payload.keys())
    for field in sorted(missing_fields):
        errors.append(_err(1, field, "MISSING_FIELD", f"{field} is required"))

    subsite_name = payload.get("subsite_name")
    if subsite_name is not None and not isinstance(subsite_name, str):
        errors.append(_err(1, "subsite_name", "INVALID_SUBSITE_NAME", "subsite_name must be a string or null"))
    elif isinstance(subsite_name, str) and subsite_name.strip():
        normalized = subsite_name.strip()
        if not SUBSITE_NAME_RE.fullmatch(normalized):
            errors.append(_err(1, "subsite_name", "INVALID_SUBSITE_NAME", "subsite_name must match ^[a-z0-9][a-z0-9_-]{0,63}$"))
        elif normalized in RESERVED_SUBSITE_NAMES:
            errors.append(_err(1, "subsite_name", "RESERVED_SUBSITE_NAME", f"subsite_name {normalized!r} is reserved"))

    pin = payload.get("pin")
    if not isinstance(pin, str) or not pin.strip():
        errors.append(_err(1, "pin", "INVALID_PIN", "pin must be non-empty string"))

    target_capacity = payload.get("target_capacity")
    if not isinstance(target_capacity, int) or target_capacity <= 0:
        errors.append(
            _err(1, "target_capacity", "INVALID_TARGET_CAPACITY", "target_capacity must be positive integer")
        )

    channels = payload.get("channels")
    if not isinstance(channels, list) or not channels:
        errors.append(_err(1, "channels", "INVALID_CHANNELS", "channels must be non-empty list"))
    else:
        seen_ids: set[str] = set()
        for idx, channel in enumerate(channels, start=1):
            if not isinstance(channel, dict):
                errors.append(_err(idx, "channels", "INVALID_CHANNEL", "channel item must be object"))
                continue

            channel_id = channel.get("channel_id")
            channel_label = channel.get("channel_label")
            listen = channel.get("listen")

            if not isinstance(channel_id, str) or not channel_id.startswith("channel_") or not channel_id.replace(
                "channel_", "", 1
            ).isdigit():
                errors.append(
                    _err(idx, "channel_id", "INVALID_CHANNEL_ID", "channel_id must match channel_<number>")
                )
            elif channel_id in seen_ids:
                errors.append(_err(idx, "channel_id", "DUPLICATE_CHANNEL_ID", f"{channel_id} already used"))
            else:
                seen_ids.add(channel_id)

            if not isinstance(channel_label, str) or len(channel_label.strip()) == 0:
                errors.append(
                    _err(idx, "channel_label", "EMPTY_CHANNEL_LABEL", "channel_label must be non-empty string")
                )
            if not isinstance(listen, bool):
                errors.append(_err(idx, "listen", "INVALID_LISTEN_VALUE", "listen must be boolean"))

    i18n_library = payload.get("i18n_library")
    required_i18n_maps = {
        "room_name_i18n",
        "custom_status_text_blocked_i18n",
        "custom_status_text_closed_i18n",
    }
    if not isinstance(i18n_library, dict):
        errors.append(_err(1, "i18n_library", "INVALID_I18N_LIBRARY", "i18n_library must be object"))
    else:
        for map_name in required_i18n_maps:
            lang_map = i18n_library.get(map_name)
            if not isinstance(lang_map, dict):
                errors.append(_err(1, map_name, "INVALID_I18N_MAP", f"{map_name} must be object"))
                continue
            for required_lang in ("en", "ru"):
                value = lang_map.get(required_lang)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        _err(
                            1,
                            f"{map_name}.{required_lang}",
                            "MISSING_REQUIRED_LANG",
                            f"{map_name} must include non-empty {required_lang}",
                        )
                    )
            for lang_tag, text in lang_map.items():
                if not isinstance(lang_tag, str) or not lang_tag.strip():
                    errors.append(
                        _err(1, map_name, "INVALID_LANGUAGE_TAG", "language tag must be non-empty string")
                    )
                if not isinstance(text, str) or not text.strip():
                    errors.append(
                        _err(1, f"{map_name}.{lang_tag}", "INVALID_I18N_TEXT", "i18n text must be non-empty string")
                    )

    return errors
