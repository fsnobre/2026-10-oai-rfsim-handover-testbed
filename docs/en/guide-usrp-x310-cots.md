# USRP X310 + COTS UE Guide

> **Document type:** Guide
>
> **Required reading:** [F00 — Docker network ownership](foundation-f00-docker-network-ownership.md), [F01 — Functional readiness model](foundation-f01-functional-readiness-model.md), and [F04 — OAI configuration enums and radio timing](foundation-f04-oai-config-enums-and-timing.md)

This guide covers the `usrp-cots` topology: a single monolithic OAI gNB driving a
**USRP X310** software-defined radio, with a **commercial off-the-shelf (COTS) phone**
attaching over the air as the UE. It is the real-RF counterpart to the rfsim handover
experiments — there is no rfsim, no channel model, and no `oai-nr-ue` container.

> Scope: this delivers single-cell gNB bring-up on the X310 and COTS-phone attach
> verification. Automated ping/iperf measurement from the handset is **not** included (it is
> manual on the phone for now). For multi-cell handover on real radios (F1 and N2,
> one radio per host), see the
> [USRP handover (distributed) guide](guide-usrp-distributed-handover.md) — this single-cell
> topology is its bring-up baseline.

Related: [Functional readiness model](foundation-f01-functional-readiness-model.md) ·
[Measurement pipeline](guide-measurement-pipeline.md).

---

## 1. Topology

```
            AMF / SMF / UPF (oai-cn5g, Docker bridge 192.168.70.0/26)
                              |
                       N2 (NGAP/SCTP)         host networking
                              |
                    gNB (container, --no rfsim)
                              |
                       USRP X310  (10GbE, 192.168.40.2)
                              |  ~~ over the air (band n78) ~~
                         COTS phone (programmable SIM)
```

- The gNB container runs with `network_mode: host` so it can drive the X310 over the
  host's 10GbE NIC, and still reaches the 5GC on the Docker bridge.
- The UE is a real handset; it must carry a SIM provisioned in the OAI subscriber DB.

---

## 2. Hardware setup

1. **10GbE link.** Connect the X310's 10GbE port (SFP+) to a host 10GbE NIC. Give the host
   NIC a static address on the same `/24` as the radio, e.g. host `192.168.40.1`, X310
   `192.168.40.2`.
2. **Jumbo frames + buffers** (required for X310 throughput; non-namespaced, set on the
   **host**, not in compose):
   ```bash
   sudo ip link set <10gbe-iface> mtu 9000
   sudo sysctl -w net.core.rmem_max=33554432
   sudo sysctl -w net.core.wmem_max=33554432
   ```
3. **RF front end.** Use band n78 (3.6 GHz) TX/RX ports with appropriate antennas or a
   cabled+attenuated path. Never transmit on licensed spectrum without authorization — use
   a shielded/cabled setup or a licensed test band.
4. **Clock/timing.** `clock_src`/`time_src = "internal"` works for a single cell. Use
   `"external"` (10 MHz + PPS) or `"gpsdo"` only if you have the reference fitted.
5. **Verify the device** before bring-up:
   ```bash
   ./scripts/check_usrp.sh
   ```
   This pings the radio and runs `uhd_usrp_probe` (inside the gNB image if UHD is not on the
   host).

---

## 3. SIM programming

The COTS phone needs a **programmable SIM** (e.g. sysmoUSIM) written with a subscriber that
exists in `oai-cn5g/database/oai_db.sql`. The DB already provisions IMSIs
`001010000000001`–`001010000000004`. Use the first one:

| Field | Value |
|---|---|
| IMSI | `001010000000001` |
| Ki (key) | `fec86ba6eb707ed08905757b1bb44b8f` |
| OPc | `C42449363BBAD02B66D16BC975D77CC1` |
| MCC / MNC | `001` / `01` |
| DNN/APN | `oai` |

Program with your SIM tool (e.g. `pySim`):

```bash
pySim-prog.py -p 0 -t sysmoISIM-SJA2 \
  --mcc 001 --mnc 01 \
  --imsi 001010000000001 \
  --ki fec86ba6eb707ed08905757b1bb44b8f \
  --opc C42449363BBAD02B66D16BC975D77CC1
```

On the phone, add an APN named `oai` and select PLMN `001/01` manually if it is not picked
automatically.

---

## 4. Configuration

- `experiments/usrp_x310/conf-gnb-usrp.conf` — monolithic gNB. Band n78, 106 PRB, 30 kHz
  SCS, TDD 7DL+2UL. The `RUs` block selects the radio (`sdr_addrs = "addr=192.168.40.2"`)
  and sets gains; there is **no** `rfsimulator`/`channelmod` block.
- `NETWORK_INTERFACES.GNB_IPV4_ADDRESS_FOR_NG_AMF`/`_FOR_NGU` default to `192.168.70.129`,
  the host's address on the `oai-cn5g-public-net` bridge. Confirm yours:
  ```bash
  docker network inspect oai-cn5g-public-net -f '{{(index .IPAM.Config 0).Gateway}}'
  ```
  and update the conf if it differs.
- `experiments/usrp_x310/gnb-docker-compose.yaml` — single `gnb` service, host networking,
  `memlock`/`rtprio` ulimits, no `--rfsim`. Tune gains at runtime via `USE_ADDITIONAL_OPTIONS`
  (e.g. `--RUs.[0].max_rxgain 105`).
- `experiments/usrp_x310/config.yaml` — radio/UE/SIM reference values.

---

## 5. Bring-up

```bash
./scripts/preflight_check.sh usrp-cots     # USRP-aware checks (device, buffers, UHD)
./scripts/up.sh usrp-cots                  # CN + gNB, waits for NG association to AMF
```

`up.sh` starts the 5GC, then the gNB, then waits for the NG (N2) association to the AMF. It
does **not** wait for a UE (the handset is external). Once it reports the gNB is associated,
power on the phone (or toggle airplane mode) so it scans and attaches.

Check status (auto-detects the topology):

```bash
./scripts/status.sh
```

In USRP mode this reports the gNB NG association and any UE registration events seen in the
AMF logs. "No UE attached yet" is informational, not a failure — attach is operator-driven.

Confirm attach directly in the AMF logs:

```bash
docker logs oai-amf 2>&1 | grep -iE 'Registration|5GMM-REGISTERED'
```

Then verify the data plane from the phone (browser / speed test / ping a public host).

Stop everything:

```bash
./scripts/down.sh                          # auto-detects usrp-cots
```

---

## 6. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `up.sh` never reaches NG association | gNB crashed on radio init | `docker logs oai-gnb`; check `check_usrp.sh`, gains, clock |
| `No LO lock` / `RuntimeError` in gNB log | clock/timing reference missing | set `clock_src/time_src = "internal"` unless a ref is fitted |
| Repeated `U`/`O`/`L` on the gNB console | USRP under/overflows | raise host buffers + MTU (§2); reduce host load; check 10GbE link |
| `uhd_usrp_probe` can't find device | 10GbE/IP/MTU issue | verify host NIC IP on the radio's `/24`, MTU 9000, cabling |
| Phone shows no service / cell not found | band/PLMN/gain | confirm band n78 support, PLMN 001/01, raise TX gain, check antenna path |
| Phone sees cell but won't register | SIM mismatch | re-check IMSI/Ki/OPc against `oai_db.sql`; check `docker logs oai-amf` |
| gNB up but AMF never associates | NG address not host-routable | set `GNB_IPV4_ADDRESS_FOR_NG_AMF` to the CN bridge gateway (§4) |

---

## 7. What this topology does not do

- No automated ping/iperf smoke test (`run_smoke_test.sh` targets the rfsim container UE).
  Measure from the handset manually for now.
- No handover (single cell). Handover over real radio needs multiple radios / COTS mobility.
- No OAI `oai-nr-ue` — the UE is a COTS handset by design.
