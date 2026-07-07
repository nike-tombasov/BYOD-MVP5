import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return parsed


# =============================================================================
# ОПЕРАТИВНО МЕНЯЕМЫЕ ЧИСЛА BACKEND
# =============================================================================
# Эти значения можно менять перед stress test или перед мероприятием.
# Менять только цифры справа. После изменения нужен restart byod-backend.

# Сколько живёт LiveKit token, который backend выдаёт Listener/Publisher.
JWT_LIFETIME_SECONDS = 7200

# Через сколько секунд без heartbeat backend считает сессию устаревшей.
HEARTBEAT_TIMEOUT_SECONDS = 30

# Через сколько секунд без PLAY heartbeat Listener считается неактивным для active-play статистики.
LISTENER_ACTIVE_PLAY_STALE_SECONDS = 60

# Сколько секунд backend ждёт TCP-проверку LiveKit.
LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS = 1.5

# Базовая расчётная ёмкость Listener для чистого deploy без сохранённого room config.
DEFAULT_TARGET_CAPACITY = 200

# Запас сверх target_capacity для временных reconnect/overlap Listener-сессий. 1.05 = +5%.
MAX_ACTIVE_LISTENER_HEADROOM_RATIO = 1.05

# Если None — считать от target_capacity. Если нужно быстро задать жёсткий максимум, поставить число, например 2500.
MAX_ACTIVE_LISTENERS_OVERRIDE = _env_int("BYOD_MAX_ACTIVE_LISTENERS_OVERRIDE", 0, 1) or None

# Делитель для расчёта глобального лимита новых Listener-подключений в секунду. Меньше число = быстрее разрешённый массовый вход.
MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR = 15.0

# Минимальный глобальный лимит новых Listener-подключений в секунду.
MAX_NEW_CONNECTIONS_PER_SEC_MIN = 1

# Если None — считать от target_capacity. Если нужно быстро задать скорость входа, поставить число, например 200.
MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE = _env_int("BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE", 0, 1) or None

# Минимальный интервал между Listener connect/reconnect с одного client IP. Важно: это per IP. При NAT/общественном Wi-Fi много реальных пользователей могут выглядеть как один IP.
LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS = _env_int("BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS", 2, 0)

# Temporary loadgen-only bypass for per-IP reconnect throttle. Safe by default.
LOADGEN_RECONNECT_BYPASS_ENABLED = _env_bool(
    "BYOD_LOADGEN_RECONNECT_BYPASS_ENABLED",
    _env_bool("LOADGEN_RECONNECT_BYPASS_ENABLED", False),
)
LOADGEN_RECONNECT_BYPASS_KEY = (
    _env_str("BYOD_LOADGEN_RECONNECT_BYPASS_KEY", "")
    or _env_str("LOADGEN_RECONNECT_BYPASS_KEY", "")
    or None
)


# Обычная deploy/config секция. Эти значения обычно задаются через env/deploy,
# а не правятся вручную перед stress test.

# Версия WS envelope/schema. Менять только вместе с documented protocol migration.
SCHEMA_VERSION = 1

BACKEND_HOST = _env_str("BYOD_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = _env_int("BYOD_BACKEND_PORT", 8000)
CORS_ALLOWED_ORIGIN = _env_str("BYOD_CORS_ALLOWED_ORIGIN", "http://127.0.0.1:8080")

LIVEKIT_URL = _env_str("BYOD_LIVEKIT_URL", "ws://127.0.0.1:7880")
LIVEKIT_API_KEY = _env_str("BYOD_LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = _env_str("BYOD_LIVEKIT_API_SECRET", "secret")

DATA_DIR = Path(_env_str("BYOD_DATA_DIR", "backend_data"))
ROOM_CONFIG_PATH = Path(_env_str("BYOD_ROOM_CONFIG_PATH", str(DATA_DIR / "room_config_v1.json")))
RUNTIME_STATE_PATH = Path(_env_str("BYOD_RUNTIME_STATE_PATH", str(DATA_DIR / "runtime_state_v1.json")))
RECORDING_STATE_PATH = Path(_env_str("BYOD_RECORDING_STATE_PATH", str(DATA_DIR / "recording_state_v1.json")))


def derive_max_active_listeners(target_capacity: int) -> int:
    if MAX_ACTIVE_LISTENERS_OVERRIDE is not None:
        return MAX_ACTIVE_LISTENERS_OVERRIDE
    return int(target_capacity * MAX_ACTIVE_LISTENER_HEADROOM_RATIO)


def derive_max_new_connections_per_sec(target_capacity: int) -> int:
    if MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE is not None:
        return MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE
    return max(
        MAX_NEW_CONNECTIONS_PER_SEC_MIN,
        int(target_capacity / MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR),
    )


DEFAULT_ROOM_CONFIG = {
    "pin": _env_str("BYOD_DEFAULT_PIN", "123456"),
    "target_capacity": DEFAULT_TARGET_CAPACITY,
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
