# Development Environment

Operating system:
- Windows 11

IDE:
- PyCharm

Python:
- Python 3.11
- virtual environment

Publisher:
- Python application
- runs locally on Windows
- later packaged to .exe

Backend:
- Python FastAPI
- runs locally on Windows during development
- will move to Ubuntu VPS later

Listener:
- static HTML + JS
- opened locally in browser
- no web server required for MVP
- test via file:// or localhost
- will move to Ubuntu VPS later

Browser testing:
- Chrome
- Edge
- Safari (later)
- mobile browsers later

LiveKit:
- local LiveKit server for development
- Windows build
- will move to Ubuntu VPS later

Development rules:
- no Docker for MVP
- no Linux-specific code
- no systemd services
- no nginx required for MVP

Networking:
- localhost testing
- local IP allowed
- no domain required
- later public IP on VPS

Goal:
- full local end-to-end testing:
publisher → backend → livekit → listener
- then same full VPS end-to-end testing:
online publisher → VPS backend → VPS livekit → VPS listener
