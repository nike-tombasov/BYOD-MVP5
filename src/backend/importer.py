from dataclasses import asdict
from typing import Any

from src.backend.domain import ChannelConfig, I18nLibraryConfig, RoomImportConfig


class ImportValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Import payload validation failed")
        self.errors = errors


def validate_import_json_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    required_fields = {"pin", "target_capacity", "channels", "i18n_library"}
    missing_fields = required_fields - set(payload.keys())
    for field in sorted(missing_fields):
        errors.append({"line": 1, "field": field, "code": "MISSING_FIELD", "message": f"{field} is required"})

    pin = payload.get("pin")
    if not isinstance(pin, str) or not pin.strip():
        errors.append({"line": 1, "field": "pin", "code": "INVALID_PIN", "message": "pin must be non-empty string"})

    target_capacity = payload.get("target_capacity")
    if not isinstance(target_capacity, int) or target_capacity <= 0:
        errors.append({"line": 1, "field": "target_capacity", "code": "INVALID_TARGET_CAPACITY", "message": "target_capacity must be positive integer"})

    channels = payload.get("channels")
    if not isinstance(channels, list) or not channels:
        errors.append({"line": 1, "field": "channels", "code": "INVALID_CHANNELS", "message": "channels must be non-empty list"})
    else:
        seen_ids: set[str] = set()
        for idx, channel in enumerate(channels, start=1):
            if not isinstance(channel, dict):
                errors.append({"line": idx, "field": "channels", "code": "INVALID_CHANNEL", "message": "channel item must be object"})
                continue
            channel_id = channel.get("channel_id")
            channel_label = channel.get("channel_label")
            listen = channel.get("listen")
            if not isinstance(channel_id, str) or not channel_id.startswith("channel_") or not channel_id.replace("channel_", "", 1).isdigit():
                errors.append({"line": idx, "field": "channel_id", "code": "INVALID_CHANNEL_ID", "message": "channel_id must match channel_<number>"})
            elif channel_id in seen_ids:
                errors.append({"line": idx, "field": "channel_id", "code": "DUPLICATE_CHANNEL_ID", "message": f"{channel_id} already used"})
            else:
                seen_ids.add(channel_id)
            if not isinstance(channel_label, str) or len(channel_label.strip()) == 0:
                errors.append({"line": idx, "field": "channel_label", "code": "EMPTY_CHANNEL_LABEL", "message": "channel_label must be non-empty string"})
            if not isinstance(listen, bool):
                errors.append({"line": idx, "field": "listen", "code": "INVALID_LISTEN_VALUE", "message": "listen must be boolean"})

    i18n_library = payload.get("i18n_library")
    required_i18n_maps = {
        "room_name_i18n",
        "custom_status_text_blocked_i18n",
        "custom_status_text_closed_i18n",
    }
    if not isinstance(i18n_library, dict):
        errors.append({"line": 1, "field": "i18n_library", "code": "INVALID_I18N_LIBRARY", "message": "i18n_library must be object"})
    else:
        for map_name in required_i18n_maps:
            lang_map = i18n_library.get(map_name)
            if not isinstance(lang_map, dict):
                errors.append({"line": 1, "field": map_name, "code": "INVALID_I18N_MAP", "message": f"{map_name} must be object"})
                continue
            for required_lang in ("en", "ru"):
                value = lang_map.get(required_lang)
                if not isinstance(value, str) or not value.strip():
                    errors.append({"line": 1, "field": f"{map_name}.{required_lang}", "code": "MISSING_REQUIRED_LANG", "message": f"{map_name} must include non-empty {required_lang}"})
            for lang_tag, text in lang_map.items():
                if not isinstance(lang_tag, str) or not lang_tag.strip():
                    errors.append({"line": 1, "field": map_name, "code": "INVALID_LANGUAGE_TAG", "message": "language tag must be non-empty string"})
                if not isinstance(text, str) or not text.strip():
                    errors.append({"line": 1, "field": f"{map_name}.{lang_tag}", "code": "INVALID_I18N_TEXT", "message": "i18n text must be non-empty string"})

    return errors


def parse_import_payload(payload: dict[str, Any]) -> RoomImportConfig:
    errors = validate_import_json_payload(payload)
    if errors:
        raise ImportValidationError(errors)

    channels = [
        ChannelConfig(
            channel_id=str(ch["channel_id"]).strip(),
            channel_label=str(ch["channel_label"]).strip(),
            listen=bool(ch["listen"]),
        )
        for ch in payload["channels"]
    ]
    i18n_cfg = I18nLibraryConfig(
        room_name_i18n={str(k): str(v) for k, v in payload["i18n_library"]["room_name_i18n"].items()},
        custom_status_text_blocked_i18n={str(k): str(v) for k, v in payload["i18n_library"]["custom_status_text_blocked_i18n"].items()},
        custom_status_text_closed_i18n={str(k): str(v) for k, v in payload["i18n_library"]["custom_status_text_closed_i18n"].items()},
    )
    return RoomImportConfig(
        pin=str(payload["pin"]).strip(),
        target_capacity=int(payload["target_capacity"]),
        channels=channels,
        i18n_library=i18n_cfg,
    )


def room_import_to_runtime_dict(model: RoomImportConfig) -> dict[str, Any]:
    return {
        "pin": model.pin,
        "target_capacity": model.target_capacity,
        "channels": [
            {"channel_id": ch.channel_id, "channel_label": ch.channel_label, "listen": ch.listen, "owner": None}
            for ch in model.channels
        ],
        "i18n_library": {
            "room_name_i18n": dict(model.i18n_library.room_name_i18n),
            "custom_status_text_blocked_i18n": dict(model.i18n_library.custom_status_text_blocked_i18n),
            "custom_status_text_closed_i18n": dict(model.i18n_library.custom_status_text_closed_i18n),
        },
    }
