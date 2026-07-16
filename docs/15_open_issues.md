## 15. Open issues

Rules for docs/15_open_issues.md:
- This file is updated only by special request.
- All new ambiguities are discussed in chat first.
- Only unresolved items after discussion are written here.
- This file is not a second architecture spec.

### 15.2 Current unresolved items

1) JSON strict validation final freeze
- open decision: keep strict regex + reject-all policy or simplify for operator UX in first VPS cycle.

2) Persistence schema versioning format
- open decision: whether dedicated `meta_schema.json` is mandatory in MVP.

3) Migration rules v1->v2
- migration and rollback policy for persistence versions is not finalized.

4) Deploy rollback hardening for nginx config replacement
- current deploy flow backs up `/etc/nginx/nginx.conf` before replacement and validates with `nginx -t`, but if validation fails after installing the BYOD site config, files on disk may remain in a non-working state even though the running nginx process was not restarted;
- define and implement rollback behavior so failed validation restores the previous known-good nginx main/site config before exit.

### 15.3 Stress-test and metrics limitations

1) `71_collect_test_tails.sh` reliability verification
- potentially useful, but has not yet been proven in a real stress incident to collect all expected files correctly;
- requires repeat verification on the VPS before it is treated as a trusted incident bundle source.

2) `73_live_stress_watch.sh` transport counters are approximate
- current UDP/TCP detection may be rough if regex counts `udp`/`tcp` inside ICE candidates instead of only stable `connectionType` fields;
- acceptable for live operator view, but not final forensic transport accounting.

3) `72_metrics_snapshot.sh` unavailable-endpoint behavior
- the helper may return non-zero when `/admin/metrics_snapshot` is unavailable;
- acceptable for standalone diagnostics, but bundle behavior should remain tolerant and must be verified.

4) Go loadgen selected-mode media accounting
- historical stress data showed possible multiple selected audio tracks per worker;
- keep this as a known measurement risk unless current code guarantees at most one selected track per worker and tests prove it.

5) Compact per-worker final state artifact
- current `VALID_RUN` summaries can be trusted at summary level, but when detailed events are deleted it is hard to re-check every worker;
- future improvement: add compact `workers_final_state.csv` or equivalent.

### 15.4 Документационные разрывы между спецификацией и текущей реализацией

Эти пункты фиксируют известные разрывы между текущей спецификацией и реализацией. Они не являются срочными runtime-исправлениями: MVP-система сейчас работает достаточно стабильно, а изменения в backend/listener/deploy-коде по этим темам могут быть рискованнее, чем сохранение текущего поведения. Вернуться к ним можно позже при архитектурном и спецификационном hardening.

1) WS envelope `ts`
- `docs/16_ws_schema_v1.md` описывает `ts` как обязательное поле каждого envelope.
- Текущая backend/listener-валидация не навязывает `ts` строго; runtime оставляем без изменений.

2) WS `client_role` в payload `connecting`
- Спецификация показывает `client_role` для Listener/Publisher `connecting`.
- Текущий backend не валидирует `client_role` строго; runtime оставляем без изменений.

3) `request_on_air_ts` / `request_off_air_ts`
- Спецификация говорит, что эти timestamps сохраняются для логирования, и упоминает freshness/age-логику.
- Текущий runtime в основном опирается на порядок приёма backend и backend-время, без старого правила 30 секунд; для MVP это приемлемо, interlock-логику сейчас не меняем.

4) Runtime session fields vs logs
- Часть формулировок backend-спецификации всё ещё выглядит так, будто publisher/listener IP/timestamps являются постоянной DB-моделью.
- В текущей реализации часть этих данных является runtime-only или JSONL diagnostic log data; уточнить позже без изменения кода.

5) Listener diagnostic/loadgen fields
- Текущий Listener/loadgen `connecting` payload может включать необязательные diagnostic fields: `client_type`, `runner_id`, `loader_run_id`, `worker_id`, `loadgen_key` и т.п.
- Каноническая WS-схема пока не полностью описывает эти optional поля; protocol/runtime оставляем без изменений.

6) Logging event names
- Logging contract и фактические event names в коде не полностью нормализованы, например `listener_disconnected` vs текущие listener close/stale events.
- Сейчас не переименовываем существующие log events.

7) Owner state after backend restart
- Текущая persistence может восстановить owner mappings из runtime state.
- Если backend перезапущен без соответствующих live publisher sessions, operator recovery может требовать явный `off_air`; startup reconciliation сейчас не меняем.

8) Listener rapid channel switching
- `tbd.md` отмечает отсутствие формального debounce/backoff policy.
- Текущий Listener имеет attach/detach busy guards и timeout protection, но без формального debounce contract; оставить как будущий UI hardening/documentation issue.

9) Mobile background playback and system media controls
- The spec requires mobile background/locked-screen playback and system media controls.
- This behavior is currently browser/OS-dependent and is not guaranteed by the current Web Listener.
- Stage I/IV legacy Media Session behavior is reference material only.
- Legacy code must not be copied directly because the current Listener hard rules require one audio element, selective subscribe, and `autoSubscribe=false`.
- Future implementation should add a small Media Session compatibility layer without changing the core Listener audio architecture.
