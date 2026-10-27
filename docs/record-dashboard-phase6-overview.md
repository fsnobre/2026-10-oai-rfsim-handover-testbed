# Dashboard Phase 6: Operator Overview

Date: 2026-07-01

## Purpose

Phase 6 turns the dashboard Overview into the main operator cockpit for F1 RFsim demos. The existing dashboard already exposes container health, run artifacts, handover observability, campaigns, and safe controls. The Overview should combine the most useful pieces so an operator can see the current testbed, trigger a safe RFsim F1 handover, and visually inspect packet delivery interruption without switching tabs.

## Operator workflow

1. Start the dashboard with actions enabled when controlled experiment actions are needed:

   ```bash
   DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
     docker compose -f dashboard/docker-compose.dashboard.yml \
       -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
   ```

2. Open Overview.
3. Confirm core/RAN/UE containers are healthy in the grouped, collapsible sidebar and topology diagram.
4. Use the topology highlight to see the serving DU when CU logs expose it.
5. Use the “Quick handover” control for RFsim demos.
6. Inspect the live UE latency chart. Successful probes show RTT; missed probes create gaps/red markers, so a handover interruption appears as delivered packets, then a gap, then recovery.

The Overview intentionally avoids showing every available field. The top topology info strip, duplicate health cards, duplicate action status cards, mobility detail card, and saved-run summary cards are intentionally omitted. Detailed tables remain on the gNB, UE, Runs, Handover, Controls, and Campaigns pages.

## Data model

The backend exposes an Overview-oriented object through:

- `GET /api/overview`
- `/ws` as `state.overview`

The object contains:

- `ue_paths`: best-known UE path rows, with current serving DU shown only when observed.
- `latest_metrics`: latest run metrics for interruption, RTT, packet loss, and iperf.
- `handover_chart`: chart-ready saved-run ping samples for APIs that need them; Overview prioritizes live latency probes.
- `live_latency`: bounded live ICMP probe history from `oai-nr-ue` over `oaitun_ue1` to `192.168.71.135`.
- `actions`: whether quick trigger is supported/enabled and the currently running job.
- `handover`: compact live mobility readiness fields, including bounded CU-log mobility state when available.
- `warnings`: Overview-specific warnings.

Each UE path row includes:

- `ue_id`
- `serving_du`
- `path`, for example `["UE", "DU1", "CU", "UPF", "EXT-DN"]`
- `metrics`
- `source`
- `confidence`
- `warnings`

Confidence values:

- `observed`: directly from current parsed UE telemetry, such as CU telnet UE context.
- `parsed`: extracted from bounded logs or textual telemetry.
- `inferred`: derived from latest run artifacts.
- `unknown`: container/config context exists, but no current or artifact source can identify attachment.

Frontend display rules:

- If serving DU is not observed, the Overview must not render `UE → Unknown → CU` as a primary path. It should show “DU not observed” and explain that current serving-DU state is unavailable from enabled telemetry.
- Latest-run metrics may still be shown as evidence, but they must be visually separated from current attachment state.
- When CU logs expose F1 handover completion, serving DU is parsed by mapping the post-handover `cellID` to DU config cell IDs. In the current F1 config, `12345678` maps to DU0 and `11111111` maps to DU1.
- The Overview should not show saved-run metrics as primary cards. Saved-run data belongs in Handover/Runs, with only a small reference if useful.
- The primary Overview chart is live packet delivery/latency. It should not label CU log handover-command duration as packet interruption.

## Safety behavior

- The Overview “Quick handover” trigger uses the existing `POST /api/actions/trigger-handover` endpoint.
- It never introduces a generic handover command.
- It is only enabled when:
  - backend actions are enabled with `DASHBOARD_ENABLE_ACTIONS=true`;
  - topology is F1/RFsim;
  - no dashboard-started action job is already running;
- the F1 stack is intentionally active.
- It keeps Phase 4 safety guarantees:
  - no arbitrary commands;
  - no shell execution;
  - fixed trusted script argv;
  - single-job concurrency;
  - bounded output tails.

Quick handover is a control action. It uses an inline warning instead of a checkbox so repeated RFsim demos stay fast. It can update live CU-log mobility state. The Overview latency chart is independent of saved smoke runs and continuously samples packet delivery while the dashboard is open.

## Telemetry limits

- F1 DU telnet is still not used.
- Serving DU is shown only when observed or parsed. Otherwise it is `Unknown`.
- RF/MAC KPIs such as CQI, MCS, BLER, PHR, RSRP, RSRQ, and SINR remain unavailable unless OAI exposes them through a safe current telemetry source.
- Artifact-derived metrics are labeled `inferred` and must not be presented as current live attachment state.
- A quick handover can update the serving-DU field when CU logs include parseable handover completion lines. If those patterns change or logs are unavailable, serving DU remains “DU not observed.”
- Live latency uses bounded `docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135` probes. If Docker, the UE container, the tunnel interface, or EXT-DN is unavailable, samples are recorded as missed/unavailable instead of crashing the dashboard.
- Passive CU telnet polling remains disabled by default through `DASHBOARD_ENABLE_TELNET_POLLING=false`.

## Validation expectations

Backend:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase6.py
```

Frontend:

```bash
cd dashboard/frontend
npm install
npm run build
```

Runtime smoke:

- Overview renders with the OAI stack down.
- Overview renders with no historical runs.
- Overview live latency chart renders delivered/missed probe samples when the UE data plane is available, and useful empty/unavailable states otherwise.
- Quick trigger is disabled when actions are disabled.
- Quick trigger starts a job when actions are enabled.
