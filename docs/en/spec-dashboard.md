# Dashboard Specification: OAI RFSim Handover Testbed Monitor

## Overview

A custom web dashboard for real-time monitoring and control of the OAI 5G RFsim handover testbed. Inspired by the OAIBOX™ Dashboard (by Allbesmart), adapted for our CU/DU-split RFsim architecture with handover capabilities.

Reference material in `docs/OAIBOX_info/` — screenshots and PDF from the commercial OAIBOX product.

## Architecture

### Testbed Topology (what we monitor)

```
                    ┌─────────┐
                    │  CN5G   │ (AMF, SMF, UPF, NRF, etc.)
                    └────┬────┘
                         │ N2/N3
                    ┌────┴────┐
                    │   CU    │ (gNB-CU, telnet on port 9090)
                    ├────┬────┤
                    │ F1 │ F1 │
               ┌────┴──┐ ┌──┴────┐
               │  DU0  │ │  DU1  │ (each with own PCI, ARFCN)
               └───┬───┘ └───┬───┘
                   │ RFsim   │ RFsim
               ┌───┴─────────┴───┐
               │       UE        │ (RFsim server, OAI nrUE)
               └─────────────────┘
```

All components run as Docker containers via docker-compose.

### Dashboard Stack

```
┌─────────────────────────────────────────────┐
│              React Frontend                  │
│  (Recharts, Tailwind, WebSocket client)      │
├─────────────────────────────────────────────┤
│              FastAPI Backend                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Telnet   │ │ Docker   │ │ Log Watcher  │ │
│  │ Poller   │ │ Monitor  │ │ (HO events)  │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │ Config   │ │ WebSocket broadcast      │  │
│  │ Parser   │ │ (real-time KPI stream)   │  │
│  └──────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────┤
│         Docker Engine / Containers           │
│  (CN5G, CU, DU0, DU1, UE, oai-ext-dn)          │
└─────────────────────────────────────────────┘
```

### Directory Structure (within this repo)

```
dashboard/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Dashboard configuration (ports, container names)
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── telnet_poller.py     # Async telnet client for gNB MAC/RRC stats
│   │   ├── docker_monitor.py    # Docker SDK container status polling
│   │   ├── log_watcher.py       # Docker log tailing for HO events + message flow
│   │   └── config_parser.py     # OAI .conf file parser (CU, DU0, DU1 configs)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── kpi.py               # Pydantic models for UE KPIs
│   │   ├── handover.py          # HO event, HO duration models
│   │   └── topology.py          # Network topology state model
│   ├── api/
│   │   ├── __init__.py
│   │   ├── containers.py        # REST endpoints: container lifecycle
│   │   ├── config.py            # REST endpoints: read/write OAI configs
│   │   ├── handover.py          # REST endpoints: trigger HO, get HO history
│   │   └── websocket.py         # WebSocket endpoint: real-time KPI + events
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── TopBar.jsx
│   │   │   │   └── NavTabs.jsx
│   │   │   ├── topology/
│   │   │   │   └── TopologyDiagram.jsx    # SVG network diagram with live status
│   │   │   ├── kpi/
│   │   │   │   ├── KpiCard.jsx            # Summary card (value + min/max/avg)
│   │   │   │   └── TimeSeriesChart.jsx    # Recharts line chart
│   │   │   ├── handover/
│   │   │   │   ├── HandoverTimeline.jsx   # Event timeline
│   │   │   │   ├── HandoverDuration.jsx   # Duration table
│   │   │   │   └── HandoverTrigger.jsx    # Trigger button
│   │   │   ├── containers/
│   │   │   │   └── ContainerControl.jsx   # Start/Stop/Restart per container
│   │   │   ├── logs/
│   │   │   │   ├── MessageFlow.jsx        # 5G SA message flow table
│   │   │   │   └── RawLogs.jsx            # Raw gNB log viewer
│   │   │   └── config/
│   │   │       └── GnbConfig.jsx          # Configuration display/editor
│   │   ├── pages/
│   │   │   ├── Overview.jsx
│   │   │   ├── GnbPage.jsx
│   │   │   ├── UePage.jsx
│   │   │   └── HandoverPage.jsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   └── useKpiHistory.js
│   │   ├── utils/
│   │   │   └── constants.js
│   │   └── App.jsx
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.dashboard.yml   # Dashboard services only
└── README.md
```

## Data Sources

### 1. gNB Telnet Interface (primary KPI source)

OAI gNB exposes a telnet server on port 9090 (when built with `--build-lib telnetsrv`).
The CU telnet provides RRC-level stats; DU telnets provide MAC/PHY stats.

**Polling interval:** ~1 second

**Key commands and expected output patterns:**

```
# MAC stats (per DU)
mac stats → per-RNTI: DLSCH/ULSCH bytes, MCS, BLER, CQI, rounds, retx

# RRC stats (CU)
rrc stats → UE contexts, RNTI, state, associated DU

# Handover trigger (CU)
handover → triggers round-robin HO across DUs
handover <cu-ue-id> → triggers HO for specific UE
```

**Extractable KPIs per UE (per poll cycle):**
- MCS DL/UL (from MAC scheduler)
- CQI (UE-reported via MAC)
- BLER DL/UL (HARQ-based)
- Throughput DL/UL (bytes delta / time delta)
- PHR (MAC CE)
- HARQ rounds/retransmissions
- Current serving DU (from RRC context)

### 2. Docker API

**Polling interval:** ~5 seconds

**Monitored containers** (names from docker-compose):
- CN5G services: oai-amf, oai-smf, oai-upf, oai-nrf (+ others)
- RAN: oai-cu, oai-du0, oai-du1
- UE: oai-nr-ue
- External: oai-ext-dn

**Per container:** status (running/stopped/restarting), health check, uptime

### 3. Log Watcher (handover events)

**Source:** `docker logs --follow oai-cu`

**Patterns to detect:**

```python
# Handover request sent
r"\[NR_RRC\].*HandoverRequest.*RNTI\s+(0x[0-9a-fA-F]+).*target.*DU\s+(\d+)"

# Handover request acknowledged
r"\[NR_RRC\].*HandoverRequestAcknowledge.*RNTI\s+(0x[0-9a-fA-F]+)"

# RRC Reconfiguration complete (HO success)
r"\[NR_RRC\].*RRCReconfigurationComplete.*RNTI\s+(0x[0-9a-fA-F]+)"

# UE context release (cleanup after HO)
r"\[NR_RRC\].*UEContextRelease.*RNTI\s+(0x[0-9a-fA-F]+)"

# General NGAP/NAS messages for the message flow table
r"\[(NGAP|NAS)\].*"
```

**Handover duration:** timestamp(RRCReconfigurationComplete) - timestamp(HandoverRequest)

### 4. Config File Parser

**Topology-specific files to parse:**

The dashboard must not assume a single fixed OAI config layout. It should detect or be configured with the active topology and then parse the corresponding compose/config files.

### F1 handover topology: `f1`

Main files:

* RAN compose: `gnb-docker-compose.yaml`
* CU config: `conf-cu.conf`
* DU base config: `conf-du.conf`
* UE config: `conf-nr-ue.conf`

Containers:

* `oai-cu`
* `oai-du0`
* `oai-du1`
* `oai-nr-ue`
* Core containers from `oai-cn5g/docker-compose.yaml`, including `oai-amf`, `oai-smf`, `oai-upf`, `oai-nrf`, `oai-udr`, `oai-udm`, `oai-ausf`, `mysql`, and `oai-ext-dn`

Important notes:

* `oai-du0` and `oai-du1` both mount `conf-du.conf`.
* `oai-du1` has topology-specific overrides injected through `gnb-docker-compose.yaml` via `USE_ADDITIONAL_OPTIONS`, including DU ID, cell ID, PCI, SSB frequency, PointA, SSB bitmap, and local F1 address.
* CU telnet is available at `192.168.70.150:9090`.
* DU telnet is not enabled in the current F1 compose file.
* F1 handover trigger command is `ci trigger_f1_ho`.

### N2 monolithic topology: `n2-monolithic`

Main files:

* RAN compose: `experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml`
* Source gNB config: `experiments/n2_handover/topology_a_monolithic/conf-gnb0.conf`
* Target gNB config: `experiments/n2_handover/topology_a_monolithic/conf-gnb1.conf`
* Neighbour config: `experiments/n2_handover/topology_a_monolithic/neighbour-config.conf`
* UE config: `conf-nr-ue.conf`

Containers:

* `oai-gnb0`
* `oai-gnb1`
* `oai-nr-ue`
* Core containers from `oai-cn5g/docker-compose.yaml`

Important notes:

* `oai-gnb0` and `oai-gnb1` are full monolithic gNBs.
* Both gNBs expose telnet through their configured listen addresses.
* N2 handover trigger command is `ci trigger_n2_ho <target_pci>,<ue_rrc_id>`.

### N2 CU/DU topology: `n2-cu-du`

Main files:

* RAN compose: `experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml`
* Source CU config: `experiments/n2_handover/topology_b_cu_du/conf-cu0.conf`
* Source DU config: `experiments/n2_handover/topology_b_cu_du/conf-du0.conf`
* Target CU config: `experiments/n2_handover/topology_b_cu_du/conf-cu1.conf`
* Target DU config: `experiments/n2_handover/topology_b_cu_du/conf-du1.conf`
* Neighbour config: `experiments/n2_handover/topology_b_cu_du/neighbour-config.conf`
* UE config: `conf-nr-ue.conf`

Containers:

* `oai-cu0`
* `oai-du0`
* `oai-cu1`
* `oai-du1`
* `oai-nr-ue`
* Core containers from `oai-cn5g/docker-compose.yaml`

Important notes:

* This topology has two CU/DU pairs.
* Telnet endpoints are configured per CU/DU in the compose file.
* For N2 CU/DU, the source telnet endpoint should follow the same logic used by `scripts/trigger_handover.sh`.
* N2 handover trigger command is `ci trigger_n2_ho <target_pci>,<ue_rrc_id>`.

### Parser requirements

The config parser should return a normalized topology model regardless of topology type. At minimum, extract when available:

* topology name
* node type: CN, CU, DU, monolithic gNB, UE, oai-ext-dn
* container name
* IP address
* telnet host/port if enabled
* gNB ID
* DU ID
* gNB name
* NR cell ID
* physical cell ID
* PLMN: MCC, MNC, MNC length, S-NSSAI
* tracking area code
* band
* absoluteFrequencySSB
* dl_absoluteFrequencyPointA
* carrier bandwidth
* subcarrier spacing
* TDD pattern
* F1 / N2 / N3 addresses where present
* neighbour-cell configuration where present
* handover trigger command for the active topology
* Measurement configuration (A2/A3 events)

The parser must also inspect docker-compose `USE_ADDITIONAL_OPTIONS`, because some runtime values override or supplement the `.conf` files.


## Dashboard Pages

### Page 1: Overview

**Layout:** 3-column (sidebar | center topology | right message flow)

**Left sidebar:**
- Container status cards for: CN5G (grouped), CU, DU0, DU1, UE, oai-ext-dn
- Each card: name, status indicator (green/red/orange), Start/Stop/Restart buttons
- Handover trigger button (prominent, sends telnet command to CU)

**Center:**
- **Top bar:** DU count, UE count, aggregate DL throughput, aggregate UL throughput
- **Topology diagram (SVG):**
  - CN5G block (top) → CU block → DU0 / DU1 blocks → UE block
  - UE icon positioned at the DU it's currently attached to (from RRC stats)
  - Animated transition when UE moves between DUs during handover
  - Connection lines: N2/N3, F1, RFsim
  - Color coding: green=running, red=stopped, orange=starting
  - Per-UE: show IMSI, RNTI, DL/UL throughput inline

**Right panel:**
- **Handover Duration table** (top): IMSI, UE ID, Source DU, Target DU, Old RNTI, New RNTI, Duration (ms)
- **5G SA Message Flow** (bottom): scrolling table with TIME, Protocol, Message columns

### Page 2: gNB

**Top:** Status bar (CU status, DU0/DU1 status, aggregate throughput)

**Left half:**
- Configuration panel (read from .conf files)
  - Band, Bandwidth, MIMO config
  - TDD slot pattern (visual: D D D F U colored blocks)
  - Modulation order DL/UL
- Per-DU details table: PCI, ARFCN, frequency, gNB DU ID

**Right half:**
- Aggregate bitrate chart (Recharts, last 10 min)
- Attached UEs table: RNTI, IMSI, serving DU, RSSI, RSRP, CQI, throughput

**Bottom:** gNB logs viewer (raw docker logs, auto-scroll, filter by layer: MAC/RRC/NGAP)

### Page 3: UE

**Top row:** KPI summary cards (current value + min/max/avg):
- CQI, MCS DL, MCS UL, BLER DL, BLER UL, Bitrate DL, Bitrate UL, PHR, Serving DU

**Main area:** Time-series charts (Recharts, toggleable via card click):
- CQI over time
- MCS DL/UL over time (dual line)
- BLER DL/UL over time (dual line)
- Bitrate DL/UL over time (dual line)
- PHR over time

**Note on RFsim KPIs:** RSSI, RSRP, RSRQ, SINR, SNR are synthetic in RFsim mode (stable/near-ideal without channel model). Display them if available from telnet stats but label as "RFsim (synthetic)" and deprioritize visually. The primary KPIs are the MAC-layer ones listed above.

### Page 4: Handover (Mobility)

**Left:**
- Handover Configuration display (parsed from CU config):
  - Neighbour cell list per DU
  - A2/A3 measurement event parameters (threshold, offset, hysteresis, time-to-trigger)
- Handover trigger control:
  - Button: "Trigger Handover" → sends `echo "handover" | nc localhost 9090` to CU container
  - Optional: UE ID selector for multi-UE scenarios

**Center:**
- Topology diagram (same as Overview but larger, focused on RAN)
- Shows UE migration animation during HO

**Right:**
- **Handover Duration table:** all recorded HO events with timing
- **Handover event timeline:** vertical timeline showing:
  - HandoverRequest (source DU → target DU)
  - HandoverRequestAcknowledge
  - RRCReconfigurationComplete
  - Duration annotation
- **Per-DU KPI comparison:** side-by-side MCS/CQI/BLER charts showing the DU switch moment as a vertical marker

## Implementation Phases

> **Status note.** The phase plan below is the original design sequence and is kept for
> historical context. The delivered page structure has since been consolidated from seven
> tabs to three — Overview, Results (Runs and Campaigns), and Controls — so the separate
> UE, gNB, and Handover pages described in Phases 2 and 3 no longer exist as pages; their
> content moved into Overview and the merged run explorer, and the per-UE radio KPIs
> (CQI/MCS/BLER/PHR) were dropped because no telemetry path populates them. See
> `dashboard/README.md` for the current page inventory, topology detection, and state
> collection model.

### Phase 1: MVP — Data Pipeline + Overview Page
**Goal:** Get data flowing from testbed to browser.

1. FastAPI app skeleton with WebSocket endpoint
2. Docker monitor collector (container status)
3. Telnet poller collector (basic MAC stats from CU/DUs)
4. Config parser (read .conf files for topology info)
5. React app with Overview page:
   - Sidebar with container status cards (no controls yet, status only)
   - Top bar with DU/UE counts and throughput
   - Static topology SVG (no animation yet)
6. WebSocket hook connecting frontend to backend
7. `docker-compose.dashboard.yml` for backend + frontend

### Phase 2: KPI Charts + gNB Page
1. Full telnet stat parsing (all per-UE KPIs)
2. KPI history buffer (in-memory ring buffer, last 10 min)
3. UE page with KPI cards and time-series charts
4. gNB page with config display and bitrate chart
5. Attached UEs table

### Phase 3: Handover Monitoring
1. Log watcher for HO events
2. Handover duration calculation
3. Handover page with duration table and event timeline
4. Handover trigger button (REST → telnet)
5. Dynamic UE position on topology diagram
6. Message flow panel

### Phase 4: Polish
1. Container lifecycle controls (Start/Stop/Restart via Docker API)
2. Handover configuration display
3. Per-DU comparison charts with HO markers
4. Raw log viewer with layer filtering
5. JSON data export
6. UE migration animation on topology

## Design Direction

**Color palette:** Teal/cyan primary (#0097A7), dark sidebar (#1a1a2e), white content area, green/red/orange status indicators. Similar energy to OAIBOX but not a copy.

**Typography:** Inter for UI, JetBrains Mono for log viewers and technical values.

**Layout:** Dense but organized — this is a monitoring tool for researchers, not a consumer product. Maximize information density without clutter.

## Technical Notes

- **Telnet parsing is fragile:** OAI telnet output format varies between versions. The parser should be version-aware and fail gracefully with warnings rather than crashes.
- **Container names must match docker-compose:** The dashboard config should map container names from the testbed's docker-compose.yml.
- **RFsim UE as server:** In the handover setup, the UE runs as the RFsim server (important for the network topology and connection flow).
- **Startup order matters:** DU0 first, then UE connects, then DU1. The dashboard should handle partial-stack scenarios gracefully.
- **All data is ephemeral:** No persistent database for MVP. In-memory buffers for KPI history. JSON export for post-analysis.
