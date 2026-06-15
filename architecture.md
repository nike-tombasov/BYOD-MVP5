# BYOD Audio Distribution System

This repository contains the full architecture of the BYOD Audio Distribution System.

IMPORTANT:
All development must follow the documentation below.
Do not change architecture without updating documentation.
`tbd.md` is for project lead personal notes only: it is out of architecture analysis scope and must not be modified by development tasks.

Read in this order:

1. HARD RULES
hard_rules.md

2. Development rules
development_rules.md

3. MVP RULES
mvp_rules.md

4. Development environment
dev_environment.md

5. Project goal
docs/00_project_goal.md

6. System concept
docs/01_system_concept.md

7. Roles
docs/02_roles.md

8. Use cases
docs/03_use_cases.md

9. Channel model
docs/04_channel_model.md

10. Audio architecture
docs/05_audio_architecture.md

11. LiveKit engine
docs/06_livekit_engine.md

12. Publisher UI
docs/07_publisher_ui.md

13. Backend
docs/08_backend.md

14. Listener UI
docs/09_listener_ui.md

15. Scaling
docs/10_scaling.md

16. Security
docs/11_security.md

17. Future features
docs/12_future_features.md

18. MVP status
docs/13_mvp_status.md

19. Open issues
docs/14_open_issues.md

20. WS schema v1
docs/15_ws_schema_v1.md

21. Backend persistence JSON schema v1
docs/16_backend_persistence_json_v1.md

22. JSON import schema v1
docs/17_json_import_schema_v1.md

23. Stage VII-IX acceptance checklist
docs/18_stage_vii_ix_acceptance_checklist.md

24. UX scenarios
docs/19_ux_scenarios.md

25. Unresolved bugs
docs/20_unresolved_bugs.md

26. Stage X backend logging contract
docs/21_backend_logging_contract_stage_x.md

27. Stress and load testing
docs/22_stress_tests.md

28. Legacy implementations
legacy/legacy_readme.md

Core rules:

- Python 3.11
- LiveKit version must remain 1.9.11
- track.name must equal channel_id
- selective subscribe only
- publish only between ON AIR and STOP
- queue overflow must drop oldest
- audio 48000 Hz stereo
- interlock logic must be preserved

Development rule:
Sound must work after each step.
