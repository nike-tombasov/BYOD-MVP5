from pathlib import Path

SCHEMA_VERSION = 1
JWT_LIFETIME_SECONDS = 2 * 60 * 60
HEARTBEAT_TIMEOUT_SECONDS = 30
LISTENER_ACTIVE_PLAY_STALE_SECONDS = 60

LIVEKIT_URL = "ws://127.0.0.1:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "secret"

DATA_DIR = Path("backend_data")
ROOM_CONFIG_PATH = DATA_DIR / "room_config_v1.json"
RUNTIME_STATE_PATH = DATA_DIR / "runtime_state_v1.json"
RECORDING_STATE_PATH = DATA_DIR / "recording_state_v1.json"

DEFAULT_ROOM_CONFIG = {
    "pin": "123456",
    "target_capacity": 200,
    "channels": [
        {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": False},
        {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": True},
        {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": True},
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
