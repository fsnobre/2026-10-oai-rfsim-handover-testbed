# Baseline Results

> **Document type:** Report
>
> **Context:** [F1 RFsim handover tutorial](tutorial-f1-handover.md) and [measurement pipeline guide](guide-measurement-pipeline.md)

This document records the original validated ping-only baseline for the OAI RFsimulator F1 handover automation harness. It predates integrated iperf measurement; its published numbers remain unchanged for comparability.

## Experiment Topology

- 1 RFsim UE: `oai-nr-ue`
- 2 DUs: `oai-du0`, `oai-du1`
- 1 CU: `oai-cu`
- 1 OAI 5GC control plane
- 1 static UPF: `oai-upf`
- 1 local data network endpoint: `oai-ext-dn`

The local data-plane target is `oai-ext-dn` at `192.168.71.135`. The UE sends measurement traffic through the PDU session interface `oaitun_ue1`.

## Startup And Handover Workflow

The testbed is started with the automation harness:

```bash
./scripts/up.sh
```

The startup workflow waits for core, CU, DU, and UE readiness before smoke tests run. The smoke test then waits for UE data-plane reachability to the configured ping target.

The validated handover trigger remains the manual CU Telnet command:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

The smoke test sends this command through:

```bash
./scripts/trigger_handover.sh
```

## Measurement Method

The baseline uses ICMP ping as the handover continuity probe. iperf was not enabled for these five historical runs:

- target: `192.168.71.135`
- target container: `oai-ext-dn`
- UE interface: `oaitun_ue1`
- repeated experiment count: `RUNS=5`
- handover method: manual CU Telnet command `ci trigger_f1_ho`

For each run, ping starts before handover, continues during handover, and remains active briefly after handover. The parser estimates interruption from ping reply timing around the handover trigger event.

## Repeated-Run Results

| Runs | Passed | Packet Loss | Mean Interruption | Std Interruption | Min Interruption | Max Interruption | Mean First Ping After Handover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 5 | 0.0% | 207.0664 ms | 22.3375 ms | 170.576 ms | 238.949 ms | 93.309 ms |

## Aggregate Summary

- Repeated experiment: `RUNS=5`
- Successful runs: `5/5`
- Packet loss: `0.0%`
- Mean estimated interruption: `207.0664 ms`
- Standard deviation of estimated interruption: `22.3375 ms`
- Minimum estimated interruption: `170.576 ms`
- Maximum estimated interruption: `238.949 ms`
- Mean first ping after handover: `93.309 ms`

## Current Interpretation

The baseline confirms that the automation harness can repeatedly start and validate the RFsim F1 handover testbed, trigger handover through the CU Telnet interface, and preserve UE data-plane connectivity to the local `oai-ext-dn` target with no packet loss across five runs.

The measured interruption is currently on the order of hundreds of milliseconds. This gives a practical baseline for future changes to compare against, especially when adding richer mobility-control logic or more controlled measurement paths.

## Current iperf capability

New smoke and repeated runs can add concurrent iperf using `IPERF_ENABLED=1`. Those results include throughput, jitter, UDP loss, or TCP retransmissions, but they are not part of the historical table above. A new multi-run iperf baseline should be recorded separately rather than retroactively changing this dataset.

## Known Limitation

RTT samples still include OAI RFsim timing effects, Docker/container scheduling, host scheduling, and transient processing spikes. The current ping-based baseline is useful for smoke and early research comparison, but it should not yet be treated as a clean radio-protocol latency measurement.
