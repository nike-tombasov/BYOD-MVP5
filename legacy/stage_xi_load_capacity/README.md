# Stage XI legacy snapshot — Load and Capacity Characterization

Stage XI completed BYOD protocol/engine load and capacity characterization for current MVP pilot risk.

This snapshot preserves the implementation state used after Stage XI finalization:
- Ubuntu single-VPS deploy package;
- backend;
- Listener UI;
- Go LiveKit loadgen;
- permanent stress-test specification/result document.

Result summary:
- latest useful stress-test result: 23.06.2026;
- VPS: cloud.reg.ru, 3 vCPU × 2.2 GHz, NVMe, 3 GB RAM, 10 GB SSD;
- approximately 695 emulated listener participants reached;
- one real Web Listener remained open and audio did not disappear during observed load;
- result is sufficient for current MVP pilot risk.

Limitations:
- not browser/Web Listener mass-load testing;
- not a 2000-listener capacity certificate;
- further scaling characterization remains future work.

Rules:
- Do not reuse directly.
- Use only as historical reference.
- Current architecture is defined by root `architecture.md` and current `docs/`.
