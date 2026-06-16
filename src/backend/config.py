import os
from pathlib import Path


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
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return parsed


def _env_optional_int(name: str, min_value: int = 1) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return parsed


def _env_float(name: str, default: float, min_value: float = 0.0) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float") from exc
    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    return parsed


# ---------------------------------------------------------------------------
# Операционные лимиты backend.
# Менять безопасно только перед deploy/reconfiguration или между тестовыми
# profile runs, когда оператор понимает влияние на admission control.
# ---------------------------------------------------------------------------

# Версия WS envelope/schema. Менять только вместе с документированным protocol migration.
SCHEMA_VERSION = 1

# Время жизни LiveKit JWT token. Увеличивать/уменьшать только вместе с token refresh policy.
JWT_LIFETIME_SECONDS = 2 * 60 * 60

# Таймаут отсутствия heartbeat для online-сессий. Менять осторожно: влияет на stale detection.
HEARTBEAT_TIMEOUT_SECONDS = 30

# Таймаут active PLAY heartbeat для Listener. Менять осторожно: влияет на reconnect_required.
LISTENER_ACTIVE_PLAY_STALE_SECONDS = 60

# TCP timeout проверки доступности LiveKit. Можно менять при медленной сети/VPS diagnostics.
LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS = _env_float(
    "BYOD_LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS",
    1.5,
    min_value=0.1,
)

# Bootstrap target_capacity для чистого deploy без persisted room config.
DEFAULT_TARGET_CAPACITY = _env_int("BYOD_TARGET_CAPACITY", 200, min_value=1)

# Запас сверх target_capacity для временных reconnect/overlap listener-сессий. Например, 1.05 означает +5%.
MAX_ACTIVE_LISTENER_HEADROOM_RATIO = 1.05

# Делитель для расчёта глобального лимита новых Listener-подключений в секунду. Меньше значение — выше разрешённая скорость подключения.
MAX_NEW_CONNECTIONS_PER_SEC_DIVISOR = 15.0

# Минимально допустимый глобальный лимит новых Listener-подключений в секунду.
MAX_NEW_CONNECTIONS_PER_SEC_MIN = 1

# Override максимума активных Listener-сессий. Безопасно задавать для stress tests; пусто = считать от target_capacity.
MAX_ACTIVE_LISTENERS_OVERRIDE = _env_optional_int("BYOD_MAX_ACTIVE_LISTENERS", min_value=1)

# Override глобального лимита новых Listener-подключений в секунду. Безопасно задавать для stress tests; пусто = считать от target_capacity.
MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE = _env_optional_int("BYOD_MAX_NEW_CONNECTIONS_PER_SEC", min_value=1)

# Минимальный интервал между Listener connect/reconnect с одного client IP. Важно: лимит именно per IP. При NAT/общественном Wi-Fi несколько реальных пользователей могут выглядеть как один IP.
LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS = _env_int(
    "BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS",
    2,
    min_value=0,
)

# Host backend bind. Для Stage X/XI обычно 127.0.0.1, чтобы backend был доступен только локально за nginx.
BACKEND_HOST = _env_str("BYOD_BACKEND_HOST", "127.0.0.1")

# Port backend bind. Менять только вместе с systemd/nginx/operator docs.
BACKEND_PORT = _env_int("BYOD_BACKEND_PORT", 8000)

# Единственный allowed browser origin для CORS. Менять при смене public Listener origin.
CORS_ALLOWED_ORIGIN = _env_str("BYOD_CORS_ALLOWED_ORIGIN", "http://127.0.0.1:8080")

# LiveKit URL, который backend выдаёт клиентам и использует для reachability checks.
LIVEKIT_URL = _env_str("BYOD_LIVEKIT_URL", "ws://127.0.0.1:7880")

# LiveKit API key для JWT/API. Менять только синхронно с livekit.yaml.
LIVEKIT_API_KEY = _env_str("BYOD_LIVEKIT_API_KEY", "devkey")

# LiveKit API secret для JWT/API. Не логировать и не сохранять в diagnostics.
LIVEKIT_API_SECRET = _env_str("BYOD_LIVEKIT_API_SECRET", "secret")

# Базовый каталог backend JSON state/logs. Менять только вместе с deploy paths/permissions.
DATA_DIR = Path(_env_str("BYOD_DATA_DIR", "backend_data"))

# Файл room config persistence. Менять только при переносе storage layout.
ROOM_CONFIG_PATH = Path(_env_str("BYOD_ROOM_CONFIG_PATH", str(DATA_DIR / "room_config_v1.json")))

# Файл runtime state persistence. Менять только при переносе storage layout.
RUNTIME_STATE_PATH = Path(_env_str("BYOD_RUNTIME_STATE_PATH", str(DATA_DIR / "runtime_state_v1.json")))

# Файл recording marker persistence. Менять только при переносе storage layout.
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
