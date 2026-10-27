# Docker Network Ownership for OAI Compose Stacks

> **Document type:** Foundation (`F00`)
>
> **Required reading:** None

## Purpose

This document defines which Compose stack owns the shared Docker networks and how other OAI stacks should consume them. The rule applies to the F1 and N2 topologies in this repository.

## Ownership model

The OAI CN Compose project owns and creates:

| Docker network | Subnet | Compose network key | Linux bridge |
|---|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` | `oai-cn5g` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` | `oai-internet` |

The network definitions live in `oai-cn5g/docker-compose.yaml`. RAN Compose files reference these networks with `external: true`.

The resulting lifecycle is:

```text
OAI CN Compose starts
        |
        +-- creates public_net and traffic_net
        |
RAN Compose starts
        |
        +-- attaches containers to the existing external networks
```

## Why networks must not be created manually

A command such as:

```bash
docker network create oai-cn5g-public-net
```

creates an independently managed network. Even if its name matches, it may differ in:

- subnet and IPAM configuration;
- driver options and Linux bridge name;
- Compose ownership labels; and
- lifecycle behavior during `docker compose down`.

The historical manual command used `192.168.70.0/24`, while the CN Compose definition uses `192.168.70.128/26`. Static container addresses can appear valid under both ranges, which makes the mismatch easy to overlook, but Compose cannot replace an existing incompatible network.

## Correct startup behavior

Run:

```bash
./scripts/up.sh <topology>
```

Preflight treats a missing CN network as informational because the CN stack has not started yet. After CN startup, `up.sh` verifies:

- the network exists;
- its driver is `bridge`;
- its expected subnet is present;
- `com.docker.compose.project` identifies the CN project; and
- `com.docker.compose.network` identifies the expected network key.

Only then is the RAN stack started.

## Recovery from an incompatible network

First stop containers attached to the network:

```bash
./scripts/down.sh
```

Inspect remaining attachments:

```bash
docker network inspect oai-cn5g-public-net
docker network inspect oai-ext-dn-traffic-net
```

If no unrelated container depends on the incompatible network, remove it:

```bash
docker network rm oai-cn5g-public-net
docker network rm oai-ext-dn-traffic-net
```

Then run `scripts/up.sh` and allow CN Compose to recreate both networks. Do not remove an in-use network without identifying its attached containers.

## Compose project-name constraint

Network ownership validation expects the CN Compose project name to match the directory-derived default `oai-cn5g`, unless `COMPOSE_PROJECT_NAME` is supplied consistently.

If a custom project name is required:

```bash
COMPOSE_PROJECT_NAME=my-cn ./scripts/up.sh f1
```

The same environment value must be used for subsequent CN lifecycle commands.

## Design rule for new topologies

New RAN topologies should not duplicate CN network IPAM definitions. They should declare:

```yaml
networks:
  public_net:
    external: true
    name: oai-cn5g-public-net
```

Add `traffic_net` only when a RAN container genuinely requires direct access to the traffic-side Docker network. This keeps one authoritative network definition and avoids configuration drift.
