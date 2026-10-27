# N2 Monolithic RFsim Handover Tutorial

> **Document type:** Tutorial
>
> **Required reading:** [N2 handover guide](guide-n2-handover.md) and the [measurement pipeline guide](guide-measurement-pipeline.md)

This tutorial runs an inter-gNB N2 handover between two monolithic gNBs while ping and UDP iperf cross the handover interval.

## Topology

- source gNB: `oai-gnb0` at `192.168.70.160`, PCI 0
- target gNB: `oai-gnb1` at `192.168.70.161`, PCI 1
- UE: `oai-nr-ue`, PDU address `10.0.0.2`
- AMF-mediated handover command: `ci trigger_n2_ho 1,1`
- ping destination: `192.168.71.135`
- iperf destination: `192.168.70.135`

Each gNB contains its CU and DU functions. Both gNBs register independently with the AMF.

## Prerequisites

Run from the repository root:

```bash
./scripts/preflight_check.sh n2-monolithic
```

The current topology depends on the repository RFsim compatibility settings: the UE is the RFsim server, both gNBs connect to `192.168.70.181:4043`, and the random-access response window is configured for RFsim timing.

## Run a clean automated experiment

```bash
./scripts/down.sh n2-monolithic
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-monolithic
```

The script waits for the UE PDU session, starts ping and iperf, then sends the N2 trigger to `oai-gnb0`.

A successful run prints a directory such as:

```text
results/runs/20260619_152343_n2_monolithic_smoke
```

## Verify the result

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-gnb0.log"
rg "Handover Request Acknowledge|CFRA procedure succeeded|in-sync"   "$RUN_DIR/docker_logs/oai-gnb1.log"
```

The target `oai-gnb1` log should show target context allocation, successful contention-free random access, and in-sync traffic after handover. This is stronger evidence than command submission alone.

The validated June 19, 2026 reference run recorded 1.538% ping loss, about 199 ms estimated interruption, about 1.049 Mbps UDP throughput, and 0% UDP loss.

## Manual workflow

```bash
./scripts/up.sh n2-monolithic
./scripts/status.sh n2-monolithic
echo ue | nc -N 192.168.70.160 9090
./scripts/trigger_handover.sh n2-monolithic
./scripts/status.sh n2-monolithic
```

The default trigger assumes target PCI 1 and source RRC UE ID 1. Override them when needed:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-monolithic
```

## Repeated experiments

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

N2 repeated tests reset the topology before each run by default. This is necessary because every configured trigger moves the UE from the source gNB to the target gNB. Set `RESET_BETWEEN_RUNS=0` only when another mechanism returns the UE to the source cell.

## Cleanup

```bash
./scripts/down.sh n2-monolithic
```
