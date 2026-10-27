# OAI User-Plane and DN Reachability

> **Document type:** Foundation (`F02`)
>
> **Required reading:** [F00 — Docker network ownership](foundation-f00-docker-network-ownership.md)

## Reference path

For the default `oai` DNN, subscriber `001010000000001` receives `10.0.0.2`. The local test target is `oai-ext-dn` at `192.168.71.135`.

```text
oai-nr-ue oaitun_ue1: 10.0.0.2
        |
        | GTP-U through gNB/CU
        v
oai-upf public eth0: 192.168.70.134
oai-upf traffic eth1: 192.168.71.134
        |
        v
oai-ext-dn public eth0: 192.168.70.135
oai-ext-dn traffic eth1: 192.168.71.135
```

## Deterministic interface names

| Container | Network | Interface | Address |
|---|---|---|---|
| UPF | `public_net` | `eth0` | `192.168.70.134` |
| UPF | `traffic_net` | `eth1` | `192.168.71.134` |
| oai-ext-dn | `public_net` | `eth0` | `192.168.70.135` |
| oai-ext-dn | `traffic_net` | `eth1` | `192.168.71.135` |

Explicit interface names prevent Docker attachment order from changing interfaces used by OAI and route commands.

## Return route

`oai-ext-dn` installs:

```bash
ip route add 10.0.0.0/16 via 192.168.70.134 dev eth0
```

This sends traffic for UE DNN subnets back through the UPF public-side address.

## Why the ping interface matters

The UE container also has ordinary Docker interfaces. Bind probes to the PDU interface:

```bash
docker exec oai-nr-ue ping -I oaitun_ue1 -c 3 192.168.71.135
```

Without `-I oaitun_ue1`, a successful ping may test Docker networking rather than the UE user plane.

## iperf target selection

The ping probe targets `192.168.71.135`, but iperf targets the oai-ext-dn public-side address `192.168.70.135`. The UPF delivers the tested TCP/UDP flow on that public-side address; targeting `192.168.71.135` produced an asymmetric iperf control connection even though ICMP remained reachable.

The iperf client still binds to the UE PDU address on `oaitun_ue1`, so traffic enters the user plane rather than the UE container's Docker route.

## Readiness conditions

1. `oaitun_ue1` exists.
2. It has the expected UE address.
3. The DN target is reachable through it.

```bash
docker exec oai-nr-ue ip -4 addr show oaitun_ue1
docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
```

## Diagnostic workflow

Run `./scripts/diagnose_dn_reachability.sh`. It records network inspection, routes, interfaces, probes, and firewall state under `results/diagnostics/` without modifying the system.

Manual checks:

```bash
docker exec oai-nr-ue ip route
docker exec oai-upf ip -4 addr
docker exec oai-upf ip route
docker exec oai-ext-dn ip -4 addr
docker exec oai-ext-dn ip route
docker network inspect oai-cn5g-public-net
docker network inspect oai-ext-dn-traffic-net
```

## Common failure distinctions

| Observation | Likely layer |
|---|---|
| `oaitun_ue1` absent | Registration or PDU-session setup |
| Tunnel exists, local DN unreachable | UPF, route, interface, or firewall |
| Internet reachable but oai-ext-dn fails | Local DN attachment or return route |
| oai-ext-dn reachable without tunnel binding | Docker path tested instead of PDU path |
| UPF lacks expected `eth1` address | Compose network attachment/order problem |

The UPF image may lack tools such as `ping`. A missing command must not be reported as a reachability failure.
