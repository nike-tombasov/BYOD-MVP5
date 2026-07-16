# BYOD Audio Distribution System

This repository contains the full technical specification of the BYOD Audio Distribution System.

Current status: the MVP supports a single-node Ubuntu Server 22.04 LTS VPS pilot
with self-hosted LiveKit. Stage X and Stage XI are completed for current MVP
pilot risk; Stage XII documents optional domain HTTPS/WSS mode and MVP launch hardening.

IMPORTANT:
1. Read hard_rules.md first
2. Then read system architecture.md files in order
3. Follow architecture strictly
4. Do not violate LiveKit requirements
5. Sound must work after each step

Documentation list:

Root-level docs and continuous docs/01_... through docs/24_... files are listed below.

* docs/01_project_goal.md
* docs/02_system_concept.md
* docs/03_roles.md
* docs/04_use_cases.md
* docs/05_channel_model.md
* docs/06_audio_architecture.md
* docs/07_livekit_engine.md
* docs/08_publisher_ui.md
* docs/09_backend.md
* docs/10_listener_ui.md
* docs/11_scaling.md
* docs/12_security.md
* docs/13_future_features.md
* mvp_status.md
* docs/14_ubuntu_deploy_contract.md
* docs/15_open_issues.md
* docs/16_ws_schema_v1.md
* docs/17_backend_persistence_json_v1.md
* docs/18_json_import_schema_v1.md
* docs/19_stage_vii_ix_acceptance_checklist_legacy.md
* docs/20_domain_https_wss_mode.md
* docs/21_ux_scenarios.md
* docs/22_unresolved_bugs.md
* docs/23_backend_logging_contract_stage_x.md
* docs/24_stress_tests.md
* hard_rules.md
* development_rules.md
* mvp_rules.md
* dev_environment.md
* roadmap.md
* legacy/legacy_readme.md

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
- `docs/14_ubuntu_deploy_contract.md`
- `docs/23_backend_logging_contract_stage_x.md`

Completed-stage snapshots:
- `legacy/stage_x_ubuntu_pilot/`
- `legacy/stage_xi_load_capacity/`

The current BYOD VPS deploy keeps direct-IP pilot mode available. Stage XII documents optional domain HTTPS/WSS mode for later implementation; production monitoring, scaling, load balancing, and multi-node deployment remain future hardening work.

## Stage XI — Protocol/engine load measurement

Stage XI is completed for current MVP pilot risk. The latest useful result is
documented in `docs/24_stress_tests.md`: approximately 695 emulated listener
participants were reached on the tested cloud.reg.ru VPS, with one real Web
Listener open separately and audio remaining present during observed load.

This is **Protocol/engine load only**. Browser/Web Listener UI mass-load testing
and a 2000-listener certificate remain future scaling/hardening work.

Permanent test manual and canonical result:
- `docs/24_stress_tests.md`

Historical snapshot:
- `legacy/stage_xi_load_capacity/`

Loader manual:
- `tools/go_livekit_loadgen/README.md`
