# HARD RULES (DO NOT VIOLATE)

* Python v3.11
* LiveKit version: 1.9.11
* track.name == channel_id
* Listener subscribes only to track.name == selected channel_id
* publish only between ON AIR and STOP
* publish only when owner == self publisher_id
* backend is single source of truth for owner assignment
* queue full → drop oldest (non-blocking)
* audio sample rate: 48000 Hz only
* audio channels: stereo
* frame size: 960 samples
* codec: Opus
* selective subscribe only
* autoSubscribe = false
* single audio element for listener session
* heartbeat publisher → backend: 5 seconds
* timeout publisher: 15 seconds
* Interlock logic must prevent multiple publishers for one channel_id
* Audio device must be opened before ON AIR
* Send frames only after ON AIR
* track created only after publish
* track removed after STOP