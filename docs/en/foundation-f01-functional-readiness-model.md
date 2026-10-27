# Functional Readiness Model for OAI Testbeds

> **Document type:** Foundation (`F01`)
>
> **Required reading:** None

## Problem

An OAI process can remain alive while the protocol stack is unusable. Therefore container existence, process health, and open control ports are necessary but not sufficient readiness conditions.

The testbed uses a layered readiness model:

| Layer | Evidence | Typical failure when absent |
|---|---|---|
| Host | Docker, TUN, SCTP, tools | Containers cannot start or attach devices |
| Container | Required process running | Immediate crash or restart loop |
| Transport | RFsim, F1, NGAP/PFCP associations | Components run but cannot communicate |
| Radio | PBCH/SIB1, PRACH/RAR | UE cannot enter RRC |
| Control plane | RRC and NAS registration | AMF has no registered UE |
| Session | `oaitun_ue1` with UE address | No PDU session |
| User plane | Target reachable via UE tunnel | Session exists but forwarding is broken |
| Handover | Trigger acknowledged and completes | No eligible UE or target-cell failure |

## Readiness invariants

The following implications must not be assumed:

```text
container running != RFsim connected
RF synchronized != random access complete
RRC connected != NAS registered
UE registered != PDU session established
PDU interface present != user-plane target reachable
handover command accepted != handover completed
```

## Script responsibilities

### `preflight_check.sh`

Checks prerequisites that can be evaluated before startup: Docker and Compose, host tools, Compose validity, network compatibility, TUN, SCTP, routes, VPNs, ports, images, and disk space. Preflight must not require runtime state that startup is responsible for creating.

### `up.sh`

For F1, runtime gates are:

1. CN services healthy.
2. CU and Telnet ready.
3. DU0 and UE started.
4. UE PDU session and DN reachability ready.
5. DU1 started.
6. UE data-plane reachability rechecked.

The second data-plane check detects target-cell startup effects on the registered UE.

### `status.sh`

`SUMMARY: PASS` requires all critical containers, the handover control endpoint, `oaitun_ue1` with an IPv4 address, and the configured DN target reachable through the tunnel.

### `poststart_check.sh`

Provides non-blocking diagnostics and fatal-log scanning. The blocking startup verdict remains in `up.sh`.

### `trigger_handover.sh`

Treats a control-plane response saying no UE exists in RRC as a failed command.

## Recommended diagnostic order

1. Container state and exit codes.
2. RFsim sockets and endpoint addresses.
3. F1, NGAP, and PFCP associations.
4. UE PBCH/SIB1 synchronization.
5. PRACH and RAR/Msg2 processing.
6. CU/gNB RRC UE state.
7. AMF UE registration table.
8. `oaitun_ue1` address.
9. Ping through `oaitun_ue1`.
10. Handover source and target logs.

This avoids debugging subscriber or SMF configuration when the UE has not completed radio synchronization.

## Health-check guidance

Docker health checks should remain lightweight and local. Cross-container and end-to-end readiness belongs in orchestration scripts. A DU may be a healthy process while waiting for a UE, and a UE may be a healthy RFsim server before a DU connects; full readiness in individual health checks would create circular dependencies.
