# BYOD Audio Distribution System

This repository contains the full technical specification of the BYOD Audio Distribution System.

Current status: MVP10 supports a single-node Ubuntu Server 22.04 LTS VPS pilot
with self-hosted LiveKit. Stage X is completed; Stage XI load and capacity
characterization has an initial Protocol/engine tooling baseline; real VPS
measurement runs are pending.

IMPORTANT:
1. Read hard_rules.md first
2. Then read system architecture.md files in order
3. Follow architecture strictly
4. Do not violate LiveKit requirements
5. Sound must work after each step

Documentation list:

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
* 13_mvp_status.md
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

Backend logging contract:
- `docs/21_backend_logging_contract_stage_x.md`

Completed-stage snapshot:
- `legacy/stage_x_ubuntu_pilot/`

The current BYOD VPS deploy is public-IPv4 and HTTP-only without a domain. Domain setup, TLS,
production monitoring, scaling, load balancing, and multi-node deployment are
future production-hardening work.

## Stage XI — Protocol/engine load measurement

Stage XI tooling baseline is implemented for **Protocol/engine load only**.
Browser/Web Listener UI load testing is explicitly out of scope and is
postponed to future Web Listener UI hardening. The goal is VPS resource
characterization: CPU, RAM, network RX/TX, disk, and backend/LiveKit/nginx
behavior under increasing Listener count. The tooling includes Go LiveKit SDK loadgen, 
a VPS Analyzer, and a local-only backend metrics endpoint.

Permanent test manual:
- `docs/22_stress_tests.md`

Loader manual:
- `tools/load_test/README.md`
