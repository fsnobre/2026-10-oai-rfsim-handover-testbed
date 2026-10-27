# OAI RFsim Handover Testbed

This repository contains a research-grade automation harness for OpenAirInterface handover experiments. It supports two RFsimulator handover experiments:

| Experiment | Topology | Trigger | OAI version |
|---|---|---|---|
| F1 handover | 1 CU + 2 DUs (intra-gNB) | CU Telnet `ci trigger_f1_ho` | v2.4.0 |
| N2 handover | 2 monolithic gNBs **or** 2 CU+DU pairs (inter-gNB) | Source gNB Telnet `ci trigger_n2_ho` | v2.4.0 |

The handover experiments share the same OAI 5GC (AMF, SMF, UPF, oai-ext-dn) and the same RFsim UE.

Real-radio (USRP X310) topologies are also provided, with a COTS phone as the UE:

| Experiment | Topology | Radios | UE |
|---|---|---|---|
| USRP single cell | 1 monolithic gNB (`usrp-cots`) | 1 × X310 | COTS phone |
| USRP F1 handover | 1 CU + 2 DUs (distributed) | 2 × X310 | COTS phone |
| USRP N2 handover | 2 gNBs **or** 2 CU+DU pairs (distributed) | 2 × X310 | COTS phone |

The handover topologies run **one radio per host**. See the
[USRP X310 + COTS UE guide](docs/guide-usrp-x310-cots.md) (single cell) and the
[USRP handover (distributed) guide](docs/guide-usrp-distributed-handover.md).

---

## F1 Handover Experiment

### Topology

- 1 OAI 5GC (AMF, SMF, UPF, oai-ext-dn)
- 1 static UPF
- 1 CU (`192.168.70.150`)
- 2 DUs (`192.168.70.171`, `192.168.70.172`)
- 1 RFsim UE (`192.168.70.181`)
- Manual F1 handover triggered through the CU Telnet interface

Container names: `oai-amf`, `oai-smf`, `oai-upf`, `oai-cu`, `oai-du0`, `oai-du1`, `oai-nr-ue`

### Baseline

5-run repeated smoke test against local `oai-ext-dn` (`192.168.71.135`) via `oaitun_ue1`. All 5 runs passed with 0.0% packet loss and a mean estimated handover interruption of **207.07 ms**.

See [docs/report-baseline-results.md](docs/report-baseline-results.md) for the full results and interpretation.

### Usage

Start the testbed:

```bash
./scripts/up.sh f1
```

Check readiness:

```bash
./scripts/status.sh
```

Trigger F1 handover manually:

```bash
./scripts/trigger_handover.sh
```

Run the smoke test (starts stack, captures ping across handover, writes results):

```bash
./scripts/run_smoke_test.sh f1
```

Enable concurrent iperf measurement across the handover:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh f1
```

By default, iperf targets the oai-ext-dn public-side address `192.168.70.135`, binds to the UE PDU address, and records failures without invalidating valid ping and handover results. Make it mandatory with `IPERF_REQUIRED=1`.

Run 5 repeated smoke tests and aggregate results:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh f1
```

Enable and aggregate iperf for every repeated run:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh f1
```

Fallback to internet target if local DN reachability is being investigated:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh f1
```

Override the UE data-plane readiness timeout:

```bash
UE_DATA_READY_TIMEOUT=180 ./scripts/run_smoke_test.sh f1
```

---

## N2 Handover Experiment

**Full guide: [docs/guide-n2-handover.md](docs/guide-n2-handover.md)**

N2 handover (inter-gNB, AMF-mediated) is available in OAI v2.4.0+. Two topologies are provided:

- **`n2-monolithic` — two standalone gNBs** (`oai-gnb0` at `192.168.70.160`, `oai-gnb1` at `192.168.70.161`)
- **`n2-cu-du` — two CU+DU pairs** (`oai-cu0`/`oai-du0` and `oai-cu1`/`oai-du1`)

The UE (`192.168.70.181`) acts as the RFsim server in both cases.

### Quick start

```bash
./scripts/up.sh n2-monolithic          # or n2-cu-du
./scripts/trigger_handover.sh          # auto-detects topology from running containers
```

### Automated smoke test

```bash
./scripts/run_smoke_test.sh n2-monolithic
./scripts/run_smoke_test.sh n2-cu-du
```

### Repeated experiments

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

Repeated N2 runs reset the topology before each trial by default so every same-direction handover starts from the source cell. Override only with `RESET_BETWEEN_RUNS=0`.

---

## USRP X310 Experiment (real radio)

**Full guide: [docs/guide-usrp-x310-cots.md](docs/guide-usrp-x310-cots.md)**

A single monolithic gNB drives a USRP X310 over 10GbE; a COTS phone with a programmed SIM attaches over the air. There is no rfsim, no channel model, and no `oai-nr-ue` container.

### Quick start

```bash
./scripts/check_usrp.sh                 # probe the X310 (ping + uhd_usrp_probe)
./scripts/preflight_check.sh usrp-cots  # USRP-aware preflight
./scripts/up.sh usrp-cots               # CN + gNB, waits for NG association to the AMF
./scripts/status.sh                     # gNB NG association + UE registration (from AMF logs)
```

Then power on the COTS UE (SIM programmed from `oai-cn5g/database/oai_db.sql`) so it attaches. Data-plane measurement from the handset is manual (browser/speed test); automated smoke tests are rfsim-only.

The X310 needs host-side jumbo frames and large socket buffers (`mtu 9000`, `net.core.rmem_max/wmem_max`) — see the guide.

---

## USRP X310 Handover (distributed, real radio)

**Full guide: [docs/guide-usrp-distributed-handover.md](docs/guide-usrp-distributed-handover.md)**

The three handover topologies (F1, N2 monolithic, N2 CU/DU) on real X310 radios, **one radio per host**. Each DU/gNB runs on its own host with host networking; CUs are radio-less; configs live under `experiments/usrp_handover/`. Inter-node addresses are injected per host from a `.env`.

```bash
# Core host: make the 5GC reachable from RAN hosts (no CN changes)
sudo ./scripts/usrp_core_routing.sh <core-host-lan-ip>

# Each RAN host: copy the topology .env.example to .env, set LAN IPs, then:
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0    # e.g. on the gnb0 host

# Trigger from a control host pointing at the source node's LAN IP:
N2_SOURCE_GNB_TELNET_HOST=<gnb0-lan-ip> ./scripts/trigger_handover.sh n2-monolithic
```

---

## Common Operations

### Layer Compose overlays onto the RAN stack

`RAN_COMPOSE_OVERLAY` adds extra Compose files after the topology's RAN compose file, so an external experiment can override service settings without editing this repository's compose files:

```bash
RAN_COMPOSE_OVERLAY=/path/to/overlay.yml ./scripts/up.sh f1
```

Use a colon-separated list for several overlays; they are applied left to right, so later files win:

```bash
RAN_COMPOSE_OVERLAY=/path/a.yml:/path/b.yml ./scripts/up.sh f1
```

The variable is honoured by every script that sources `scripts/lib.sh`, including `up.sh`, `down.sh`, and `preflight_check.sh`. **Pass the same value to `down.sh` that you passed to `up.sh`** so the stack is torn down against the same merged configuration. A missing overlay path fails immediately with exit code 2. The base compose file always stays first, so the Compose project directory and project name are unchanged and relative paths inside the base file still resolve.

Typical use is adding softmodem options or mounting an alternate config. Note that `USE_ADDITIONAL_OPTIONS` is replaced wholesale, not merged, so an overlay must repeat the options it wants to keep:

```yaml
services:
    du0:
        environment:
            USE_ADDITIONAL_OPTIONS: --rfsim
                                    --log_config.global_log_options level,nocolor,time
                                    --rfsimulator.[0].serveraddr 192.168.70.181
                                    --rfsimulator.[0].options chanmod
```

Bring-up ordering still matters and is why `up.sh` should be used rather than a bare `docker compose up -d`: the UE runs as the RFsim server and cannot be restarted in place while the DUs keep running, or it never re-establishes a data plane.

### Stop the testbed

Auto-detects the running topology:

```bash
./scripts/down.sh
```

Or specify the topology explicitly:

```bash
./scripts/down.sh f1
./scripts/down.sh n2-monolithic
./scripts/down.sh n2-cu-du
./scripts/down.sh usrp-cots
```

Pass `--volumes` to also wipe Compose-managed volumes (destructive — removes the subscriber database):

```bash
./scripts/down.sh --volumes
```

### Collect logs

```bash
./scripts/collect_logs.sh
./scripts/collect_logs.sh --run-dir results/runs/<run_id>
```

### DN reachability diagnostics

```bash
./scripts/diagnose_dn_reachability.sh
```

Writes Docker network state, routes, ping probes, firewall rules, and a summary under `results/diagnostics/`. Does not modify any configuration.

Documentation:

- [Documentation map and required reading paths](docs/README.md)
- [F1 handover tutorial](docs/tutorial-f1-handover.md)
- [N2 monolithic handover tutorial](docs/tutorial-n2-monolithic-handover.md)
- [N2 CU/DU handover tutorial](docs/tutorial-n2-cu-du-handover.md)
- [USRP X310 + COTS UE guide](docs/guide-usrp-x310-cots.md)
- [USRP handover (distributed) guide](docs/guide-usrp-distributed-handover.md)
- [Validated three-topology experiment set](results/validated/2026-06-19/README.md)

### Optional standalone iperf3 measurement

Check support:

```bash
./scripts/check_iperf_support.sh
```

Run a UDP test from `oai-nr-ue` to `oai-ext-dn`:

```bash
IPERF_MODE=udp IPERF_DURATION=10 ./scripts/run_iperf_test.sh
```

---

## Known failure modes and interventions

Run `./scripts/preflight_check.sh` before starting — it automatically detects the issues listed below and reports `[PASS]`, `[WARN]`, or `[FAIL]` for each one. Run `./scripts/poststart_check.sh` after starting to verify the testbed is healthy.

To skip the preflight in one-off situations where you know the environment is good:

```bash
SKIP_PREFLIGHT=1 ./scripts/up.sh
```

### Issue reference

| Failure | Symptom | Intervention |
|---|---|---|
| **Tailscale exit node without LAN access**, *or* **route via tailscale0** | `nc/Telnet` to 192.168.70.x fails | `sudo tailscale set --exit-node-allow-lan-access=true`, disable exit node, or `sudo tailscale down` |
| **WireGuard active** | Traffic to 192.168.70.x misdirected | Disconnect WireGuard (`wg-quick down <iface>`) |
| **OpenVPN / other TUN VPN** | Same as WireGuard | Disconnect VPN |
| **Stale containers** | Container name already in use on start | `docker rm -f <names>` |
| **CN Docker network missing** | Preflight reports that Compose will create it | Run `./scripts/up.sh`; do not create shared networks manually |
| **CN Docker network incompatible** | Preflight reports wrong subnet or ownership | Stop attached containers, remove the incompatible network, then rerun `./scripts/up.sh` |
| **Subnet conflict** | Traffic silently misdirected | Remove/reconfigure conflicting interface or route |
| **/dev/net/tun missing** | `oaitun_ue1` never appears; data-plane timeout | `sudo modprobe tun` |
| **SCTP not loaded** | AMF NG Setup never completes | `sudo modprobe sctp` |
| **Port 9090 or 4043 held** | Telnet unreachable / rfsim won't connect | Kill holding process or `docker rm -f` zombie container |
| **iptables FORWARD DROP** | UE cannot reach oai-ext-dn | Check FORWARD chain; ensure Docker rules are not overridden |
| **AppArmor blocking NET_ADMIN** | `oaitun_ue1` absent, no error visible | Check `dmesg \| grep apparmor`; adjust profile |
| **Clock out of sync** | NAS authentication failures | `sudo systemctl restart systemd-timesyncd` |
| **Images not pulled** | Slow start or pull failure on first run | `docker pull oaisoftwarealliance/oai-gnb:develop && docker pull oaisoftwarealliance/oai-nr-ue:develop` |
| **Low disk space** | Log collection or result writes silently fail | Clean old runs from `results/runs/` and `results/repeated/` |

---

## Repository Layout

```
experiments/
  manual_f1_handover/        F1 handover experiment config
  n2_handover/               N2 handover experiment config
    config.yaml
    topology_a_monolithic/   Two monolithic gNBs
    topology_b_cu_du/        Two CU+DU pairs
  usrp_x310/                 USRP X310 real-radio gNB, single cell (COTS UE)
    config.yaml
    conf-gnb-usrp.conf
    gnb-docker-compose.yaml
  usrp_handover/             USRP X310 handover, distributed (one radio per host)
    f1/                      CU + 2 DUs (per-host compose, confs, .env.example)
    n2_monolithic/           2 gNBs
    n2_cu_du/                2 CU+DU pairs
scripts/
  up.sh / down.sh / restart.sh / status.sh  (accept topology: f1, n2-monolithic, n2-cu-du, usrp-cots)
  wait_ready.sh / wait_ue_data_ready.sh
  trigger_handover.sh        Handover trigger (all topologies; auto-detects if no arg)
  run_smoke_test.sh          Smoke test (all topologies)
  run_repeated_smoke_tests.sh
  preflight_check.sh / poststart_check.sh
  start_ping_capture.sh / collect_logs.sh
  run_iperf_test.sh / check_iperf_support.sh
  check_usrp.sh              USRP X310 device probe (ping + uhd_usrp_probe)
  usrp_core_routing.sh       Make the 5GC reachable from distributed RAN hosts
  usrp_site_up.sh / usrp_site_down.sh  Per-host launcher for distributed USRP roles
  diagnose_dn_reachability.sh
  lib.sh                     Shared helpers (apply_topology, detect_topology, ...)
conf-cu.conf                 F1 CU configuration
conf-du.conf                 F1 DU base configuration
conf-nr-ue.conf              UE configuration (shared by all experiments)
oai-cn5g/                   5GC Docker Compose and configuration
tools/
  parse_ping.py
  parse_iperf.py
docs/
  README.md                  Reading paths and documentation index
  foundation-fNN-*.md       Stable foundational concepts and rules
  guide-*.md                Broad operational guides
  tutorial-*.md             Goal-oriented procedures
  report-*.md               Results and validation reports
  record-*.md               Historical records
  handoff-*.md              Cross-effort context documents
results/
  runs/                      Per-run results
  repeated/                  Aggregated repeated-run results
  diagnostics/               DN reachability diagnostic runs
```

---

## Scope

This repository covers:

- Static UPF placement
- RFsimulator operation (single host, no RF hardware) for the handover experiments
- USRP X310 real-radio operation with a COTS UE (single cell, and distributed F1/N2 handover — one radio per host)
- F1 intra-gNB handover (CU/DU split)
- N2 inter-gNB handover (monolithic and CU+DU topologies)
- Automated readiness checks, ping/iperf measurement, log collection, and result aggregation

Automated measurement from a COTS UE, handover over real radio, DRL, GNN, and xApp integration are planned for future milestones.
