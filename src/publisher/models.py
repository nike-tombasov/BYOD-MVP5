from dataclasses import dataclass
import asyncio
import queue

import sounddevice as sd
from livekit import rtc


@dataclass
class ChannelRuntime:
    channel_id: str
    label: str
    listen: bool
    owner: str | None
    desired_on_air: bool = False
    streaming: bool = False
    audio_queue: queue.Queue[bytes] | None = None
    capture_stream: sd.InputStream | None = None
    source: rtc.AudioSource | None = None
    local_track: rtc.LocalAudioTrack | None = None
    track_sid: str | None = None
    sender_task: asyncio.Task | None = None
    last_actual_status: str = "FREE"
