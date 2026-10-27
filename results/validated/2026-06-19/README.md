# Validated Three-Topology Experiment Set

Date: June 19, 2026

These are single-run, cold-start reference experiments for the three supported RFsim handover topologies. They validate the automation and provide reproducible examples; they are not a statistically representative performance baseline.

All runs used:

```text
IPERF_ENABLED=1
IPERF_REQUIRED=1
IPERF_MODE=udp
IPERF_DURATION=10
PING_INTERVAL=0.2
PING_POST_HANDOVER_SECONDS=10
```

## Results

| Topology | Run ID | Ping loss | Estimated interruption | First ping after trigger | UDP throughput | UDP jitter | UDP loss |
|---|---|---:|---:|---:|---:|---:|---:|
| F1 CU + 2 DUs | `20260619_145515_f1_handover_smoke` | 0.000% | 202.072 ms | 20.664 ms | 1.049 Mbps | 5.932 ms | 0.000% |
| N2 monolithic | `20260619_152343_n2_monolithic_smoke` | 1.538% | 198.860 ms | 0.145 ms | 1.049 Mbps | 7.154 ms | 0.000% |
| N2 CU/DU | `20260619_152628_n2_cu_du_smoke` | 1.538% | 208.574 ms | 77.762 ms | 1.049 Mbps | 7.725 ms | 0.000% |

Every run passed required ping and iperf validation. The iperf client was bound to the UE PDU address on `oaitun_ue1`.

## Handover evidence

- F1: the CU reported handover acknowledgement, RRC reconfiguration completion, and `handover ... complete`.
- N2 monolithic: `gnb0` sent Handover Required and received the NG Handover Command; `gnb1` acknowledged the request, completed CFRA, and carried in-sync traffic.
- N2 CU/DU: `cu0` sent Handover Required and received the NG Handover Command; `cu1` acknowledged target allocation; `du1` completed CFRA and carried in-sync traffic.

## Preserved artifacts

Each topology directory contains:

- `summary.json`: overall smoke and metric result
- `ping_summary.json`: parsed ping metrics
- `iperf_summary.json`: parsed UDP metrics
- `events.csv`: experiment timeline

Full raw logs remain under the ignored local `results/runs/<run-id>/` directories. The preserved files intentionally omit host-specific bulk logs.

## Interpretation

The similar interruption values are useful as a functional reference, but no ranking should be inferred from one run per topology. A comparative performance study should use repeated cold-start trials, fixed host load, image digests, and confidence intervals.
