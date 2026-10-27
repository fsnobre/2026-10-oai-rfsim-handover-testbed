# Plano de usuário e acesso à rede de dados na OAI

> Tradução para o português em Linguagem Simples. O original em inglês é o [foundation-f02-dn-reachability.md](foundation-f02-dn-reachability.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** base (`F02`)
>
> **Leitura prévia:** [F00 — Quem cria as redes Docker](foundation-f00-docker-network-ownership.pt-BR-simples.md)

## Caminho de referência

No DNN padrão `oai`, o assinante `001010000000001` recebe o endereço `10.0.0.2`. O destino de teste local é o contêiner `oai-ext-dn`, em `192.168.71.135`. Esse contêiner faz o papel da rede de dados (DN).

```text
oai-nr-ue oaitun_ue1: 10.0.0.2
        |
        | GTP-U pela gNB ou CU
        v
oai-upf eth0 (lado público): 192.168.70.134
oai-upf eth1 (lado de tráfego): 192.168.71.134
        |
        v
oai-ext-dn eth0 (lado público): 192.168.70.135
oai-ext-dn eth1 (lado de tráfego): 192.168.71.135
```

## Nomes fixos das interfaces

| Contêiner | Rede | Interface | Endereço |
|---|---|---|---|
| UPF | `public_net` | `eth0` | `192.168.70.134` |
| UPF | `traffic_net` | `eth1` | `192.168.71.134` |
| oai-ext-dn | `public_net` | `eth0` | `192.168.70.135` |
| oai-ext-dn | `traffic_net` | `eth1` | `192.168.71.135` |

Os nomes das interfaces são fixos. Assim, a ordem em que o Docker liga as redes não muda as interfaces que a OAI e os comandos de rota usam.

## Rota de volta

O `oai-ext-dn` cria esta rota:

```bash
ip route add 10.0.0.0/16 via 192.168.70.134 dev eth0
```

Com ela, o tráfego para as sub-redes dos UEs volta pelo endereço público do UPF.

## Por que a interface do ping importa

O contêiner do UE também tem interfaces Docker comuns. Por isso, faça os testes pela interface da sessão PDU:

```bash
docker exec oai-nr-ue ping -I oaitun_ue1 -c 3 192.168.71.135
```

Sem `-I oaitun_ue1`, o ping pode responder pela rede Docker, e não pelo plano de usuário do UE.

## Destino do iperf

O ping vai para `192.168.71.135`. O iperf vai para o endereço público do `oai-ext-dn`, `192.168.70.135`. O UPF entrega o fluxo TCP ou UDP testado nesse endereço público. Com o destino `192.168.71.135`, a conexão de controle do iperf ficou assimétrica, mesmo com o ping funcionando.

O cliente iperf continua usando como origem o endereço da sessão PDU, na `oaitun_ue1`. Assim, o tráfego passa pelo plano de usuário, e não pela rota Docker do contêiner do UE.

## Condições de prontidão

1. A interface `oaitun_ue1` existe.
2. Ela tem o endereço esperado do UE.
3. O destino na rede de dados responde por ela.

```bash
docker exec oai-nr-ue ip -4 addr show oaitun_ue1
docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
```

## Como diagnosticar

Execute `./scripts/diagnose_dn_reachability.sh`. Ele grava em `results/diagnostics/` as redes, as rotas, as interfaces, os testes e o estado do firewall. Ele não muda nada no sistema.

Conferências manuais:

```bash
docker exec oai-nr-ue ip route
docker exec oai-upf ip -4 addr
docker exec oai-upf ip route
docker exec oai-ext-dn ip -4 addr
docker exec oai-ext-dn ip route
docker network inspect oai-cn5g-public-net
docker network inspect oai-ext-dn-traffic-net
```

## Como separar as falhas comuns

| O que você vê | Camada provável |
|---|---|
| A interface `oaitun_ue1` não existe. | Registro ou criação da sessão PDU |
| O túnel existe, mas a rede de dados local não responde. | UPF, rota, interface ou firewall |
| A internet responde, mas o `oai-ext-dn` não. | Ligação da rede de dados local ou rota de volta |
| O `oai-ext-dn` responde sem usar o túnel. | O teste usou o caminho Docker, e não a sessão PDU. |
| O UPF não tem o endereço esperado na `eth1`. | Problema na ligação ou na ordem das redes no Compose |

A imagem do UPF pode não ter ferramentas como o `ping`. A falta de um comando não indica falha de acesso. Não a relate como tal.
