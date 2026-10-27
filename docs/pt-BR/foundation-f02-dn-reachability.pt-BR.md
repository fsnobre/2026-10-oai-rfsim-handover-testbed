# Alcance do plano de usuário e da DN na OAI

> Tradução para o português. O original em inglês é o [foundation-f02-dn-reachability.md](../en/foundation-f02-dn-reachability.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Fundamento (`F02`)
>
> **Leitura obrigatória:** [F00 — Propriedade das redes Docker](foundation-f00-docker-network-ownership.pt-BR.md)

## Caminho de referência

Na DNN padrão `oai`, o assinante `001010000000001` recebe `10.0.0.2`. O destino de teste local é o `oai-ext-dn`, em `192.168.71.135`.

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

## Nomes de interface determinísticos

| Contêiner | Rede | Interface | Endereço |
|---|---|---|---|
| UPF | `public_net` | `eth0` | `192.168.70.134` |
| UPF | `traffic_net` | `eth1` | `192.168.71.134` |
| oai-ext-dn | `public_net` | `eth0` | `192.168.70.135` |
| oai-ext-dn | `traffic_net` | `eth1` | `192.168.71.135` |

Nomes de interface explícitos impedem que a ordem de conexão do Docker mude as interfaces usadas pela OAI e pelos comandos de rota.

## Rota de retorno

O `oai-ext-dn` instala:

```bash
ip route add 10.0.0.0/16 via 192.168.70.134 dev eth0
```

Isso envia o tráfego destinado às sub-redes de DNN do UE de volta pelo endereço do lado público da UPF.

## Por que a interface do ping importa

O contêiner do UE também tem interfaces Docker comuns. Vincule as sondas à interface PDU:

```bash
docker exec oai-nr-ue ping -I oaitun_ue1 -c 3 192.168.71.135
```

Sem `-I oaitun_ue1`, um ping bem-sucedido pode estar testando a rede do Docker, e não o plano de usuário do UE.

## Escolha do destino do iperf

A sonda de ping usa como destino `192.168.71.135`, mas o iperf usa o endereço do lado público do oai-ext-dn, `192.168.70.135`. A UPF entrega o fluxo TCP/UDP testado nesse endereço do lado público; usar `192.168.71.135` como destino produziu uma conexão de controle do iperf assimétrica, embora o ICMP continuasse alcançável.

O cliente iperf continua vinculado ao endereço PDU do UE na `oaitun_ue1`, de modo que o tráfego entra no plano de usuário, e não na rota Docker do contêiner do UE.

## Condições de prontidão

1. A `oaitun_ue1` existe.
2. Ela tem o endereço de UE esperado.
3. O destino da DN é alcançável por ela.

```bash
docker exec oai-nr-ue ip -4 addr show oaitun_ue1
docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
```

## Fluxo de diagnóstico

Execute `./scripts/diagnose_dn_reachability.sh`. Ele registra a inspeção das redes, rotas, interfaces, sondas e estado do firewall em `results/diagnostics/`, sem modificar o sistema.

Verificações manuais:

```bash
docker exec oai-nr-ue ip route
docker exec oai-upf ip -4 addr
docker exec oai-upf ip route
docker exec oai-ext-dn ip -4 addr
docker exec oai-ext-dn ip route
docker network inspect oai-cn5g-public-net
docker network inspect oai-ext-dn-traffic-net
```

## Distinções entre falhas comuns

| Observação | Camada provável |
|---|---|
| `oaitun_ue1` ausente | Registro ou estabelecimento da sessão PDU |
| Túnel existe, DN local inalcançável | UPF, rota, interface ou firewall |
| Internet alcançável, mas oai-ext-dn falha | Conexão da DN local ou rota de retorno |
| oai-ext-dn alcançável sem vincular ao túnel | Testou-se o caminho do Docker em vez do caminho PDU |
| UPF sem o endereço `eth1` esperado | Problema de conexão/ordem das redes no Compose |

A imagem da UPF pode não ter ferramentas como o `ping`. Um comando ausente não deve ser relatado como falha de alcance.
