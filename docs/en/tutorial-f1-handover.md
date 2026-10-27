# F1 RFsim Handover Tutorial

> **Document type:** Tutorial
>
> **Required reading:** [F00](foundation-f00-docker-network-ownership.md), [F01](foundation-f01-functional-readiness-model.md), [F02](foundation-f02-dn-reachability.md), [F03](foundation-f03-rfsim-multicell-operations.md), [F04](foundation-f04-oai-config-enums-and-timing.md), and the [measurement pipeline guide](guide-measurement-pipeline.md)

This tutorial runs an intra-gNB F1 handover from DU0 to DU1 while measuring user-plane continuity with ping and UDP iperf.

## Topology

- CU: `oai-cu` at `192.168.70.150`
- source cell: `oai-du0`, PCI 0
- target cell: `oai-du1`, PCI 1
- UE: `oai-nr-ue`, PDU address `10.0.0.2`
- ping destination: `192.168.71.135`
- iperf destination: `192.168.70.135`

The CU controls both DUs, so the handover is triggered through the CU Telnet interface with `ci trigger_f1_ho`.

## Prerequisites

Run from the repository root. Docker, Docker Compose v2, SCTP support, `/dev/net/tun`, `nc`, and Python 3 must be available.

```bash
./scripts/preflight_check.sh f1
```

Warnings about Tailscale are informational unless the route to `192.168.70.150` is affected.

## Run a clean automated experiment

Stop any existing topology, then run the smoke experiment with iperf required:

```bash
./scripts/down.sh f1
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh f1
```

The script starts the core, CU, source DU, UE, and target DU in readiness-safe order. It then starts ping and iperf before sending the handover command.

A successful run prints its result directory, for example:

```text
results/runs/20260619_145515_f1_handover_smoke
```

## Verify the result

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "HO acknowledged|handover .* complete" "$RUN_DIR/docker_logs/cu.log"
```

Success requires:

- `status: pass`
- `handover_triggered: true`
- `ping_metrics_valid: true`
- `iperf_status: pass`
- CU log evidence that the handover completed

The validated June 19, 2026 reference run recorded 0% ping loss, about 202 ms estimated interruption, about 1.049 Mbps UDP throughput, and 0% UDP loss.

## Manual workflow

For interactive inspection:

```bash
./scripts/up.sh f1
./scripts/status.sh f1
./scripts/trigger_handover.sh f1
./scripts/status.sh f1
```

Query the CU directly when troubleshooting:

```bash
echo ue | nc -N 192.168.70.150 9090
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090
```

## Repeated experiments

Use topology resets when comparing independent cold-start trials:

```bash
RUNS=5 RESET_BETWEEN_RUNS=1 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh f1
```

The aggregate is written under `results/repeated/`. Without a reset, later F1 runs may start from a different serving DU than the first run.

## Cleanup

```bash
./scripts/down.sh f1
```

Use `--volumes` only when persisted core state should also be removed.
