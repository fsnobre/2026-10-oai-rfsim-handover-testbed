# Handoff: `fsnobre/oai-rfsim-handover-testbed`

> **Document type:** Handoff
>
> **Required reading:** [N2 handover guide](guide-n2-handover.md), [baseline results](report-baseline-results.md), and [development history](record-development-history.md)

> Context document for the artigo_doc_1 research chat. Written so that a session
> with no access to this repository can reason about integrating the
> artigo_doc_1 handover method into this testbed as an xApp.

## What this repo is

A research-grade, fully containerized OAI (OpenAirInterface) 5G SA handover
testbed. The handover experiments run on RFsimulator — single host, no radio
hardware, everything in Docker Compose (there is also an optional USRP X310
real-radio path with a COTS UE; the xApp work below targets the RFsim flow). It
automates handover experiments end-to-end:
stack bring-up, readiness gating, handover triggering, ping-based interruption
measurement, optional concurrent TCP/UDP iperf, log collection, and repeated-run
statistical aggregation. Its
stated roadmap (README) is: **"DRL, GNN, and xApp integration are planned for
future milestones"** — it was built to eventually host exactly the kind of
method we are developing.

## Supported experiments

| Experiment | Topology | Trigger mechanism | OAI version |
|---|---|---|---|
| F1 handover (intra-gNB) | 1 CU + 2 DUs | CU Telnet: `ci trigger_f1_ho` | v2.4.0 / develop |
| N2 handover (inter-gNB) | 2 monolithic gNBs (`oai-gnb0`/`oai-gnb1`) **or** 2 CU+DU pairs | Source gNB Telnet: `ci trigger_n2_ho <target_pci>,<ue_rrc_id>` | v2.4.0 |

All share one OAI 5GC (AMF/SMF/UPF/oai-ext-dn, images on `develop`) and one RFsim
UE. **The UE is the rfsim server** (port 4043) so multiple gNBs can connect to
the same UE — this is required for handover in rfsim, since the OAI rfsim UE
cannot trigger handover via measurement reporting; handover is always
triggered manually/programmatically via gNB telnet.

## Network layout (Docker bridge `oai-cn5g-public-net`, 192.168.70.128/26)

- AMF `192.168.70.132`, oai-ext-dn ping target `192.168.71.135`
- F1: CU `.150`, oai-du0 `.171`, oai-du1 `.172`
- N2 monolithic: oai-gnb0 `.160` (PCI 0, gNB_ID 0xe00), oai-gnb1 `.161` (PCI 1, 0xe01), telnet on `:9090`
- N2 CU+DU: oai-cu0 `.150`, oai-cu1 `.155`, oai-du0 `.171`, oai-du1 `.172`
- UE `oai-nr-ue` `.181`, PDU session interface `oaitun_ue1`, IP `10.0.0.2`, UE telnet `:8091` (`ciUE` module)
- Band 78, 106 PRB, 30 kHz SCS; oai-gnb0 SSB ARFCN 641280, oai-gnb1 643296; neighbour relations declared via `neighbour-config.conf` included in each gNB conf

## Key operational interfaces (actuation/observation primitives)

- **Trigger handover:** `./scripts/trigger_handover.sh` (auto-detects topology) or raw: `echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090`
- **Query connected UEs + RRC IDs:** `echo "ue" | nc -N <gnb_ip> 9090`
- **Channel models:** configuration blocks for `rfsimu_channel_ue0/ue1` are present, but runtime `chanmod` command-line activation is disabled for the currently validated image because that option is rejected. Re-enable channel-model control only after validating the option syntax against the selected OAI image.
- **Lifecycle:** `./scripts/up.sh {f1|n2-monolithic|n2-cu-du}`, `down.sh`, `status.sh`, `preflight_check.sh` / `poststart_check.sh`
- **Experiments:** `./scripts/run_smoke_test.sh <topology>`, `RUNS=5 ./scripts/run_repeated_smoke_tests.sh <topology>`; defaults in `experiments/n2_handover/config.yaml`, all overridable via env vars (`N2_TARGET_PCI`, `N2_UE_RRC_ID`, `PING_TARGET`, `IPERF_ENABLED`, `IPERF_MODE`, etc.)

## Measurement pipeline & baseline

Each run produces a timestamped dir under `results/runs/` with `events.csv`
(timeline incl. `n2_handover_trigger_start`), `ping.csv`, `ping_summary.json`
(`estimated_interruption_ms`, `first_ping_after_handover_ms`, loss, RTT
stats), optional `iperf_summary.json` (throughput, jitter, UDP loss, TCP
retransmits), `summary.json` (pass/fail), and full container logs. Repeated runs
aggregate ping and available iperf metrics under `results/repeated/`. **Validated F1
baseline: 207.07 ms mean interruption, 0.0% loss across 5 runs**
(`docs/en/report-baseline-results.md`).

## What it does NOT have (gaps for xApp work)

1. **No RIC, no E2, no xApp layer.** No FlexRIC/OSC RIC, no `e2_agent` block
   in any gNB conf, no E2SM service models. The HO trigger is OAI's
   proprietary telnet CI shim, not E2SM-RC.
2. **Stock images** (`oaisoftwarealliance/oai-gnb:develop`/`v2.4.0`) — must
   verify they include the E2 agent (mainline OAI builds it with
   `--build-e2`); worst case is one image rebuild. OAI publishes an official
   `oai-flexric` image for the RIC side.
3. **No measurement reporting to a controller** — observation today is
   telnet/log scraping; a real xApp needs E2SM-KPM or FlexRIC custom SMs
   (MAC/RLC/PDCP) for per-UE features.
4. **Single UE**, and the UE-as-rfsim-server pattern does not generalize to
   many-UE × many-gNB — the biggest structural constraint if the method needs
   multi-UE state (relevant for GNN approaches).

## Agreed integration assessment

Verdict: **usable as the future xApp testbed** — it solves environment +
actuation + measurement rigor; only the RIC layer must be added (2–3
containers on the existing Docker network + conf changes). Recommended phased
path, targeting the **N2 monolithic** topology (two clean E2 nodes, inter-gNB
HO is what an O-RAN HO xApp semantically controls):

- **Phase 0 (no E2):** run the artigo_doc_1 method as an "xApp-like"
  controller container on the same network — observe via
  telnet/logs/channelmod, actuate via the existing `trigger_n2_ho` telnet
  primitive. Validates the decision logic end-to-end immediately, reusing the
  whole measurement harness and the existing baseline as the comparison point.
- **Phase 1:** add FlexRIC + `e2_agent = { near_ric_ip_addr = ...; sm_dir = ... }`
  in gNB confs; method becomes a real xApp consuming E2SM-KPM/custom-SM
  indications; keep telnet actuation as bridge.
- **Phase 2:** move actuation to E2SM-RC handover control (least mature piece
  in OAI/FlexRIC — verify before any paper claims depend on it; OSC Near-RT
  RIC is the heavier standards-conformant alternative).

Two risks to scope before committing the method to this testbed: the
**multi-UE rfsim constraint** and **E2SM-RC HO-control maturity** in the
pinned OAI version.

## Repo map (most relevant files)

```
experiments/n2_handover/config.yaml          # N2 experiment defaults (PCIs, telnet IPs, ping params)
experiments/n2_handover/topology_a_monolithic/   # gnb0/gnb1 confs + compose + neighbour-config
experiments/n2_handover/topology_b_cu_du/        # cu0/cu1/du0/du1 confs + compose
gnb-docker-compose.yaml                      # F1 topology (CU + 2 DU + UE)
oai-cn5g/                                    # 5GC compose + conf + subscriber DB
scripts/trigger_handover.sh, run_smoke_test.sh, run_repeated_smoke_tests.sh, lib.sh
tools/parse_ping.py                          # interruption-time computation
docs/en/guide-n2-handover.md, report-baseline-results.md, record-development-history.md
```

## Notes for the receiving chat

- Treat the **Phase 0 controller** as the first concrete integration
  deliverable.
- Determine early whether the artigo_doc_1 method requires **multi-UE
  observations** — that is the one constraint here that cannot be fixed with
  configuration alone.
