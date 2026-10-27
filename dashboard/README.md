# OAI RFsim Dashboard

Dashboard for the OAI RFsim handover testbed. Phase 5 adds campaign/repeated-run observability and comparative analysis on top of the live overview, KPI history, run explorer, gNB page, UE page, handover/mobility observability, and disabled-by-default safe experiment controls.

## What it does

- FastAPI backend with:
  - `GET /health`
  - `GET /api/topology`
  - `GET /api/config`
  - `WebSocket /ws`, broadcasting state every second
- Docker status polling through `/var/run/docker.sock`.
- F1 config parsing from `conf-cu.conf`, `conf-du.conf`, `conf-nr-ue.conf`, and DU1 overrides in `gnb-docker-compose.yaml`.
- Automatic detection of the running topology, so the dashboard follows a deploy or teardown without a restart.
- Optional best-effort telnet polling of the current topology's control node (the F1 CU at `192.168.70.150:9090`, the N2 source gNB/CU otherwise), disabled by default for OAI CU stability.
- Latest run summary from `results/runs/*/summary.json`.
- In-memory KPI history with 10-minute retention.
- Current UE count only when a current telemetry source exposes attached UE context.
- Separate AMF registration-event observation from recent AMF logs.
- Run artifact explorer for `results/runs/*`.
- Handover/mobility observability from existing run artifacts and bounded read-only log reads.
- Safe experiment actions, disabled by default, for trusted handover, smoke-test, and topology deploy/teardown scripts.
- One-click deploy/teardown of a full stack (F1, N2 monolithic, N2 CU/DU) from the Overview page, so operators can switch topologies without the CLI.
- Campaign summaries from `results/repeated/*` and linked `results/runs/*` artifacts.
- Statistical comparison of campaign groups and topologies.
- Safe repeated smoke-test campaign action, disabled by default.
- Three React pages: Overview, Results (Runs and Campaigns), and Controls.

## Run with Docker Compose

From the repository root:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

Open:

```text
http://localhost:5173
```

Backend API:

```text
http://localhost:8000/api/topology
http://localhost:8000/api/config
http://localhost:8000/api/runs
http://localhost:8000/api/kpi/history
http://localhost:8000/api/ues
http://localhost:8000/api/gnb
http://localhost:8000/api/handover
http://localhost:8000/api/handover/runs
http://localhost:8000/api/handover/durations
http://localhost:8000/api/campaigns
http://localhost:8000/api/campaigns/compare
http://localhost:8000/api/campaigns/export
http://localhost:8000/api/actions/capabilities
http://localhost:8000/api/actions/jobs
```

The backend uses host networking so the dashboard can still start when the OAI testbed and Docker networks are down. Passive CU telnet polling is disabled by default because repeated telnet `help` commands can destabilize some OAI CU builds. To enable it intentionally, start the backend with:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

When enabled, the backend rate-limits polling and caches telnet capability discovery instead of sending `help` every second. Explicit experiment actions such as smoke-test runs and handover triggers remain separate from passive telnet polling.

## Pages

One page per question an operator actually asks.

| Page | Route | Contents |
|---|---|---|
| Overview | `/` | Container health sidebar, topology diagram (all four topologies), live mobility, live UE latency, UE context, deploy/teardown, quick handover, interruption capture, collapsible cell configuration |
| Results | `/results/runs`, `/results/campaigns` | Run explorer (metrics, ping trace with handover markers, event timeline, message flow) and repeated-run campaigns with comparison |
| Controls | `/controls` | Action capabilities, safety guarantees, runtime checks, API token, smoke test, job list and output tails |

Consolidated from seven tabs. The gNB and UE pages folded into Overview; Handover merged
into the run explorer, since both read the same `results/runs/*` artifacts and both plotted
the same RTT trace. Old paths (`/gnb`, `/ue`, `/handover`, `/runs/:id`, `/campaigns/:id`)
redirect, so existing bookmarks keep working.

Two things were dropped rather than moved:

- The gNB page's RAN status panel duplicated the Overview sidebar.
- The gNB page's "throughput history" chart plotted `latest_run.iperf_mbps` from the KPI
  ring buffer, so it was a flat line that only stepped when a run finished. It read as a
  live throughput series and was not one.
- The UE page's CQI, MCS DL/UL, BLER DL/UL, PHR and serving-DU tiles are gone: no current
  telemetry path populates them, so they read "Unavailable" permanently. UE count and AMF
  registration events, which do have sources, moved to the Overview UE context card.

## Topology detection

The dashboard detects which topology is running from the containers present, using the
same probe order as `detect_topology()` in `scripts/lib.sh` (`oai-cu` → F1, `oai-gnb0` →
N2 monolithic, `oai-cu0` → N2 CU/DU, `oai-gnb` → USRP). Because the dashboard can itself
deploy and tear down stacks, this means it follows a topology switch without a restart:
the monitored container set, the telnet control endpoint, and the topology posted to the
handover actions all move together.

`DASHBOARD_TOPOLOGY` pins the topology instead of detecting it:

| Value | Behaviour |
|---|---|
| unset or `auto` (default) | detect from the running containers |
| `f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots` | pin, skipping detection |

Detection is reported rather than assumed. The state carries `topology_detection` with
`mode` (`auto`/`pinned`), `detected` (the observed topology, or `null`), and `source`
(`container_probe`, `fallback`, `DASHBOARD_TOPOLOGY`). When nothing identifiable is
running, the default topology is shown with `detected: null` and a warning — never a guess
presented as an observation.

The telnet control endpoint follows the topology: the CU (`192.168.70.150:9090`) for F1,
the source gNB (`192.168.70.160:9090`) for N2 monolithic, and the source CU
(`192.168.70.150:9090`) for N2 CU/DU. `usrp-cots` has no telnet control node and says so.

The live UE latency probe only runs when the detected topology has a UE container and that
container is running. Previously it issued a failing `docker exec` every second whenever
the testbed was down, and on `usrp-cots`, where the UE is an external COTS handset and no
`oai-nr-ue` container exists. When probing is not possible, `live_latency.probing` is
`false` with a `skip_reason`, and stale samples are dropped rather than left on a chart
that would read as live.

## State collection

A single background task collects state and publishes a snapshot; the WebSocket and the
state-backed REST endpoints (`/api/topology`, `/api/overview`, `/api/gnb`, `/api/handover`)
read that snapshot instead of each rebuilding it. Collection cost is therefore independent
of how many browsers are connected, and the blocking Docker SDK and artifact reads are
dispatched off the event loop.

Sources are grouped into refresh tiers by how fast they actually change:

| Tier | Default interval | Env var | Sources |
|---|---|---|---|
| fast | 1 s | `DASHBOARD_POLL_INTERVAL_SECONDS` | container status, live latency probe, telnet, action jobs |
| medium | 5 s | `DASHBOARD_MEDIUM_INTERVAL_SECONDS` | bounded Docker log reads: recent handover events, AMF registrations, CU mobility |
| slow | 30 s | `DASHBOARD_SLOW_INTERVAL_SECONDS` | parsed config, run list, latest run, handover chart, campaigns |

The slow tier is invalidated early when a new directory appears under `results/runs`, so a
finished experiment shows up without waiting out the interval.

KPI history is sampled once per fast cycle by the collector. It was previously sampled
inside each reader's rebuild, which made the series density depend on the number of open
browser tabs; `GET /api/kpi/history` is now a uniform ~1 Hz series regardless of readers.

On-demand detail reads (`/api/runs/{id}`, `/api/handover/runs/{id}`, campaign detail,
`/api/config`) are served directly rather than from the snapshot, so they always reflect
current artifacts.

## Run locally for degraded/offline development

Backend:

```bash
cd dashboard/backend
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DASHBOARD_REPO_ROOT=../.. uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd dashboard/frontend
npm install
npm run dev
```

If the frontend renders only the background and the browser console shows `React is not defined`, verify that `dashboard/frontend/vite.config.js` exists and includes `@vitejs/plugin-react`, then rebuild the frontend container without cache:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend
```

The dashboard is expected to start even when the OAI testbed is down. Missing containers, Docker socket issues, unavailable CU telnet, and missing configs are surfaced as warnings instead of fatal backend errors.
Missing historical `results/runs/*/summary.json` files are normal and produce `latest_run: null`.

## Phase 2 endpoints

- `GET /api/runs` lists run directories with summary metrics when available.
- `GET /api/runs/{run_id}` returns summary, optional ping/iperf summaries, events, and bounded ping samples.
- `GET /api/kpi/history` returns the in-memory KPI ring buffer.
- `GET /api/ues` returns the current parsed UE table if CU telnet exposes it.
- `GET /api/gnb` returns CU/DU config, container status, telnet status, and KPI history.
- `/ws` includes current topology, containers, telnet status, latest run, short KPI history, warnings, and source freshness.

Large artifacts such as full raw logs are intentionally not sent over the WebSocket.

## Phase 3 handover endpoints

- `GET /api/handover` returns current best-effort mobility readiness, CU/source telnet reachability, recent bounded log-derived events, and warnings.
- `GET /api/handover/runs` returns handover-oriented summaries for all `results/runs/*` directories.
- `GET /api/handover/runs/{run_id}` returns normalized events, message flow, ping interruption markers, bounded ping samples, and warnings for one run.
- `GET /api/handover/message-flow/{run_id}` returns only reconstructed message-flow steps.
- `GET /api/handover/durations` returns table-ready handover duration rows.

Handover event confidence values:

- `observed`: directly present in `events.csv` or another structured artifact.
- `parsed`: extracted from bounded Docker log or telnet text.
- `inferred`: derived from summary metrics, such as `estimated_interruption_ms` or `first_ping_after_handover_ms`.

Message-flow reconstruction is best-effort. `events.csv` is the primary source; collected `docker_logs/*.log` and live Docker log tails may add parsed hints. Artifact Docker log parsing reads only the last 512 KiB of each log file and keeps at most 30 matching parsed events per file. Live Docker log parsing uses bounded Docker log tails. Unknown endpoints remain `Unknown` rather than being inferred from topology names.

## Phase 4 safe controls

Actions are disabled unless the backend is started with:

```bash
DASHBOARD_ENABLE_ACTIONS=true
```

For dashboard-triggered actions that start OAI Docker Compose stacks, the backend controls the host Docker daemon through `/var/run/docker.sock`. Docker bind-mount paths are interpreted by the host daemon, so `DASHBOARD_REPO_ROOT` must be an absolute path that exists on the host, not only an in-container alias such as `/repo`. Use the host-actions override from the repository root:

> **This is enforced, not just documented.** Docker does not fail on a missing bind source — it silently creates an empty directory. Without the override, a dashboard-started stack mounts empty directories where `config.yaml` and the subscriber database should be, the 5GC never comes up, and root-owned junk is left on the host. The backend therefore compares `DASHBOARD_REPO_ROOT` against the host-side source of its own bind mount and **refuses deploy, teardown, smoke-test and repeated smoke-test with HTTP 409** when they do not match, naming the correct command. Telnet/ping-only actions (handover trigger, interruption capture) are unaffected. Blocking requires positive evidence of a mismatch: if the mount cannot be inspected, or the backend is not containerised, actions proceed as before.

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

The base compose file mounts `/dev/net/tun` into `dashboard-backend`; `network_mode: host` alone does not expose `/dev` devices. The override keeps the same TUN mount and mounts the repository at the host-visible absolute path, with only `results/` writable.

If the dashboard is already running with actions disabled, recreate only the backend with:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Or restart the full dashboard with:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

The enable flag is read at backend startup. Setting the shell variable after the backend is already running does not enable actions in that running process.

Action endpoints:

- `GET /api/actions/capabilities` reports whether actions are enabled and lists safety guarantees.
- `POST /api/actions/trigger-handover` starts a trusted handover job for the active topology when enabled and confirmed.
- `POST /api/actions/deploy-topology` brings a full stack up via `scripts/up.sh <topology>` (`f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots`) when enabled and confirmed.
- `POST /api/actions/teardown-topology` tears a stack down via `scripts/down.sh <topology>` when enabled and confirmed.
- `POST /api/actions/smoke-test` starts a trusted smoke-test job for `f1`, `n2-monolithic`, or `n2-cu-du` when enabled and confirmed.
- `POST /api/actions/repeated-smoke-test` starts a trusted repeated smoke-test campaign when enabled and confirmed.
- `GET /api/actions/jobs` lists dashboard-started jobs without full output tails.
- `GET /api/actions/jobs/{job_id}` returns job details with bounded stdout/stderr tails.

Safety guarantees:

- Disabled by default.
- No arbitrary commands.
- No shell execution; subprocesses use fixed argument arrays.
- Whitelisted scripts only: `scripts/trigger_handover.sh`, `scripts/measure_interruption.sh`, `scripts/up.sh`, `scripts/down.sh`, `scripts/run_smoke_test.sh`, and `scripts/run_repeated_smoke_tests.sh`. Each is invoked with a fixed argument array; the only free parameter is a topology name checked against a closed allowlist. No arbitrary container lifecycle: deploy/teardown can only run these two scripts for an allowlisted topology.
- Actions execute inside the dashboard backend container.
- Repository root is used as the subprocess working directory.
- The default `/repo` mount is sufficient for read-only dashboard use. For actions that invoke host Docker Compose, use `dashboard/docker-compose.dashboard.host-actions.example.yml` so `DASHBOARD_REPO_ROOT` is host-visible.
- The repository mount stays read-only except for `results/`, which is mounted read-write so smoke tests can create `results/runs/*` artifacts and `trigger_handover.sh` can append events under a smoke-test `RUN_DIR`.
- `/dev/net/tun` is mounted into the backend container for scripts that need UE TUN support.
- The backend image includes the minimal CLI/network tools required by the trusted scripts: `bash`, Docker CLI with Compose v2, `nc`, `ip`, `ss`, `ping`, and `python3`.
- The mounted Docker socket is used to interact with the local Docker daemon; no Docker daemon runs inside the backend container.
- Compose-spawning actions are refused when the repository root is not visible to the host Docker daemon at the same path (`runtime_checks.repo_root_host_visible`, surfaced as a banner on the Controls page).
- Only one dashboard-started action job can run at a time.
- stdout/stderr tails are bounded to 200 lines each.
- Action timeout handling terminates the whole process group, first with SIGTERM and then SIGKILL after a short grace period.
- Job state is in memory only and resets on backend restart.

Do not expose the dashboard on untrusted networks when actions are enabled.

## Authentication and CORS

Authentication is optional and disabled by default (lab default), so nothing changes unless you configure it.

- `DASHBOARD_API_TOKEN` — when set to a non-empty value, all `/api/actions/*` endpoints and the `/ws` WebSocket require the token. REST calls must send `Authorization: Bearer <token>`; the WebSocket must connect with `?token=<token>`. When unset, no auth is enforced. Requests without or with a wrong token get HTTP 401 (WebSocket close code 1008).
- `DASHBOARD_CORS_ORIGINS` — comma-separated allowed origins (for example `https://ops.example.com,https://lab.internal`). Defaults to `*` to preserve the previous lab behavior. Set an explicit list for anything reachable beyond localhost. Credentialed CORS is not enabled: the token travels in an `Authorization` header, not a cookie, and `*` combined with credentials is a configuration browsers reject anyway.

In the frontend, set the token on the **Controls** page ("API token" card). It is stored in the browser and attached to action requests and the live WebSocket; reload the page after changing it so the socket re-authenticates.

This is defense-in-depth, not a substitute for network isolation: still do not expose the dashboard on untrusted networks when actions are enabled, because the backend drives the host Docker daemon.

Start the backend with auth enabled, for example:

```bash
DASHBOARD_API_TOKEN="$(openssl rand -hex 24)" \
DASHBOARD_CORS_ORIGINS="http://localhost:5173" \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

## Phase 5 campaigns

Campaign endpoints:

- `GET /api/campaigns` lists discovered repeated-run campaigns.
- `GET /api/campaigns/{campaign_id}` returns one campaign with per-run rows, statistics, outliers, and warnings.
- `GET /api/campaigns/compare` returns comparison-ready summaries grouped by topology and campaign.
- `GET /api/campaigns/export` returns flat JSON rows suitable for client-side CSV conversion. It does not write files.

Artifact assumptions:

- Campaigns are discovered under `results/repeated/*`.
- The repeated smoke-test script writes `runs.txt`, `summary.csv`, `summary.json`, and per-run logs under each campaign directory.
- Linked run directories under `results/runs/*` remain the source of truth for run-level metrics when `summary.json` is available.
- Missing or malformed optional artifacts produce warnings instead of backend failures.

Statistics:

- Numeric campaign statistics are computed for handover interruption, first ping after handover, packet loss, RTT average, and iperf throughput.
- `null`/missing values are ignored for numeric statistics.
- If no valid values exist for a metric, its statistics are `null`.
- Reported statistics are `min`, `mean`, `median`, nearest-rank `p95`, and `max`.
- Outliers are simple ranked lists: failed runs, missing handover trigger, missing ping metrics, highest interruption, highest packet loss, highest RTT, and lowest iperf throughput.

Repeated smoke-test action:

- Endpoint: `POST /api/actions/repeated-smoke-test`.
- Request shape: `{"confirm": true, "topology": "f1", "count": 5}`.
- Allowed topologies are `f1`, `n2-monolithic`, and `n2-cu-du`.
- Count is bounded to 1 through 20.
- The trusted script is called with fixed arguments and `RUNS=<count>` in a controlled environment override.
- The action uses the same disabled-by-default gate, single-job concurrency, process-group timeout handling, and bounded output tails as Phase 4.

## Idle state

When no CU, DU, gNB or UE container exists, there is no topology to draw. The Overview
shows an explicit "No topology deployed" panel listing the deployable topologies instead
of rendering the fallback topology with every node stopped — which read as "the F1 stack
is deployed and broken" and named a stack the operator never chose. The sidebar likewise
hides the fallback RAN nodes and keeps only the core containers, which are shared by every
topology and therefore a real observation. A running core with no RAN is called out
separately, since deploying will reuse it.

Deployment is judged from observed container existence, not from the detected topology
name, so it is also correct when the topology is pinned. If Docker itself is unreachable
the normal view is kept: absence of evidence is not evidence of absence.

The top-level `status` field reflects this with a third value:

| Value | Meaning |
|---|---|
| `ok` | a topology is deployed and its required containers are up |
| `idle` | no RAN container exists — nothing is deployed |
| `degraded` | a warning was raised, or a deployed stack has a required container down |

`topology_detection` separates `warning` (a real problem: Docker unreachable, or an
unknown `DASHBOARD_TOPOLOGY` pin) from `note` (an idle host). Only `warning` feeds the
global warnings list, so an idle machine no longer reports itself as degraded.

## Mobility readiness semantics

`handover.readiness` distinguishes what was observed from what was never looked at:

| Value | Meaning |
|---|---|
| `ready` | telnet was polled and the control node answered |
| `degraded` | telnet was polled and did not answer |
| `not_observed` | nothing probed the control node — passive polling is disabled (the default), or the topology has no telnet endpoint |
| `unavailable` | a required container is not running |

`handover.cu_telnet_status` carries the same distinction as `reachable`, `unreachable`,
`polling_disabled`, or `no_endpoint`. Only `unreachable` — a probe that actually failed —
produces a warning. Reporting the disabled-by-default case as "not reachable" asserted a
failure that was never observed, and, because warnings drive the overall `status` field,
left a perfectly healthy stack reading `degraded` indefinitely.

For the same reason, a topology whose `.conf` files are not parsed carries a `note` on the
config payload instead of a warning: a known scope limit is not an anomaly.

## UE telemetry semantics

- `live_kpis.ue_count` means current attached UE context only. It is populated from CU telnet, or another true current-state source if one is added later.
- If CU telnet is unavailable or does not expose parseable UE context, `live_kpis.ue_count` remains `null` and the UI shows it as Unavailable.
- Recent AMF log matches are exposed separately as `live_kpis.amf_registration_events_seen` with source `amf_logs_tail` and window `last_500_log_lines`.
- AMF registration-event matches are not a current attachment count. Repeated tests, detach/reattach cycles, and failed attempts can make them differ from currently attached UEs.

## Validation

Check that the dashboard registry still matches the current compose files:

```bash
cd dashboard/backend
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_registry.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase2.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase3.py
```

Full validation from the repository root:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
docker compose -f dashboard/docker-compose.dashboard.yml config
python3 scripts/validate_cn_subscriber.py
cd dashboard/frontend && npm install && npm run build
git diff --check
```

## F1 smoke-test subscriber diagnostics

The RFsim UE uses IMSI `001010000000001`, key `fec86ba6eb707ed08905757b1bb44b8f`, OPC `C42449363BBAD02B66D16BC975D77CC1`, DNN `oai`, and slice SST `1` / SD `FFFFFF`. The SQL seed includes both numeric and canonical SUPI authentication aliases: `001010000000001` and `imsi-001010000000001`.

Validate the committed seed with:

```bash
python3 scripts/validate_cn_subscriber.py
```

If `wait_ue_data_ready.sh` times out with `oaitun_ue1` missing, it now prints focused UE/AMF/AUSF/UDM/UDR/MySQL diagnostics. If logs show `CONTEXT_NOT_FOUND` or MySQL is unhealthy, recreate the core DB from the updated SQL seed:

```bash
./scripts/down.sh f1 --volumes
./scripts/up.sh f1
```

`--volumes` is destructive for persisted compose-managed state and is intended for lab/testbed reset only.

## Limitations

- No lifecycle buttons.
- No config editing.
- No broad container lifecycle controls.
- Phase 4 can trigger trusted scripts only when `DASHBOARD_ENABLE_ACTIONS=true`.
- Phase 5 can start repeated smoke-test campaigns only when `DASHBOARD_ENABLE_ACTIONS=true`.
- Optional bearer-token auth is available (`DASHBOARD_API_TOKEN`), disabled by default; still do not expose actions on untrusted networks.
- The Overview quick handover and interruption capture follow the detected topology (`f1`, `n2-monolithic`, `n2-cu-du`) via the whitelisted actions. N2 uses the configured default target PCI / UE RRC ID; there is no source/target selection UI, and a same-direction N2 re-trigger needs a topology reset.
- The topology diagram is drawn for all four topologies from the container registry. Node addresses are registry values, not parsed config, so they stay accurate where `.conf` parsing is not implemented. The detailed config parser remains F1-only, so only F1 nodes show cell parameters such as PCI; other topologies say so rather than showing an F1-shaped configuration.
- The serving-cell highlight appears only when a telemetry source actually reports one. In practice that means F1 with CU log parsing; N2 topologies show "serving cell not observed" rather than highlighting a guess. The USRP diagram marks the COTS handset as outside the monitored stack, since it has no container.
- Campaign comparisons are artifact-derived and do not fabricate missing metrics or infer unavailable campaign status.
- No DU telnet parsing for F1; current F1 DU containers do not expose telnet.
- Log-derived handover events and message-flow steps are best-effort and bounded; artifact logs are parsed from a 512 KiB tail, and unavailable protocol details remain `null`, empty, or Unavailable.
- Live RF/MAC KPIs are shown only when the running OAI telnet output exposes them. Otherwise they are `null`/Unavailable. No current telemetry path populates CQI, MCS, BLER, PHR or serving DU, so those tiles were removed from the UI rather than shown permanently unavailable; the `live_kpis` fields remain in the API for a future telnet or xApp source.
- Unavailable current UE context remains `null`; AMF log-derived registration matches are shown separately as recent events.
- RFsim RF metrics such as RSRP/RSRQ/SINR may be synthetic or unavailable.
- Config parsing remains F1-focused; future topologies are represented in the registry for container discovery.
