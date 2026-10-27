# Documentation Map

Documents are named by purpose. Foundation documents also have stable IDs (`F00`, `F01`, and so on) so prerequisites can be referenced without encoding the dependency graph in every filename.

Foundation IDs are identifiers, not interchangeable difficulty levels. Do not renumber existing foundations when inserting a new document; assign the next unused ID.

## Foundations

| ID | Document | Required reading |
|---|---|---|
| F00 | [Docker network ownership](foundation-f00-docker-network-ownership.md) | None |
| F01 | [Functional readiness model](foundation-f01-functional-readiness-model.md) | None |
| F02 | [User-plane and DN reachability](foundation-f02-dn-reachability.md) | F00 |
| F03 | [RFsim multi-cell operating rules](foundation-f03-rfsim-multicell-operations.md) | F00 |
| F04 | [OAI configuration enums and radio timing](foundation-f04-oai-config-enums-and-timing.md) | None |

## Recommended reading paths

### F1 RFsim handover

`F00 → F01 → F02 → F03 → F04 →` [measurement pipeline](guide-measurement-pipeline.md) `→` [F1 tutorial](tutorial-f1-handover.md)

### N2 monolithic RFsim handover

`F00 → F01 → F02 → F03 → F04 →` [N2 guide](guide-n2-handover.md) `→` [measurement pipeline](guide-measurement-pipeline.md) `→` [monolithic tutorial](tutorial-n2-monolithic-handover.md)

### N2 CU/DU RFsim handover

`F00 → F01 → F02 → F03 → F04 →` [N2 guide](guide-n2-handover.md) `→` [measurement pipeline](guide-measurement-pipeline.md) `→` [CU/DU tutorial](tutorial-n2-cu-du-handover.md)

### USRP X310 with a COTS UE

`F00 → F01 → F04 →` [single-cell USRP guide](guide-usrp-x310-cots.md) `→` [distributed handover guide](guide-usrp-distributed-handover.md)

When an OTA run misbehaves, go to the OAI troubleshooting catalogue in the companion `cerise_nobre` repository (`oai/docs/oai_troubleshooting_testbed.md`) and grep it for the log string you are seeing. See [External references](#external-references) below.

## Guides and tutorials

- [Measurement pipeline and run lifecycle](guide-measurement-pipeline.md)
- [N2 handover testbed guide](guide-n2-handover.md)
- [USRP X310 + COTS UE guide](guide-usrp-x310-cots.md)
- [Distributed USRP handover guide](guide-usrp-distributed-handover.md)
- [F1 RFsim handover tutorial](tutorial-f1-handover.md)
- [N2 monolithic RFsim handover tutorial](tutorial-n2-monolithic-handover.md)
- [N2 CU/DU RFsim handover tutorial](tutorial-n2-cu-du-handover.md)

## Reports, records, and handoffs

These documents provide evidence or historical context. They are not sequential prerequisites unless another document explicitly lists them.

- [Baseline results](report-baseline-results.md)
- [F1 RFsim startup and readiness fix report](report-f1-rfsim-readiness-fix.md)
- [Repository evaluation: practices, standards, and UX](report-repository-evaluation.md)
- [SMF IPv4v6 DNN fix report](report-smf-ipv4v6-dnn-fix.md)
- [Development history](record-development-history.md)
- [Dashboard Phase 6 operator overview record](record-dashboard-phase6-overview.md)
- [xApp integration handoff](handoff-xapp-integration.md)
- [Evaluation remediation implementation handoff](handoff-evaluation-remediation.md)
- [Dashboard overview live handoff](handoff-dashboard-overview-live.md)
- [F1 smoke-test auth-failure handoff (resolved)](handoff-f1-smoke-auth-failure.md)

## External references

Cross-testbed OAI knowledge deliberately lives outside this repository, in the
companion `cerise_nobre` repo, under `oai/` (`github.com/fsnobre/cerise_nobre`,
cloned on the Mini PC at `../cerise_nobre`; it absorbed the former `cerise_oai` repo on
2026-10-26). Paths in the table below are relative to `oai/`. Keep general OAI/ORANSlice material there and testbed-specific
material here.

| Document | Purpose |
|---|---|
| `docs/oai_troubleshooting_testbed.md` | Recurring OTA failures indexed by OAI log string, with confirmed causes and discarded hypotheses. **Start here when a run misbehaves.** Extend it rather than re-deriving a diagnosis. |
| `docs/oai_gnb_yaml_testbed.md` | Authoritative gNB parameter values for this hardware |
| `docs/oai_gnb_yaml_general.md` | Vendor-neutral gNB parameter reference |
| `docs/nr_prb_frequency_reference.md` | PRB / bandwidth / ARFCN tables |
| `docs/oai_handover_{n2,xn,intra_gnb,ric}.md` | Handover flavours, including E2SM-RC IE mapping |
| `docs/oai_f1_split_*.md`, `docs/oai_oru_fronthaul_*.md` | F1 split and ORU fronthaul |
| `scripts/validate_gnb_yaml.py` | Static validator for gNB YAML/conf parameter coherence |
| `scripts/collect_*.sh` | Diagnostic collectors (gNB, CN, FlexRIC, workstation, FN990) |

## Specifications

- [Dashboard specification](spec-dashboard.md)

## Naming convention

```text
foundation-fNN-<topic>.md  Stable foundational concept or operating rule
guide-<topic>.md           Broad operational or conceptual guide
tutorial-<topic>.md        Goal-oriented executable procedure
spec-<topic>.md            Design specification
report-<topic>.md          Results, investigation, or validation report
record-<topic>.md          Historical record
handoff-<topic>.md         Context prepared for transfer to another effort
```

Every new guide or tutorial should declare its required reading near the top and link to the prerequisite documents directly.
