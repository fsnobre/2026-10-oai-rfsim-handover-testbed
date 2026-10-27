# CLAUDE.md — OAI RFsim Handover Testbed

Research testbed automating OAI 5G SA handover experiments (RFsim F1 / N2, plus USRP X310
real-radio configs) with a FastAPI + React monitoring dashboard. Docs live in `docs/`
(index and reading paths: `docs/README.md`). `AGENTS.md` holds the original agent notes;
the invariants below supersede and extend it.

## Hard invariants — do not violate

- Container names: `oai-amf`, `oai-smf`, `oai-upf`, `oai-cu`, `oai-du0`, `oai-du1`,
  `oai-nr-ue`, `oai-gnb0`, `oai-gnb1`, `oai-cu0`, `oai-cu1`, `oai-ext-dn`, plus core
  helpers (`oai-nrf`, `oai-udr`, `oai-udm`, `oai-ausf`, `mysql`). Compose files and
  `scripts/lib.sh` are the source of truth for names and addresses.
- F1 handover command is `ci trigger_f1_ho` (CU telnet `192.168.70.150:9090`).
  N2 is `ci trigger_n2_ho <target_pci>,<ue_rrc_id>`. Never invent a generic `handover`
  command.
- The event name `handover_trigger_start` in `events.csv` is a contract between
  `scripts/trigger_handover.sh` and `tools/parse_ping.py` (interruption metric silently
  becomes null if renamed). Keep it stable.
- Dashboard action-safety model is non-negotiable: actions disabled by default
  (`DASHBOARD_ENABLE_ACTIONS`), explicit `confirm`, whitelisted scripts with fixed argv,
  no `shell=True` / `create_subprocess_shell` anywhere in `dashboard/backend/actions.py`
  (tests assert on the source), single-job concurrency, bounded output tails,
  process-group timeouts.
- Dashboard telemetry honesty: never fabricate state. Unobserved values stay
  `null`/"Unavailable"/"not observed"; keep the observed/parsed/inferred/unknown
  confidence labels.
- Dashboard-only work stays under `dashboard/`; do not modify OAI testbed runtime files
  (compose files, `conf-*.conf`, `scripts/`) for dashboard-only changes.
- F1 DU containers do not expose telnet. Passive CU telnet polling stays disabled by
  default (repeated `help` probes have crashed the OAI CU).

## Git rules

- NEVER `git add -A` or `git add .`. Stage files explicitly by path. A background
  auto-commit tool also commits to `main` on a timer; unrelated artifacts may be present
  in the working tree at any time.
- `dashboard/frontend/node_modules/` is currently NOT gitignored — never stage it.
- Do not push unless explicitly asked.
- Commit per completed work package with a descriptive message, not at arbitrary points.

## Validation suite (run after any backend/frontend/scripts change)

From the repository root:

```bash
python3 -m compileall dashboard/backend
pip install -r dashboard/backend/requirements-dev.txt   # pytest + ruff + backend deps
ruff check dashboard/backend tools                      # lint (E501 intentionally ignored)
pytest dashboard/backend tools                          # backend validators + parse_ping golden tests
docker compose -f dashboard/docker-compose.dashboard.yml config
python3 scripts/validate_cn_subscriber.py
cd dashboard/frontend && npm install && npm run lint && npm run test && npm run build
```

The backend checks live in `dashboard/backend/tests/` (subject-named pytest
modules) and wrap the assertion logic in `dashboard/backend/validate_phase*.py`
/ `validate_registry.py`. Those `validate_*.py` files still run standalone
(`python3 dashboard/backend/validate_phaseN.py`) — the pytest modules import and
expose their checks for granular reporting.

For shell scripts: `bash -n scripts/*.sh` (plus `shellcheck` if installed).
The live OAI testbed is NOT assumed to be running; anything needing a live stack is
manual verification, not part of this suite.

## Docs conventions

- Naming taxonomy (see `docs/README.md`): `foundation-fNN-*`, `guide-*`, `tutorial-*`,
  `report-*`, `record-*`, `handoff-*`. Every new doc gets indexed in `docs/README.md`.
- Foundation IDs are stable identifiers; never renumber.
- New guides/tutorials declare required reading near the top.
