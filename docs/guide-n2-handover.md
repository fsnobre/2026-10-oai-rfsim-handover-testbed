# N2 Handover Testbed — User Guide

> **Document type:** Guide
>
> **Required reading:** [F00](foundation-f00-docker-network-ownership.md), [F01](foundation-f01-functional-readiness-model.md), [F02](foundation-f02-dn-reachability.md), [F03](foundation-f03-rfsim-multicell-operations.md), and [F04](foundation-f04-oai-config-enums-and-timing.md)

This guide covers everything needed to run N2 inter-gNB handover experiments using the OAI RFsimulator testbed. N2 handover requires OAI v2.4.0 or later.

---

## Table of Contents

1. [N2 vs F1 handover — key differences](#1-n2-vs-f1-handover--key-differences)
2. [Topology overview](#2-topology-overview)
3. [Prerequisites](#3-prerequisites)
4. [Configuration reference](#4-configuration-reference)
5. [Starting the 5GC](#5-starting-the-5gc)
6. [Topology A — two monolithic gNBs](#6-topology-a--two-monolithic-gnbs)
7. [Topology B — two CU+DU pairs](#7-topology-b--two-cudu-pairs)
8. [Triggering N2 handover manually](#8-triggering-n2-handover-manually)
9. [Automated smoke test](#9-automated-smoke-test)
10. [Repeated experiments](#10-repeated-experiments)
11. [Reading results](#11-reading-results)
12. [Stopping the stack](#12-stopping-the-stack)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. N2 vs F1 handover — key differences

| | F1 handover | N2 handover |
|---|---|---|
| Scope | Intra-gNB (one CU, two DUs) | Inter-gNB (two independent gNBs) |
| Mediator | CU moves the UE between its own DUs | AMF mediates the transfer between gNBs |
| Interface used | F1-C | N2 (NGAP) |
| Trigger | `ci trigger_f1_ho` on CU Telnet | `ci trigger_n2_ho <pci>,<rrc_id>` on source gNB Telnet |
| OAI minimum version | v2.3.0 | v2.4.0 |
| Measurement reporting | Not needed (manual trigger) | Not needed (manual trigger) |

In both cases the UE acts as the **rfsim server** so that multiple gNBs can connect to the same UE instance.

---

## 2. Topology overview

### Topology A — two monolithic gNBs

```
                     AMF (192.168.70.132)
                    /                    \
           N2 (NGAP)                      N2 (NGAP)
                  /                          \
    oai-gnb0 (192.168.70.160)          oai-gnb1 (192.168.70.161)
    PCI=0  gNB_ID=0xe00            PCI=1  gNB_ID=0xe01
    Telnet :9090                   Telnet :9090
                  \                          /
                   rfsim client    rfsim client
                          \        /
                      oai-nr-ue (192.168.70.181)
                      rfsim server :4043
```

Handover is triggered from **oai-gnb0 Telnet**, targeting oai-gnb1 (PCI=1).

### Topology B — two CU+DU pairs

```
                     AMF (192.168.70.132)
                    /                    \
           N2 (NGAP)                      N2 (NGAP)
                  /                          \
    oai-cu0 (192.168.70.150)           oai-cu1 (192.168.70.155)
    Telnet :9090                   gNB_ID=0xe01
    gNB_ID=0xe00                          |
           |                           F1-C/F1-U
        F1-C/F1-U                         |
           |                       oai-du1 (192.168.70.172)
    oai-du0 (192.168.70.171)           rfsim client
    rfsim client                          |
           \                             /
            -------- oai-nr-ue (192.168.70.181) --------
                     rfsim server :4043
```

Handover is triggered from **oai-cu0 Telnet**, targeting the cell served by oai-cu1/oai-du1 (PCI=1).

---

## 3. Prerequisites

- Docker and Docker Compose v2 installed. The OAI CN Compose stack creates
  and owns `oai-cn5g-public-net` and `oai-ext-dn-traffic-net`; do not create
  them manually. See [Docker network ownership](foundation-f00-docker-network-ownership.md).
- `nc` (netcat) installed on the host (used to send Telnet commands)
- `python3` installed on the host (used by ping parser and result aggregation)
- OAI images pulled:
  ```bash
  docker pull oaisoftwarealliance/oai-gnb:v2.4.0
  docker pull oaisoftwarealliance/oai-nr-ue:v2.4.0
  ```
- 5GC images already present (pulled with `docker compose pull` in `oai-cn5g/`)

> **Tailscale warning:** If Tailscale is active, the `nc` command used to trigger handover can fail. Run `sudo tailscale down` before triggering, or use the script which will warn you automatically.

---

## 4. Configuration reference

All N2 experiment defaults live in `experiments/n2_handover/config.yaml`. Edit this file to change ping targets, handover parameters, or topology defaults.

### Key parameters

| Parameter | Default | Description |
|---|---|---|
| `source_gnb_ip` | `192.168.70.160` | Telnet IP of the source gNB (oai-gnb0 / oai-cu0) |
| `source_gnb_port` | `9090` | Telnet port |
| `target_pci` | `1` | PCI of the target gNB cell |
| `ue_rrc_id` | `1` | RRC ID of the UE at the source gNB |
| `ping.target` | `192.168.71.135` | Ping target (local oai-ext-dn) |
| `ping.interface` | `oaitun_ue1` | UE PDU session interface |
| `ping.interval_seconds` | `0.2` | Ping interval during capture |
| `ping.post_handover_seconds` | `10` | How long to keep capturing after handover |
| `iperf.enabled` | `false` | Enable concurrent iperf measurement |
| `iperf.target` | `192.168.70.135` | oai-ext-dn public-side iperf target |
| `iperf.mode` | `udp` | `udp` or `tcp` |
| `iperf.duration_seconds` | `10` | iperf measurement duration |

### Environment variable overrides

All scripts read these environment variables, which take precedence over `config.yaml`:

| Variable | Used by | Purpose |
|---|---|---|
| `N2_SOURCE_GNB_TELNET_HOST` | trigger script | Override source gNB Telnet IP |
| `N2_SOURCE_GNB_TELNET_PORT` | trigger script | Override source gNB Telnet port |
| `N2_TARGET_PCI` | trigger script | Override target PCI |
| `N2_UE_RRC_ID` | trigger script | Override UE RRC ID |
| `PING_TARGET` | smoke test | Override ping target |
| `PING_INTERFACE` | smoke test | Override ping interface |
| `PING_INTERVAL` | smoke test | Override ping interval |
| `PING_POST_HANDOVER_SECONDS` | smoke test | Override post-handover capture duration |
| `IPERF_ENABLED` | smoke/repeated test | Enable concurrent iperf (`1`, `true`, `yes`, or `on`) |
| `IPERF_REQUIRED` | smoke/repeated test | Fail the run if iperf does not complete |
| `IPERF_TARGET` | smoke/repeated test | Override iperf target |
| `IPERF_MODE` | smoke/repeated test | Select `udp` or `tcp` |
| `IPERF_DURATION` | smoke/repeated test | Override iperf duration in seconds |
| `IPERF_INTERFACE` | standalone iperf | Override UE source interface |
| `UE_DATA_READY_TIMEOUT` | smoke test | Seconds to wait for UE data plane (default 120) |
| `RUNS` | repeated test | Number of runs (default 5) |
| `RESET_BETWEEN_RUNS` | repeated test | Reset before each run; defaults on for N2 |

---

## 5. Starting the testbed

`up.sh` starts the 5GC and the selected RAN topology in one command. If the 5GC is already running it will re-use it.

```bash
./scripts/up.sh n2-monolithic   # Topology A
./scripts/up.sh n2-cu-du        # Topology B
```

`up.sh` runs `preflight_check.sh` automatically and blocks until `oai-nr-ue` is running, then runs `poststart_check.sh`.

---

## 6. Topology A — two monolithic gNBs

### Start

```bash
./scripts/up.sh n2-monolithic
```

Startup order is enforced by `depends_on`: `oai-nr-ue` starts first, then `oai-gnb0` and `oai-gnb1` in parallel.

### Verify containers are running

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-gnb0|oai-gnb1"
```

### Check that oai-gnb0 Telnet is reachable

```bash
nc -z -w 3 192.168.70.160 9090 && echo "reachable" || echo "not reachable"
```

### Check that oai-gnb1 Telnet is reachable

```bash
nc -z -w 3 192.168.70.161 9090 && echo "reachable" || echo "not reachable"
```

### Watch oai-gnb0 logs

```bash
docker logs -f oai-gnb0
```

Look for `Received NGAP INITIAL_CONTEXT_SETUP_REQUEST` to confirm the UE has attached to oai-gnb0.

---

## 7. Topology B — two CU+DU pairs

### Start

```bash
./scripts/up.sh n2-cu-du
```

Startup order: `oai-nr-ue` → `oai-cu0` → `oai-du0` → `oai-cu1` → `oai-du1`.

### Verify containers are running

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-cu0|oai-du0|oai-cu1|oai-du1"
```

### Check oai-cu0 Telnet (used to trigger handover)

```bash
nc -z -w 3 192.168.70.150 9090 && echo "reachable" || echo "not reachable"
```

### Watch oai-cu0 logs

```bash
docker logs -f oai-cu0
```

---

## 8. Triggering N2 handover manually

### What the command does

The trigger command sends `ci trigger_n2_ho <target_pci>,<ue_rrc_id>` to the source gNB's Telnet interface. The source gNB initiates the N2 handover procedure with the AMF, which coordinates the transfer to the target gNB.

### Via the trigger script (recommended)

The script reads defaults from `config.yaml`, warns about Tailscale, checks port reachability, and appends events to `RUN_DIR` if set. With no argument it auto-detects the running topology.

```bash
./scripts/trigger_handover.sh                     # auto-detect
./scripts/trigger_handover.sh n2-monolithic       # explicit
./scripts/trigger_handover.sh n2-cu-du            # topology B (source is cu0)
```

### Manually with nc

Topology A — trigger from oai-gnb0, target oai-gnb1 (PCI=1, UE RRC ID=1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090 && echo
```

Topology B — trigger from oai-cu0, target oai-cu1/oai-du1 (PCI=1, UE RRC ID=1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.150 9090 && echo
```

### Expected output

The `nc` command prints the gNB Telnet response, which typically includes a line like:

```
RRC N2 handover triggered for UE 1
```

After triggering, watch the source and target gNB logs to see the NGAP Handover Required / Handover Request / Handover Command sequence.

### Finding the UE's RRC ID

If the UE RRC ID is not 1 (e.g. after a re-attach), query the source gNB Telnet:

```bash
echo "ue" | nc -N 192.168.70.160 9090
```

The response lists connected UEs with their RRC IDs.

---

## 9. Automated smoke test

The smoke test automates the full workflow: start 5GC and RAN (if not already running), wait for UE data-plane readiness, capture ping metrics, optionally run iperf concurrently, trigger handover, parse results, and write a summary.

```bash
./scripts/run_smoke_test.sh n2-monolithic   # Topology A
./scripts/run_smoke_test.sh n2-cu-du        # Topology B
```

Enable optional UDP or TCP iperf across the handover:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh n2-monolithic
IPERF_ENABLED=1 IPERF_MODE=tcp ./scripts/run_smoke_test.sh n2-cu-du
```

iperf failures are recorded without invalidating otherwise valid ping results unless `IPERF_REQUIRED=1` is set.

### What it does, step by step

1. Creates a timestamped run directory under `results/runs/` (e.g. `20260604_120000_n2_monolithic_smoke`)
2. Runs `preflight_check.sh`
3. Checks if the testbed is already running via `status.sh`; starts it via `up.sh` if not
4. Waits up to 120 s for the UE data plane to reach `192.168.71.135` via `oaitun_ue1`
5. Runs a 2-packet ping precheck to confirm connectivity
6. Starts a continuous timestamped ping capture in the background
7. If enabled, starts iperf bound to the UE PDU address on `oaitun_ue1`
8. Waits 3 s, then calls `trigger_handover.sh`
9. Keeps ping running for the configured post-handover duration
10. Waits for iperf, parses ping, and stores both metric sets
11. Collects container logs with `collect_logs.sh`
12. Writes `summary.json`
13. Prints the run directory path on success

### Override example — longer post-handover capture

```bash
PING_POST_HANDOVER_SECONDS=30 ./scripts/run_smoke_test.sh n2-monolithic
```

---

## 10. Repeated experiments

Run multiple back-to-back smoke tests and get aggregated statistics:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

N2 repeated runs reset the topology before each trial by default. This returns the UE to the source cell before the next same-direction handover. Set `RESET_BETWEEN_RUNS=0` only when the experiment provides another source-cell reset mechanism.

Enable iperf in every run:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

### Output

A timestamped directory is created under `results/repeated/` (e.g. `20260604_120000_n2_monolithic_repeated`) containing:

| File | Contents |
|---|---|
| `runs.txt` | Paths to each individual run directory |
| `run_1.log` … `run_N.log` | Full stdout/stderr of each smoke test |
| `summary.csv` | Per-run metrics in tabular form |
| `summary.json` | Aggregated statistics across all runs |

The `summary.json` includes mean, min, max, and std for ping metrics and available iperf throughput, jitter, loss, and retransmission metrics. It also includes `iperf_status_counts`.

---

## 11. Reading results

### Run directory layout

```
results/runs/20260604_120000_n2_monolithic_smoke/
  events.csv          — timestamped event log (precheck, handover trigger, etc.)
  ping_raw.log        — raw ping output from oai-nr-ue
  ping_precheck_raw.log — precheck ping output (separate from capture)
  ping.csv            — parsed per-packet RTT samples
  ping_summary.json   — parsed metrics
  summary.json        — overall smoke test result
  ping_target.txt     — which IP was pinged
  ping_interface.txt  — which interface was used
  iperf_raw.json      — iperf3 JSON output when enabled
  iperf_summary.json  — parsed throughput/jitter/loss metrics when enabled
  iperf_command.txt   — exact client command and UE source binding
  iperf_server.log    — oai-ext-dn iperf server output
  docker_ps.txt       — container state at collection time
  host_info.txt       — host metadata
```

### Key metrics in `ping_summary.json`

```json
{
  "packets_transmitted": 64,
  "packets_received": 63,
  "packet_loss_percent": 1.56,
  "rtt_min_ms": 4.2,
  "rtt_avg_ms": 8.7,
  "rtt_max_ms": 312.4,
  "estimated_interruption_ms": 207.1,
  "first_ping_after_handover_ms": 93.3,
  "ping_metrics_valid": true
}
```

- **`estimated_interruption_ms`** — gap between last ping before and first ping after handover, derived from the `handover_trigger_start` event timestamp.
- **`first_ping_after_handover_ms`** — RTT of the first successful reply received after the trigger event.

### Key fields in `summary.json`

```json
{
  "status": "pass",
  "handover_triggered": true,
  "ue_data_ready": true,
  "ping_precheck_passed": true,
  "ping_metrics_valid": true,
  "estimated_interruption_ms": 207.1,
  "iperf_status": "pass",
  "iperf_protocol": "UDP",
  "iperf_mbps": 1.05,
  "iperf_jitter_ms": 7.08,
  "iperf_lost_percent": 0.0
}
```

`status` is `"pass"` only if the UE data plane was ready, ping ran successfully across the handover, and the parser found valid samples. Optional iperf failure is represented by `iperf_status: "failed"`; it becomes run-fatal only with `IPERF_REQUIRED=1`.

### Viewing the events timeline

```bash
cat results/runs/<run_id>/events.csv
```

Key events include ping precheck/capture, optional `iperf_server_start`, `iperf_client_start`, and `iperf_client_end`, the handover trigger events, and `ping_capture_stop`.

---

## 12. Stopping the stack

### Stop the N2 RAN only

Topology A:

```bash
docker compose \
  -f experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml \
  down
```

Topology B:

```bash
docker compose \
  -f experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml \
  down
```

### Stop the 5GC

```bash
cd oai-cn5g && docker compose down && cd ..
```

> Do **not** pass `--volumes` unless you want to wipe the subscriber database. Wiping the database requires re-inserting the UE IMSI before the next run.

### Stop everything at once

```bash
cd oai-cn5g && docker compose down && cd ..
docker compose \
  -f experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml \
  down 2>/dev/null || true
docker compose \
  -f experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml \
  down 2>/dev/null || true
```

---

## 13. Troubleshooting

### UE does not attach to oai-gnb0

Check that the AMF is healthy before oai-gnb0 tries to register:

```bash
docker logs oai-amf | grep "UE Context"
docker logs oai-gnb0 | grep -i "ngap\|ng setup\|error"
```

The AMF must complete NG Setup with both gNBs before the UE can attach.

### Handover trigger returns no output or an error

1. Confirm the source gNB Telnet port is reachable:
   ```bash
   nc -z -w 3 192.168.70.160 9090 && echo ok
   ```
2. Check that the UE is connected to the source gNB with RRC ID 1:
   ```bash
   echo "ue" | nc -N 192.168.70.160 9090
   ```
3. If Tailscale is active, take it down:
   ```bash
   sudo tailscale down
   ```

### Handover triggers but UE loses connectivity permanently

The target gNB may not have completed NG Setup with the AMF. Check:

```bash
docker logs oai-gnb1 | grep "NG Setup"   # topology A
docker logs oai-cu1  | grep "NG Setup"   # topology B
```

Both gNBs must show a successful NG Setup before triggering handover.

### Ping capture shows `packets_transmitted: 2`

This indicates the precheck ping output contaminated `ping_raw.log`. This was a known bug that has been fixed — the precheck now writes to `ping_precheck_raw.log`. If you see this in an old run directory it is a pre-fix artifact.

### Smoke test fails at UE data-plane readiness

The UE PDU session may not be established yet. Increase the timeout:

```bash
UE_DATA_READY_TIMEOUT=240 ./scripts/run_smoke_test.sh n2-monolithic
```

Also verify the UE has an IP on `oaitun_ue1`:

```bash
docker exec oai-nr-ue ip addr show oaitun_ue1
```

Expected output: `inet 10.0.0.2/24`.

### Topology B: oai-du0 or oai-du1 fails to connect to its CU

Confirm the CU F1 listen address matches the compose IP:

- `oai-cu0` listens on `192.168.70.150` — oai-du0 connects to that address
- `oai-cu1` listens on `192.168.70.155` — oai-du1 connects to that address

The `--gNBs.[0].remote_s_address 0.0.0.0` option in each CU's `USE_ADDITIONAL_OPTIONS` tells the CU to accept connections from any DU address.

### Container exits immediately

Check for image pull issues or capability problems:

```bash
docker logs oai-gnb0
docker inspect oai-gnb0 --format '{{.State.ExitCode}}'
```

A missing `NET_ADMIN` capability on the oai-nr-ue will prevent `oaitun_ue1` from being created.
