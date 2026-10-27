# Testbeds de handover com USRP X310 (distribuídos, UE COTS)

> Tradução para o português. O original em inglês é o [guide-usrp-distributed-handover.md](../en/guide-usrp-distributed-handover.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Guia
>
> **Leitura obrigatória:** [guia USRP X310 + UE COTS](guide-usrp-x310-cots.pt-BR.md), [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) e [F04 — Enumerações de configuração e temporização de rádio na OAI](foundation-f04-oai-config-enums-and-timing.pt-BR.md)

Este guia trata da execução das três topologias de handover em **rádios USRP X310 reais**,
espelhando o conjunto em rfsim:

| Diretório da topologia | Handover | Nós (um rádio por host) | Disparo |
|---|---|---|---|
| `f1/` | Intra-gNB (F1) | 1 CU (sem rádio) + DU0 + DU1 (uma X310 cada) | Telnet da CU `ci trigger_f1_ho` |
| `n2_monolithic/` | Inter-gNB (N2) | gnb0 + gnb1 (uma X310 cada) | Telnet da gnb0 `ci trigger_n2_ho` |
| `n2_cu_du/` | Inter-gNB (N2) | cu0 + du0 (site 0), cu1 + du1 (site 1) | Telnet da cu0 `ci trigger_n2_ho` |

Os arquivos ficam em `experiments/usrp_handover/`. O UE é um **celular COTS** (a programação do SIM
e a subida do rádio estão no [guia USRP X310 + UE COTS](guide-usrp-x310-cots.pt-BR.md)).

> Em RF real, o truque do rfsim de "UE como servidor" deixa de existir — **cada célula precisa do seu próprio rádio**.
> A implantação é de **um rádio por host**: cada DU/gNB roda em seu próprio host, com uma X310 num
> enlace 10GbE dedicado; as CUs não têm rádio; o 5GC roda em seu próprio host. A topologia de célula única
> `usrp-cots` é a referência de subida; esta é a extensão para handover entre várias células.

---

## 1. Em que o modo distribuído difere do conjunto em rfsim

As topologias em rfsim rodam num único host: todos os contêineres compartilham uma bridge Docker
(`192.168.70.0/26`) e se endereçam pelo nome do contêiner. Aqui, cada nó fica num
**host diferente**, de modo que F1, N2/NG e N3 atravessam a **LAN real**:

- Todo nó roda com `network_mode: host` e controla sua X310 local.
- Todos os endereços entre nós são **injetados em tempo de execução a partir de um `.env` por host** no
  `USE_ADDITIONAL_OPTIONS` do contêiner (os arquivos de configuração contêm apenas parâmetros de rádio/célula e
  marcadores). Isso reutiliza o padrão de substituição já usado pelos arquivos Compose do rfsim.
- Não há um único `docker compose up`: você inicia um papel por host com
  `scripts/usrp_site_up.sh`.

---

## 2. Planejamento de IPs

Escolha IPs de LAN para cada host e para os rádios e, em seguida, copie `.env.example` para `.env` no
diretório da topologia **em cada host** e preencha os valores. Exemplo para `n2_cu_du`:

| Variável | Significado | Exemplo |
|---|---|---|
| `CORE_HOST_IP` | IP de LAN do host do núcleo (gateway da rota para a sub-rede do CN) | `192.168.1.10` |
| `AMF_N2_IP` | Endereço do AMF na bridge do CN (a RAN se conecta aqui) | `192.168.70.132` |
| `CU0_HOST_IP` / `CU1_HOST_IP` | IPs de LAN dos hosts das CUs (escuta F1 + NG + Telnet) | `192.168.1.20/.25` |
| `DU0_HOST_IP` / `DU1_HOST_IP` | IPs de LAN dos hosts das DUs (F1) | `192.168.1.30/.40` |
| `DU0_SDR_ADDR` / `DU1_SDR_ADDR` | cada X310 no enlace 10GbE do seu host | `192.168.40.2` |

Os rádios usam sua própria `/24` dedicada em cada host (por exemplo, `192.168.40.0/24`), separada da
LAN entre os hosts.

---

## 3. Tornar o 5GC alcançável a partir dos hosts da RAN

O 5GC permanece em sua bridge Docker (sem mudanças no CN). Colocar o AMF/UPF na rede do host **não** é
usado, porque as NFs compartilham a porta SBI 8080 e se resolvem umas às outras na bridge — isso
quebraria a malha SBI. Em vez disso, roteie a sub-rede do CN pela LAN.

No **host do núcleo** (uma vez):

```bash
sudo ./scripts/usrp_core_routing.sh <core-host-lan-ip>
```

Isso ativa o encaminhamento IPv4 e libera `192.168.70.128/26` na cadeia FORWARD e, em seguida,
imprime o comando de rota para os hosts da RAN. Em **cada host da RAN**:

```bash
sudo ip route add 192.168.70.128/26 via <core-host-lan-ip>
ping -c1 192.168.70.132   # AMF reachable?
ping -c1 192.168.70.134   # UPF (N3) reachable?
```

As gNBs/CUs usam `amf_ip_address = AMF_N2_IP` (o IP do AMF na bridge), e o SMF lhes fornece o
endereço N3 da UPF (`192.168.70.134`) — ambos alcançáveis depois que a rota estiver configurada.

---

## 4. SIM e rádios

- Programe o SIM COTS e verifique cada X310 conforme o
  [guia USRP X310 + UE COTS](guide-usrp-x310-cots.pt-BR.md) (`./scripts/check_usrp.sh` em cada
  host de rádio; defina `SDR_ADDR` como o rádio daquele host).
- Jumbo frames e buffers de socket no host são necessários em todos os hosts de rádio (veja aquele guia).

---

## 5. Subida

Inicie o 5GC no host do núcleo (fluxo existente), configure o roteamento (§3) e, em seguida, inicie cada papel
em seu host. O `usrp_site_up.sh` inicia o papel e aguarda a prontidão local (e a associação
NG, para os papéis de CU/gNB).

**F1** (3 hosts de RAN):
```bash
# CU host
./scripts/usrp_site_up.sh f1 cu
# DU0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du0
# DU1 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du1
```

**N2 monolítica** (2 hosts de RAN):
```bash
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0   # gnb0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb1   # gnb1 host
```

**N2 CU/DU** (4 hosts de RAN):
```bash
./scripts/usrp_site_up.sh n2-cu-du cu0                            # cu0 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du0          # du0 host
./scripts/usrp_site_up.sh n2-cu-du cu1                            # cu1 host
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du1          # du1 host
```

Confirme a associação NG no host do núcleo: `docker logs oai-amf 2>&1 | grep -i NGSetup`.
Em seguida, ligue o UE COTS para que ele se conecte à célula de origem.

---

## 6. Disparar o handover

Execute a partir de qualquer host que alcance o Telnet do nó de origem (por exemplo, o host do núcleo/controle),
apontando o disparo existente para o IP de LAN do nó de origem:

**F1** (origem = CU):
```bash
CU_TELNET_HOST=<CU_HOST_IP> ./scripts/trigger_handover.sh f1
```

**N2 monolítica** (origem = gnb0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<GNB0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-monolithic
```

**N2 CU/DU** (origem = cu0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<CU0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-cu-du
```

`N2_UE_RRC_ID` é o ID RRC do UE no nó de origem (normalmente `1` para um único UE; leia-o
no log da origem em caso de dúvida). O celular também emite relatórios de medição reais, de modo que a
rede pode disparar o handover por conta própria depois que as vizinhas estiverem configuradas.

---

## 7. Verificar o handover

- **Logs de origem/destino**: a origem mostra Handover Required / (F1) comando de handover; o destino
  mostra o UE admitido e o CFRA/RA sendo concluído.
- **Host do núcleo**: `docker logs oai-amf` mostra o path switch (N2) no caso inter-gNB.
- **Celular**: continuidade da sessão de dados (um download/ping em andamento continua durante a
  troca). A medição a partir do aparelho é manual.

Pare um papel em seu host:
```bash
./scripts/usrp_site_down.sh <topology> <role>
```

---

## 8. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| A gNB/CU nunca se associa via NG | O host da RAN não alcança o AMF | verifique se o `usrp_core_routing.sh` foi executado; `ping 192.168.70.132` a partir do host da RAN; firewall |
| A DU nunca se conecta à CU | Endereços F1 / roteamento na LAN | confirme `DUx_HOST_IP`/`CUx_HOST_IP`, os dois hosts na LAN, SCTP liberado |
| O UE se conecta, mas não há dados | N3 da UPF inalcançável a partir do host da DU/gNB | `ping 192.168.70.134`; verifique a rota e as regras FORWARD |
| O handover nunca ocorre | Vizinha/PCI/ID RRC errados | verifique `neighbour-config.conf`, a PCI de destino (1) e o `N2_UE_RRC_ID` no log da origem |
| Underflow/overflow do rádio (U/O/L) | Buffers/MTU do 10GbE | aplique os buffers do host + MTU 9000 (veja o guia COTS) |
| O celular vê só uma célula | Ganhos/antena/banda | aumente o ganho de TX da célula fraca; confirme as duas células na banda n78 |

---

## 9. Fora do escopo

- Arranjo com vários rádios num único host (este guia pressupõe um rádio por host).
- Ping/iperf automatizados a partir do UE COTS (manual por enquanto).
- nr-ue da OAI num rádio dedicado como UE.
