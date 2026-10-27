# RFsim Multi-Cell Operating Rules

> **Document type:** Foundation (`F03`)
>
> **Required reading:** [F00 — Docker network ownership](foundation-f00-docker-network-ownership.md)

## Topology rule

In the multi-cell topologies used here, the UE is the RFsim server and each DU/gNB is an RFsim client:

```text
DU/gNB 0 -----\
               >----- oai-nr-ue RFsim server :4043
DU/gNB 1 -----/
```

The UE server address is `192.168.70.181`.

## Container addressing

`127.0.0.1` always refers to the current container namespace. A DU configured with `--rfsimulator.serveraddr 127.0.0.1` tries to connect to itself, not the UE container.

Use the UE address explicitly:

```text
--rfsimulator.serveraddr 192.168.70.181
```

This repository uses indexed and non-indexed OAI option forms depending on topology and image behavior. Validate the effective command line after an OAI image upgrade.

## Command-line precedence

For the tested OAI develop image, enabling `--rfsim` initialized the client endpoint to `127.0.0.1`, even when the configuration file contained another address. The endpoint is therefore explicit on the DU command line.

Inspect:

```bash
docker logs <du-or-gnb> | grep -E "CMDLINE|Trying to connect"
```

## F1 addressing

| Component | Address |
|---|---|
| CU | `192.168.70.150` |
| DU0 | `192.168.70.171` |
| DU1 | `192.168.70.172` |

A DU local F1 address of `127.0.0.1` cannot establish SCTP with a CU in another container.

## Source-cell-first startup

For F1 initial attachment:

1. Start the UE RFsim server and source DU0.
2. Wait for UE PDU-session and data-plane readiness.
3. Start target DU1.
4. Verify the UE remains reachable.

Starting both RF transmitters before initial attachment caused PBCH and SIB1 decoding instability in the validated environment. Once attached, both DUs remain connected and F1 handover succeeds.

## Verification

```bash
docker exec oai-nr-ue ss -ltnp
docker exec oai-du0 ss -tnp
docker exec oai-du1 ss -tnp
docker logs oai-cu | grep -E "F1 Setup Request|cell .* is in service"
```

Expected DU peer: `192.168.70.181:4043`.

## Version sensitivity

OAI RFsim options are image-sensitive. An option present in another topology may be unsupported by the current image. Unknown options can be detected late and may abort after radio activity begins.

After changing images, revalidate server/client roles, accepted option names, TCP connections, synchronization, random access, PDU-session establishment, and post-handover connectivity.
