# BYOD Audio Distribution System

This repository contains the full technical specification of the BYOD Audio Distribution System.

Current status: MVP10 supports a single-node Ubuntu Server 22.04 LTS VPS pilot
with self-hosted LiveKit. Stage X and Stage XI are completed for current MVP
pilot risk; Stage XII technology discussion and decisions are next.

IMPORTANT:
1. Read hard_rules.md first
2. Then read system architecture.md files in order
3. Follow architecture strictly
4. Do not violate LiveKit requirements
5. Sound must work after each step

Documentation list:

Entries `00_...` through `22_...` are under `docs/`; root-level docs and deploy/operator docs are shown with explicit paths.

* 00_project_goal.md
* 01_system_concept.md
* 02_roles.md
* 03_use_cases.md
* 04_channel_model.md
* 05_audio_architecture.md
* 06_livekit_engine.md
* 07_publisher_ui.md
* 08_backend.md
* 09_listener_ui.md
* 10_scaling.md
* 11_security.md
* 12_future_features.md
* mvp_status.md
* docs/13_ubuntu_deploy_contract.md
* 14_open_issues.md
* 15_ws_schema_v1.md
* 16_backend_persistence_json_v1.md
* 17_json_import_schema_v1.md
* 18_stage_vii_ix_acceptance_checklist.md
* 19_ux_scenarios.md
* 20_unresolved_bugs.md
* 21_backend_logging_contract_stage_x.md
* 22_stress_tests.md
* hard_rules.md
* development_rules.md
* mvp_rules.md
* dev_environment.md
* roadmap.md
* legacy_readme.md


## BYOD VPS deploy package

Deploy package path: `deploy/stage_x_ubuntu_pilot`

Operator docs:
- `deploy/stage_x_ubuntu_pilot/docs/deploy_guide.md`
- `deploy/stage_x_ubuntu_pilot/docs/smoke_test_guide.md`
- `deploy/stage_x_ubuntu_pilot/docs/incident_quick_actions.md`
- `deploy/stage_x_ubuntu_pilot/docs/configuration_reference.md`
- `deploy/stage_x_ubuntu_pilot/docs/testing_diagnostics_metrics.md`

Canonical spec docs:
- `mvp_status.md`
- `docs/13_ubuntu_deploy_contract.md`
- `docs/21_backend_logging_contract_stage_x.md`

Completed-stage snapshots:
- `legacy/stage_x_ubuntu_pilot/`
- `legacy/stage_xi_load_capacity/`

The current BYOD VPS deploy is public-IPv4 and HTTP-only without a domain. Domain setup, TLS,
production monitoring, scaling, load balancing, and multi-node deployment are
future production-hardening work.

## Stage XI — Protocol/engine load measurement

Stage XI is completed for current MVP pilot risk. The latest useful result is
documented in `docs/22_stress_tests.md`: approximately 695 emulated listener
participants were reached on the tested cloud.reg.ru VPS, with one real Web
Listener open separately and audio remaining present during observed load.

This is **Protocol/engine load only**. Browser/Web Listener UI mass-load testing
and a 2000-listener certificate remain future scaling/hardening work.

Permanent test manual and canonical result:
- `docs/22_stress_tests.md`

Historical snapshot:
- `legacy/stage_xi_load_capacity/`

Loader manual:
- `tools/load_test/README.md`
