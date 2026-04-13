from dataclasses import dataclass, field


@dataclass
class ListenerRuntime:
    connect_sec: int
    connect_count: int
    last_connect_by_ip: dict[str, int] = field(default_factory=dict)
