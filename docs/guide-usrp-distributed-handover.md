# USRP X310 Handover Testbeds (distributed, COTS UE)

> **Document type:** Guide
>
> **Required reading:** [USRP X310 + COTS UE guide](guide-usrp-x310-cots.md), [F01 — Functional readiness model](foundation-f01-functional-readiness-model.md), and [F04 — OAI configuration enums and radio timing](foundation-f04-oai-config-enums-and-timing.md)

This guide covers running the three handover topologies on **real USRP X310 radios**,
mirroring the rfsim set:

| Topology dir | Handover | Nodes (one radio per host) | Trigger |
|---|---|---|---|
| `f1/` | Intra-gNB (F1) | 1 CU (radio-less) + DU0 + DU1 (one X310 each) | CU Telnet `ci trigger_f1_ho` |
| `n2_monolithic/` | Inter-gNB (N2) | gnb0 + gnb1 (one X310 each) | gnb0 Telnet `ci trigger_n2_ho` |
| `n2_cu_du/` | Inter-gNB (N2) | cu0 + du0 (site 0), cu1 + du1 (site 1) | cu0 Telnet `ci trigger_n2_ho` |

Files live under `experiments/usrp_handover/`. The UE is a **COTS phone** (SIM programming
and radio bring-up are in the [USRP X310 + COTS UE guide](guide-usrp-x310-cots.md)).

> On real RF the rfsim "UE-as-server" trick is gone — **each cell needs its own radio**.
> Deployment is **one radio per host**: each DU/gNB runs on its own host with one X310 on a
> dedicated 10GbE link; CUs are radio-less; the 5GC runs on its own host. The single-cell
> `usrp-cots` topology is the bring-up baseline; this is the multi-cell handover extension.

---

## 1. How distributed differs from the rfsim set

The rfsim topologies are single-host: all containers share one Docker bridge
(`192.168.70.0/26`) and address each other by container name. Here, each node is on a
**different host**, so F1, N2/NG, and N3 traverse the **real LAN**:

- Every node runs with `network_mode: host` and drives its local X310.
- All inter-node addresses are **injected at runtime from a per-host `.env`** into the
  container's `USE_ADDITIONAL_OPTIONS` (the conf files hold only radio/cell parameters and
  placeholders). This reuses the override idiom already used by the rfsim composes.
- There is no single `docker compose up`: you start one role per host with
  `scripts/usrp_site_up.sh`.

---

## 2. IP planning

Pick LAN IPs for every host and the radios, then copy `.env.example` to `.env` in the
topology directory **on each host** and fill them in. Example for `n2_cu_du`:

| Variable | Meaning | Example |
|---|---|---|
| `CORE_HOST_IP` | Core host LAN IP (route gateway for the CN subnet) | `192.168.1.10` |
| `AMF_N2_IP` | AMF address on the CN bridge (RAN connects here) | `192.168.70.132` |
| `CU0_HOST_IP` / `CU1_HOST_IP` | CU host LAN IPs (F1 listen + NG + Telnet) | `192.168.1.20/.25` |
| `DU0_HOST_IP` / `DU1_HOST_IP` | DU host LAN IPs (F1) | `192.168.1.30/.40` |
| `DU0_SDR_ADDR` / `DU1_SDR_ADDR` | each X310 on its host's 10GbE link | `192.168.40.2` |

The radios use their own dedicated `/24` per host (e.g. `192.168.40.0/24`), separate from
the inter-host LAN.

---

## 3. Make the 5GC reachable from RAN hosts

The 5GC stays on its Docker bridge (no CN changes). Host-networking the AMF/UPF is **not**
used because the NFs share SBI port 8080 and resolve each other on the bridge — that would
break the SBI mesh. Instead, route the CN subnet over the LAN.

On the **core host** (once):

```bash
sudo ./scripts/usrp_core_routing.sh <core-host-lan-ip>
```

This enables IPv4 forwarding and allows `192.168.70.128/26` through the FORWARD chain, then
prints the route command for the RAN hosts. On **each RAN host**:

```bash
sudo ip route add 192.168.70.128/26 via <core-host-lan-ip>
ping -c1 192.168.70.132   # AMF reachable?
ping -c1 192.168.70.134   # UPF (N3) reachable?
```

The gNBs/CUs use `amf_ip_address = AMF_N2_IP` (the AMF bridge IP) and the SMF hands them the
UPF N3 address (`192.168.70.134`) — both reachable once the route is in place.

---

## 4. SIM and radios

- Program the COTS SIM and verify each X310 per the
  [USRP X310 + COTS UE guide](guide-usrp-x310-cots.md) (`./scripts/check_usrp.sh` on each
  radio host; set `SDR_ADDR` to that host's radio).
- Host-side jumbo frames + socket buffers are required on every radio host (see that guide).

---

## 5. Bring-up

Start the 5GC on the core host (existing flow), set up routing (§3), then start each role on
its host. `usrp_site_up.sh` starts the role and waits for local readiness (and NG
association for CU/gNB roles).

**F1** (3 RAN hosts):
```bash
# CU host
./scripts/usrp_site_up.sh f1 cu
# DU0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du0
# DU1 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du1
```

**N2 monolithic** (2 RAN hosts):
```bash
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0   # gnb0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb1   # gnb1 host
```

**N2 CU/DU** (4 RAN hosts):
```bash
./scripts/usrp_site_up.sh n2-cu-du cu0                            # cu0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du0          # du0 host
./scripts/usrp_site_up.sh n2-cu-du cu1                            # cu1 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du1          # du1 host
```

Confirm NG association on the core host: `docker logs oai-amf 2>&1 | grep -i NGSetup`.
Then power on the COTS UE so it attaches to the source cell.

---

## 6. Triggering the handover

Run from any host that can reach the source node's Telnet (e.g. the core/control host),
pointing the existing trigger at the source node's LAN IP:

**F1** (source = CU):
```bash
CU_TELNET_HOST=<CU_HOST_IP> ./scripts/trigger_handover.sh f1
```

**N2 monolithic** (source = gnb0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<GNB0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-monolithic
```

**N2 CU/DU** (source = cu0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<CU0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-cu-du
```

`N2_UE_RRC_ID` is the UE's RRC id at the source node (usually `1` for a single UE; read it
from the source log if unsure). The phone also emits real measurement reports, so the
network may trigger handover on its own once neighbours are configured.

---

## 7. Verifying the handover

- **Source/target logs**: source shows Handover Required / (F1) handover command; target
  shows the UE admitted and CFRA/RA completing.
- **Core host**: `docker logs oai-amf` shows the path switch (N2) for inter-gNB.
- **Phone**: data session continuity (an ongoing download/ping keeps running across the
  switch). Measurement from the handset is manual.

Stop a role on its host:
```bash
./scripts/usrp_site_down.sh <topology> <role>
```

---

## 8. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| gNB/CU never NG-associates | RAN host can't reach the AMF | check `usrp_core_routing.sh` ran; `ping 192.168.70.132` from the RAN host; firewall |
| DU never connects to CU | F1 addresses / LAN routing | confirm `DUx_HOST_IP`/`CUx_HOST_IP`, both hosts on the LAN, SCTP allowed |
| UE attaches but no data | UPF N3 unreachable from the DU/gNB host | `ping 192.168.70.134`; check the route and FORWARD rules |
| Handover never fires | neighbour/PCI/RRC-id wrong | verify `neighbour-config.conf`, target PCI (1), and `N2_UE_RRC_ID` from the source log |
| Radio under/overflows (U/O/L) | 10GbE buffers/MTU | apply host buffers + MTU 9000 (see the COTS guide) |
| Phone sees only one cell | gains/antenna/band | raise TX gain on the weak cell; confirm both cells on band n78 |

---

## 9. Out of scope

- Single-host multi-radio layout (this guide assumes one radio per host).
- Automated ping/iperf from the COTS UE (manual for now).
- OAI nr-ue on a dedicated radio as the UE.
