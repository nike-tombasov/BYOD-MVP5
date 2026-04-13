from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    channel_id: str
    channel_label: str
    listen: bool


@dataclass(frozen=True)
class I18nLibraryConfig:
    room_name_i18n: dict[str, str]
    custom_status_text_blocked_i18n: dict[str, str]
    custom_status_text_closed_i18n: dict[str, str]


@dataclass(frozen=True)
class RoomImportConfig:
    pin: str
    target_capacity: int
    channels: list[ChannelConfig]
    i18n_library: I18nLibraryConfig
