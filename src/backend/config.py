import os
from pathlib import Path

SCHEMA_VERSION = 1
JWT_LIFETIME_SECONDS = 2 * 60 * 60
HEARTBEAT_TIMEOUT_SECONDS = 30
LISTENER_ACTIVE_PLAY_STALE_SECONDS = 60


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    parsed = int(value)
    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return parsed


LIVEKIT_URL = _env_str("BYOD_LIVEKIT_URL", "ws://127.0.0.1:7880")
LIVEKIT_API_KEY = _env_str("BYOD_LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = _env_str("BYOD_LIVEKIT_API_SECRET", "secret")

BACKEND_HOST = _env_str("BYOD_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = _env_int("BYOD_BACKEND_PORT", 8000)
CORS_ALLOWED_ORIGIN = _env_str("BYOD_CORS_ALLOWED_ORIGIN", "http://127.0.0.1:8080")

DATA_DIR = Path(_env_str("BYOD_DATA_DIR", "backend_data"))
ROOM_CONFIG_PATH = Path(_env_str("BYOD_ROOM_CONFIG_PATH", str(DATA_DIR / "room_config_v1.json")))
RUNTIME_STATE_PATH = Path(_env_str("BYOD_RUNTIME_STATE_PATH", str(DATA_DIR / "runtime_state_v1.json")))
RECORDING_STATE_PATH = Path(_env_str("BYOD_RECORDING_STATE_PATH", str(DATA_DIR / "recording_state_v1.json")))

LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS = float(_env_str("BYOD_LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS", "1.5"))

DEFAULT_ROOM_CONFIG = {
    "pin": _env_str("BYOD_DEFAULT_PIN", "123456"),
    "target_capacity": _env_int("BYOD_TARGET_CAPACITY", 200, min_value=1),
    "channels": [
        {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": False},
        {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": True},
        {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": True},
        {"channel_id": "channel_3", "channel_label": "Reserve 1", "listen": False},
        {"channel_id": "channel_4", "channel_label": "Reserve 2", "listen": False},
    ],
    "i18n_library": {
        "room_name_i18n": {"en": "Conference room", "ru": "Зал конференции"},
        "custom_status_text_blocked_i18n": {
            "en": "Stream temporarily stopped",
            "ru": "Трансляция временно остановлена",
        },
        "custom_status_text_closed_i18n": {
            "en": "The conference is over. Thank you for your participation",
            "ru": "Конференция окончена. Благодарим за участие",
        },
    },
}
