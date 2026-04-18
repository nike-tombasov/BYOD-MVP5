SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_SIZE = 960
QUEUE_MAXSIZE = 32
HEARTBEAT_SECONDS = 5
TOKEN_REFRESH_LEAD_SECONDS = 10 * 60
TOKEN_REFRESH_POLL_SECONDS = 15
CHANNEL_IDS = [f"channel_{i}" for i in range(32)]
PIN_LENGTH = 6
PUBLISHER_UI_VERSION = "v0.5"

COLORS = {
    "green": "#8FB996",
    "yellow": "#C9B26A",
    "red": "#B97A7A",
    "blue": "#1F3A5F",
    "text": "#D6D6D6",
    "line": "#FFFFFF",
    "bg": "#262626",
    "field_bg": "#333333",
    "dropdown_list_bg": "#3B3B3B",
    "btn_disabled": "#4A4A4A",
    "btn_active": "#6A6A6A",
    "btn_hover": "#B3B3B3",
}


def status_html(text: str, color: str) -> str:
    return f"<span style='color:{color}; font-size: 13px; font-weight: 700;'>■</span> {text}"
