# Repository agent notes

- Dashboard work must live under `dashboard/` unless explicitly requested.
- Do not modify the existing OAI testbed runtime files for dashboard-only work.
- Treat the current compose files and `scripts/lib.sh` as source of truth for service/container names.
- Preserve F1 facts:
  - Containers: `oai-amf`, `oai-smf`, `oai-upf`, `oai-cu`, `oai-du0`, `oai-du1`, `oai-nr-ue`, plus core helpers such as `oai-nrf`, `oai-udr`, `oai-udm`, `oai-ausf`, `mysql`, `oai-ext-dn`.
  - CU telnet endpoint: `192.168.70.150:9090`.
  - F1 handover command: `ci trigger_f1_ho`.
  - Do not invent or use a generic `handover` command for F1.
  - Current F1 DU containers do not expose telnet; dashboard Phase 1 must not depend on DU telnet.
- Phase 1 dashboard is read-only: no lifecycle controls, no config editing, no DU telnet parsing.
