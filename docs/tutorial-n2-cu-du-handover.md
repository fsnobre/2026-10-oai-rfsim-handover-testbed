# N2 CU/DU RFsim Handover Tutorial

> **Document type:** Tutorial
>
> **Required reading:** [N2 handover guide](guide-n2-handover.md) and the [measurement pipeline guide](guide-measurement-pipeline.md)

This tutorial runs an inter-gNB N2 handover between two split CU/DU gNBs while measuring user-plane continuity with ping and UDP iperf.

## Topology

- source CU: `oai-cu0` at `192.168.70.150`
- source DU: `oai-du0` at `192.168.70.171`, PCI 0
- target CU: `oai-cu1` at `192.168.70.155`
- target DU: `oai-du1` at `192.168.70.172`, PCI 1
- UE: `oai-nr-ue`, PDU address `10.0.0.2`
- AMF-mediated handover command: `ci trigger_n2_ho 1,1`
- ping destination: `192.168.71.135`
- iperf destination: `192.168.70.135`

The command is sent to source `oai-cu0`. The AMF coordinates handover to `oai-cu1`, and the UE performs contention-free random access through target `oai-du1`.

## Prerequisites

```bash
./scripts/preflight_check.sh n2-cu-du
```

Both CU/DU pairs must establish F1 before handover. The DUs connect to the UE RFsim server at `192.168.70.181:4043`.

## Run a clean automated experiment

```bash
./scripts/down.sh n2-cu-du
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-cu-du
```

A successful run prints a directory such as:

```text
results/runs/20260619_152628_n2_cu_du_smoke
```

## Verify the result

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-cu0.log"
rg "Handover Request Acknowledge|Handover triggered"   "$RUN_DIR/docker_logs/oai-cu1.log"
rg "CFRA procedure succeeded|in-sync|goodput"   "$RUN_DIR/docker_logs/oai-du1.log"
```

The target CU confirms N2 resource allocation and the target DU confirms successful target-cell random access plus post-handover traffic.

The validated June 19, 2026 reference run recorded 1.538% ping loss, about 209 ms estimated interruption, about 1.049 Mbps UDP throughput, and 0% UDP loss.

## Manual workflow

```bash
./scripts/up.sh n2-cu-du
./scripts/status.sh n2-cu-du
echo ue | nc -N 192.168.70.150 9090
./scripts/trigger_handover.sh n2-cu-du
./scripts/status.sh n2-cu-du
```

Override target PCI or UE RRC ID when the source CU reports different values:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-cu-du
```

## Repeated experiments

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

N2 repeated tests reset the complete topology before each trial by default so every run starts with the UE on `oai-du0`. Use `RESET_BETWEEN_RUNS=0` only if the experiment explicitly performs a reverse handover.

## Cleanup

```bash
./scripts/down.sh n2-cu-du
```
