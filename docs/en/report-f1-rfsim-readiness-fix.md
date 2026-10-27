# F1 RFsim Startup and Readiness Fix Report

> **Document type:** Report
>
> **Context:** [F01 — Functional readiness model](foundation-f01-functional-readiness-model.md), [F03 — RFsim multi-cell operating rules](foundation-f03-rfsim-multicell-operations.md), and [F04 — OAI configuration enums and radio timing](foundation-f04-oai-config-enums-and-timing.md)

**Date:** June 19, 2026
**Scope:** F1 intra-gNB handover topology
**Status:** Implemented and validated end-to-end

## Executive summary

The F1 testbed previously reported `SUMMARY: PASS` whenever the containers were
running and the CU Telnet port was reachable. That did not prove that the UE had
synchronized with a cell, established an RRC connection, registered with the
5GC, or created a PDU session.

The observed failure had four related causes:

1. Both DUs were configured to connect to RFsim at `127.0.0.1:4043`. Inside a
   DU container, that address refers to the DU itself, not the UE RFsim server.
2. DU1 bound its F1 interface to `127.0.0.1`, preventing a valid container-to-CU
   F1 association.
3. The UE was initially exposed to both RFsim transmitters before it completed
   attachment to DU0, making initial synchronization unreliable.
4. The configured random-access response window was too short for the observed
   RFsim scheduling delay. The DU detected PRACH but rejected Msg2 scheduling
   because it was one slot outside the permitted window.

The fix corrects RFsim and F1 addressing, increases the random-access response
window, stages DU startup so that the UE attaches through DU0 before DU1 starts,
and makes UE data-plane readiness a mandatory startup and status condition.

The final validation demonstrated:

- both DUs connected to the UE RFsim server;
- both DUs completed F1 setup with the CU;
- the UE established an RRC connection and PDU session;
- `oaitun_ue1` received `10.0.0.2`;
- the UE reached `192.168.71.135` through `oaitun_ue1`;
- F1 handover from PCI 0 to PCI 1 completed successfully; and
- UE data-plane connectivity remained available after handover.

## Initial symptoms

After `scripts/up.sh` completed, the post-start check reported:

```text
[WARN] oaitun_ue1 not yet present — UE has not established a PDU session
[WARN] UE cannot reach 192.168.71.135 via oaitun_ue1
```

At the same time, `scripts/status.sh` reported all containers as running, the CU
Telnet endpoint as reachable, and:

```text
SUMMARY: PASS
```

Attempting an F1 handover produced:

```text
no single UE in RRC present
```

These results were internally inconsistent only because the existing status
definition measured process availability rather than functional readiness.

## Diagnostic findings

### 1. The UE never reached the CU or AMF

The AMF showed the CU/gNB as connected but its UE table was empty. The CU also
reported that it could not find a UE in RRC.

The UE log repeatedly showed:

```text
synch Failed
```

This established that the initial fault was below NAS and the 5GC. Subscriber
credentials, DNN configuration, and PDU-session configuration were not yet in
the execution path.

### 2. Both DUs connected to their own loopback address

The DU logs repeatedly showed:

```text
Trying to connect to 127.0.0.1:4043
connect() to 127.0.0.1:4043 failed, errno(111)
```

The UE is the RFsim server and listens on port `4043` at
`192.168.70.181`. Therefore the DUs must use that container address. Docker
container loopback addresses are namespace-local and cannot refer to another
container.

The explicit loopback override also took precedence over the correct
`serveraddr = "192.168.70.181"` value in `conf-du.conf`.

### 3. DU1 used loopback for F1

DU1 was started with:

```text
--MACRLCs.[0].local_n_address 127.0.0.1
```

Its logs showed repeated SCTP failures:

```text
Connect failed: Network is unreachable
```

The correct DU1 F1 address is its Docker network address,
`192.168.70.172`.

### 4. Starting both DUs before attachment disrupted initial synchronization

After correcting RFsim connectivity, both DUs successfully connected to the UE
RFsim server. However, starting DU1 before the UE attached to DU0 caused repeated
PBCH and SIB1 decoding failures.

Stopping DU1 allowed the UE to:

- decode PBCH;
- synchronize to PCI 0; and
- decode SIB1.

This confirmed that initial registration needed to complete on the source cell
before enabling the target cell.

### 5. Random access exceeded the configured response window

With only DU0 active, the DU detected every UE PRACH transmission, but logged:

```text
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
```

The response arrived after 11 slots while the configured window allowed 10.

`ra_ResponseWindow` is represented as an enum index in the OAI configuration,
not as a literal slot count. The relevant mapping is:

| Configuration value | Window |
|---:|---:|
| `4` | 10 slots |
| `5` | 20 slots |

An intermediate test using literal value `8` was rejected by the OAI RACH
encoder. Setting the value to `5` selected the next valid 20-slot window and
allowed random access to complete.

## Implemented changes

### Docker and radio configuration

#### `gnb-docker-compose.yaml`

Both DUs now explicitly connect to the UE RFsim server:

```yaml
--rfsimulator.[0].serveraddr 192.168.70.181
```

DU1 now binds F1 to its actual Docker network address:

```yaml
--MACRLCs.[0].local_n_address 192.168.70.172
```

Explicit RFsim addressing is retained even though `conf-du.conf` contains the
same address. Testing showed that the `--rfsim` command-line option initializes
the client endpoint to `127.0.0.1` in this OAI image, so relying only on the
configuration-file value is unsafe.

#### `conf-du.conf`

The random-access response-window enum was changed:

```text
ra_ResponseWindow = 4;
```

to:

```text
ra_ResponseWindow = 5;
```

This changes the effective window from 10 slots to 20 slots.

### Startup sequencing and readiness

#### `scripts/up.sh`

F1 startup now follows this sequence:

1. Run topology-aware preflight checks.
2. Start OAI CN.
3. Verify that Compose created both required Docker networks with the expected
   subnet and ownership.
4. Start the CU.
5. Start the UE and DU0.
6. Wait until the UE establishes its PDU session and reaches the external data
   network.
7. Start DU1.
8. Verify that DU1 and the UE remain stable.
9. Recheck UE data-plane connectivity.
10. Report startup success.

The key behavioral change is that startup cannot succeed merely because
`nr-uesoftmodem` is running.

### Shared readiness helpers

#### `scripts/lib.sh`

The following helpers were added:

- `core_docker_network_specs`
- `docker_network_exists`
- `validate_core_docker_network`
- `ue_data_interface_ip`
- `ue_data_plane_reachable`

They centralize network ownership validation and UE data-plane checks so that
preflight, startup, and status use consistent definitions.

### Status semantics

#### `scripts/status.sh`

`SUMMARY: PASS` now requires:

- all critical containers to exist and run;
- the CU or source gNB Telnet endpoint to be reachable;
- `oaitun_ue1` to exist and have an IPv4 address; and
- the configured data-network target to be reachable through the configured UE
  interface.

For the validated F1 run, status reported:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

### Handover error propagation

#### `scripts/trigger_handover.sh`

The script now captures the CU Telnet response and returns a nonzero exit code
when the CU reports that no eligible UE exists in RRC. Previously it printed the
error but still completed successfully from the shell's perspective.

Detected responses include:

- `no single UE`
- `could not find any UE`
- `no UE in RRC`

### Preflight and Docker network ownership

The same work also corrected Docker network ownership handling:

- OAI CN Compose is responsible for creating both Docker networks.
- A missing network is informational during preflight.
- A pre-existing network is checked for bridge driver, expected subnet, and
  Compose ownership labels.
- Startup verifies the networks immediately after starting OAI CN.
- The RAN Compose files continue to consume the networks as external networks.

The required networks are:

| Network | Subnet | CN Compose key |
|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` |

This prevents manually created networks with incompatible IPAM settings from
causing Compose startup failures.

## Validation procedure and evidence

### Static checks

The following checks passed:

```bash
bash -n scripts/lib.sh \
  scripts/preflight_check.sh \
  scripts/up.sh \
  scripts/status.sh \
  scripts/trigger_handover.sh \
  scripts/run_smoke_test.sh

docker compose -f oai-cn5g/docker-compose.yaml config --quiet
docker compose -f gnb-docker-compose.yaml config --quiet
git diff --check
```

All RAN topology Compose configurations were also validated during the network
ownership work.

### Startup validation

The corrected startup produced:

```text
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Starting DU1
...
[up] Waiting for UE registration and data plane (180s)
[ue-data] target 192.168.71.135 via oaitun_ue1: reachable
[up] Startup readiness gates passed.
```

The post-start diagnostic then reported zero issues:

```text
[PASS] oaitun_ue1 present with IP: 10.0.0.2
[PASS] UE can reach 192.168.71.135 via oaitun_ue1
=== Post-start check: 0 issue(s) ===
```

### F1 and RRC validation

The CU accepted both DUs:

- DU0, cell `12345678`, PCI 0;
- DU1, cell `11111111`, PCI 1.

The CU then recorded UE registration and PDU-session setup for UE 1.

### Handover validation

The trigger command returned:

```text
RRC F1 handover triggered for UE 1
```

The CU logs confirmed:

```text
Handover triggered for UE 1 ... towards cell 11111111 ... PCI 1
HO acknowledged: Send reconfiguration for UE 1
handover for UE 1 ... complete!
```

After handover, `scripts/status.sh f1` still reported:

```text
UE PDU session: ready (10.0.0.2)
UE data plane 192.168.71.135 via oaitun_ue1: reachable
SUMMARY: PASS
```

## Rejected or intermediate approaches

Several intermediate tests were useful diagnostically but were not retained:

- Removing the explicit RFsim address and relying on `conf-du.conf` did not
  work because `--rfsim` reset the client endpoint to `127.0.0.1`.
- Starting both DUs before UE attachment caused PBCH/SIB1 decode failures.
- The `rfsimulator.hanging-workaround` option found in newer topology files is
  not supported by the current F1 UE image and caused an unknown-option abort.
- Setting `ra_ResponseWindow` to literal `8` was invalid because the field is
  an enum index. Value `5` is the correct selection for a 20-slot window.

These tests are relevant when upgrading OAI images because option support and
RFsim timing behavior may change between builds.

## Operational guidance

Use the normal startup command:

```bash
./scripts/up.sh f1
```

Do not treat startup as successful unless it reaches:

```text
[up] Startup readiness gates passed.
```

Check functional readiness with:

```bash
./scripts/status.sh f1
```

The status must show both a UE PDU-session address and reachable data plane.

Trigger handover with:

```bash
./scripts/trigger_handover.sh f1
```

The command now fails explicitly if no UE is eligible for handover.

## Remaining considerations

- Container health checks still verify process existence. Functional readiness
  is enforced by `up.sh` and `status.sh`, which is appropriate because a DU may
  be intentionally running before UE registration.
- Tailscale warnings remain advisory. Tailscale was active during final
  validation and did not prevent CU Telnet access or handover.
- The preflight host-interface conflict check may identify the Compose-created
  bridge names `oai-cn5g` and `oai-internet` as non-Docker interfaces. That is a
  warning-quality reporting issue and does not affect this fix.
- Future OAI image upgrades should repeat the RFsim connection, random-access,
  PDU-session, and post-handover data-plane checks because timing and supported
  command-line options can change.

## Files changed

| File | Purpose |
|---|---|
| `conf-du.conf` | Increase the RA response window |
| `gnb-docker-compose.yaml` | Correct DU RFsim and DU1 F1 addresses |
| `scripts/lib.sh` | Add network and UE readiness helpers |
| `scripts/preflight_check.sh` | Validate Compose and CN-owned networks |
| `scripts/up.sh` | Stage F1 startup and enforce data-plane readiness |
| `scripts/status.sh` | Include PDU-session and data-plane checks |
| `scripts/trigger_handover.sh` | Propagate no-UE handover failures |
| `scripts/run_smoke_test.sh` | Pass topology into preflight |

## Conclusion

The original issue was not a 5GC or subscriber configuration failure. It was a
combination of incorrect container-local addressing, unsafe radio startup
ordering, an insufficient random-access response window, and readiness checks
that measured processes instead of service behavior.

The corrected testbed now uses functional readiness as its success criterion.
The full F1 path—RF synchronization, random access, RRC, registration, PDU
session, user-plane connectivity, handover, and post-handover connectivity—was
validated successfully.
