# Dashboard Overview live handoff

Date: 2026-07-01

This handoff captures the dashboard Overview discussion, what was implemented, why the changes were made, how they were validated, and what remains limited.

## Starting point

The dashboard had already grown through the earlier phases:

- basic live topology and config observability;
- KPI history, gNB/UE/Runs pages;
- handover/mobility observability;
- disabled-by-default experiment controls;
- campaign/repeated-run analysis;
- remote-access and UX/radio display polish.

After real RFsim usage, the Overview page was still too noisy for live demos. It showed duplicated information, saved-run metrics where live values were expected, and did not make the handover interruption visually obvious during quick F1 handover triggers.

## Operator feedback

The requested changes were:

1. Make the left Handover Monitor cleaner:
   - group DU0 and DU1 under one DU card;
   - include `oai-ext-dn` under CN5G;
   - allow cards to collapse/expand;
   - add a global `Collapse all / Expand all` control below the “Handover Monitor” title.

2. Remove low-value Overview items:
   - remove the top topology strip;
   - remove duplicate “System healthy” and “Action enabled” cards;
   - remove saved-run RTT/HO cards from the primary Overview;
   - remove the Mobility State card because the useful parts are shown elsewhere;
   - remove the stale `Phase 5 dashboard` badge from the topology card.

3. Improve quick handover usability:
   - keep the existing safe backend action model;
   - remove the checkbox from Overview for repeated RFsim demos;
   - replace it with a clear warning message;
   - still only enable the button when `DASHBOARD_ENABLE_ACTIONS=true`, topology is F1, and no dashboard-started action is running.

4. Show the current serving DU:
   - CU telnet is disabled by default and DU telnet is not available;
   - current serving DU should be parsed from bounded CU logs when possible;
   - if serving DU cannot be observed, do not present an invented UE-to-DU path.

5. Replace “Live handover duration” with what the operator actually needs:
   - a live packet delivery / latency plot;
   - successful packets should show RTT through time;
   - interruption during handover should appear as missing packets/gaps;
   - recovery should be visible as packets are delivered again.

## Implemented changes

### Frontend Overview cleanup

Files:

- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/frontend/src/components/Sidebar.jsx`
- `dashboard/frontend/src/components/TopologyDiagram.jsx`

Implemented:

- Overview no longer renders the top topology strip.
- Overview no longer renders the right-side run summary panel.
- Overview no longer shows duplicate health/action/saved-run metric cards.
- The Overview layout is now focused on:
  - grouped Handover Monitor sidebar;
  - short operator summary;
  - topology diagram with active DU highlight;
  - quick F1 handover control;
  - live UE latency/interruption chart.
- The topology card no longer shows `Phase 5 dashboard`.
- Handover Monitor groups:
  - `CN5G`: core containers plus `oai-ext-dn`;
  - `CU`: CU containers;
  - `DU`: `oai-du0` and `oai-du1`;
  - `UE`: UE containers.
- Each group can be expanded/collapsed.
- A global `Collapse all / Expand all` button was added below the Handover Monitor title.

Reason:

The previous Overview mixed operator-critical live information with historical run data and duplicate status cards. For demos, the page needs to answer quickly:

- is the system running?
- where is the UE currently attached?
- can I trigger handover?
- did packet delivery stop and recover?

### Quick handover UX

File:

- `dashboard/frontend/src/pages/Overview.jsx`

Implemented:

- The checkbox was removed from the Overview quick handover control.
- A warning is shown instead:
  - this runs immediately on the local RFsim testbed;
  - use only while the F1 stack is intentionally active.
- The button still calls the existing safe endpoint:
  - `POST /api/actions/trigger-handover`
  - body: `{ "confirm": true }`
- Existing Phase 4 safety gates remain:
  - actions disabled by default;
  - requires backend startup with `DASHBOARD_ENABLE_ACTIONS=true`;
  - fixed trusted script only;
  - no arbitrary command execution;
  - no lifecycle controls;
  - no config editing;
  - single dashboard-started job at a time.

Reason:

During RFsim demo usage, repeated handover triggering is normal. The confirmation checkbox slowed down the workflow without adding meaningful safety beyond the existing backend gate and warning.

### Current serving DU from CU logs

Files:

- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/backend/validate_phase6.py`

Implemented:

- The backend reads a bounded CU log tail from `oai-cu`.
- It parses known F1 handover-related log patterns:
  - handover trigger target cell;
  - `RRCReconfigurationComplete` post-handover cell ID;
  - handover complete line;
  - GTP-U tunnel update remote IP as a fallback.
- It maps cell IDs and F1 local IPs to DU names using parsed F1 config:
  - `12345678` / `bc614e` maps to DU0;
  - `11111111` / `a98ac7` maps to DU1;
  - DU F1 local addresses also map back to DU names.
- The Overview topology highlights the parsed serving DU when available.
- UE path rows use source/confidence metadata:
  - `cu_telnet` / `observed` when current UE context exposes serving DU;
  - `cu_logs_tail` / `parsed` when inferred from CU logs;
  - `latest_run_artifacts` / `inferred` only for historical metrics;
  - `unknown` when no current source exists.

Reason:

The user observed that after handover the Overview did not change and showed `Unknown` for UE-DU information. Since F1 DU telnet is unavailable and passive CU telnet polling is disabled by default, bounded CU logs are the practical current-state source.

### Live UE latency / interruption chart

Files:

- `dashboard/backend/collectors/live_latency.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/backend/validate_phase6.py`

Implemented:

- Added `LiveLatencyMonitor`.
- It keeps an in-memory bounded ring buffer of live samples.
- It samples at roughly the dashboard update rate, with a minimum interval guard.
- It runs a fixed, bounded, non-shell command:

  ```bash
  docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
  ```

- Successful probes produce:
  - `reachable: true`;
  - parsed `rtt_ms`;
  - `status: delivered`.
- Failed probes produce:
  - `reachable: false`;
  - `rtt_ms: null`;
  - short error/status text;
  - `status: lost`, `timeout`, `unavailable`, or `error`.
- The chart plots RTT for delivered probes.
- Missed probes create gaps and red markers.
- The chart includes compact counters:
  - delivered samples;
  - missed samples;
  - probe interface/target;
  - source.

Reason:

The previous “Live handover duration” chart was based on CU log handover-command duration. That is not the same thing as data-plane interruption. The operator wanted to see packets being delivered, then interruption, then delivery again. The live ping-based chart directly represents that behavior.

## API/state impact

The following state now includes live latency:

- `GET /api/topology`
- `GET /api/overview`
- WebSocket `/ws` state

Relevant fields:

```json
{
  "live_latency": {
    "container": "oai-nr-ue",
    "interface": "oaitun_ue1",
    "target": "192.168.71.135",
    "source": "docker_exec_ping",
    "retention_samples": 300,
    "latest": {
      "timestamp": "...",
      "label": "HH:MM:SS",
      "reachable": true,
      "rtt_ms": 11.5,
      "status": "delivered",
      "error": null
    },
    "samples": [],
    "delivered_count": 0,
    "lost_count": 0,
    "warnings": []
  }
}
```

The Overview object also includes `overview.live_latency` for convenience.

## Validation performed

Backend/frontend validation:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase6.py
docker compose -f dashboard/docker-compose.dashboard.yml config
cd dashboard/frontend && npm install && npm run build
git diff --check
```

Runtime smoke:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build
```

Then:

```bash
curl -fsS http://localhost:8000/api/overview
```

Observed result:

- `/api/overview` returned live latency samples.
- Latest observed local probe:
  - `oaitun_ue1 -> 192.168.71.135`;
  - `reachable: true`;
  - `rtt_ms: ~11.5`;
  - `source: docker_exec_ping`.

## PR and merge record

Overview cleanup and live chart changes were committed and merged through:

- PR: <https://github.com/fsnobre/oai-rfsim-handover-testbed/pull/19>
- Merge commit: `b0f2c6ca838c6c5262883e720aad36775a940a77`

## Operational notes

To run the dashboard for local RFsim controls:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

To access remotely through Tailscale:

- run the dashboard on the mini PC;
- open the frontend through the mini PC Tailscale IP and frontend port;
- the frontend derives backend host from the browser host unless explicitly configured.

The live latency chart requires:

- dashboard backend can use Docker;
- `oai-nr-ue` container exists/runs;
- `oaitun_ue1` exists inside the UE container;
- EXT-DN target `192.168.71.135` is reachable.

If any of these are missing, the chart should show unavailable/lost samples rather than crashing.

## Remaining limitations

- The live latency chart is active probing. It is bounded and lightweight, but it is not passive telemetry.
- Serving DU detection depends on current CU log text patterns. If OAI log formats change, parsing may stop working.
- CU telnet passive polling remains disabled by default because repeated `help` polling previously destabilized CU.
- F1 DU telnet is still not used.
- RF/MAC KPIs such as CQI, MCS, BLER, PHR, RSRP, RSRQ, and SINR are still unavailable unless OAI exposes them through a safe current telemetry source.
- Quick handover does not itself create a saved experiment run. Saved run artifacts still come from smoke/repeated tests.
- No authentication is implemented. Do not expose an action-enabled dashboard on untrusted networks.
