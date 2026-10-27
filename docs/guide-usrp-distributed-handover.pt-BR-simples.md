# Testbeds de handover com USRP X310 (distribuídos, com UE comercial)

> Tradução para o português em Linguagem Simples. O original em inglês é o [guide-usrp-distributed-handover.md](guide-usrp-distributed-handover.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** guia
>
> **Leitura prévia:** [guia do USRP X310 com UE comercial](guide-usrp-x310-cots.pt-BR-simples.md), [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md) e [F04 — Valores enumerados da configuração da OAI e tempos de rádio](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md)

Este guia mostra como executar as três topologias de handover com **rádios USRP X310 reais**. Elas espelham as topologias do rfsim:

| Pasta da topologia | Handover | Nós (um rádio por computador) | Comando |
|---|---|---|---|
| `f1/` | Intra-gNB (F1) | 1 CU (sem rádio), DU0 e DU1 (um X310 cada) | Telnet na CU: `ci trigger_f1_ho` |
| `n2_monolithic/` | Inter-gNB (N2) | gnb0 e gnb1 (um X310 cada) | Telnet na gnb0: `ci trigger_n2_ho` |
| `n2_cu_du/` | Inter-gNB (N2) | cu0 e du0 (local 0), cu1 e du1 (local 1) | Telnet na cu0: `ci trigger_n2_ho` |

Os arquivos ficam em `experiments/usrp_handover/`. O UE é um **celular comercial (UE comercial, COTS)**. A programação do chip SIM e a subida do rádio estão no [guia do USRP X310 com UE comercial](guide-usrp-x310-cots.pt-BR-simples.md).

> Com rádio real, o truque do rfsim de usar o UE como servidor não existe. **Cada célula precisa do próprio rádio.** A montagem usa **um rádio por computador**:
>
> - cada DU ou gNB roda em um computador próprio, com um X310 em um enlace dedicado de 10 Gbit/s;
> - as CUs não têm rádio;
> - o núcleo 5G roda em um computador próprio.
>
> A topologia `usrp-cots`, com uma célula, é a base para a subida. Este guia a estende para várias células com handover.

---

## 1. Diferenças em relação às topologias do rfsim

As topologias do rfsim rodam em um único computador. Todos os contêineres usam a mesma bridge Docker (`192.168.70.0/26`) e se encontram pelo nome do contêiner. Aqui, cada nó fica em um **computador diferente**. Por isso, as interfaces F1, N2/NG e N3 passam pela **rede local (LAN) real**:

- Cada nó usa `network_mode: host` e controla o X310 local.
- Todos os endereços entre nós **vêm de um arquivo `.env` de cada computador**, na hora de subir. Eles entram no `USE_ADDITIONAL_OPTIONS` do contêiner. Os arquivos de configuração só têm os parâmetros de rádio e de célula, e marcadores de posição. É a mesma técnica de substituição dos arquivos Compose do rfsim.
- Não há um único `docker compose up`. Você sobe um papel em cada computador, com o `scripts/usrp_site_up.sh`.

---

## 2. Planejar os endereços IP

1. Escolha os IPs da LAN de cada computador e de cada rádio.
2. **Em cada computador**, copie o `.env.example` da pasta da topologia para `.env`.
3. Preencha os IPs no `.env`.

Exemplo para `n2_cu_du`:

| Variável | Significado | Exemplo |
|---|---|---|
| `CORE_HOST_IP` | IP do computador do núcleo 5G na LAN (gateway da rota para a sub-rede do núcleo) | `192.168.1.10` |
| `AMF_N2_IP` | Endereço do AMF na bridge do núcleo 5G (a RAN se conecta a ele) | `192.168.70.132` |
| `CU0_HOST_IP` / `CU1_HOST_IP` | IPs dos computadores das CUs na LAN (escuta F1, NG e Telnet) | `192.168.1.20` e `.25` |
| `DU0_HOST_IP` / `DU1_HOST_IP` | IPs dos computadores das DUs na LAN (F1) | `192.168.1.30` e `.40` |
| `DU0_SDR_ADDR` / `DU1_SDR_ADDR` | Cada X310 no enlace de 10 Gbit/s do seu computador | `192.168.40.2` |

Os rádios usam uma rede `/24` própria em cada computador (por exemplo, `192.168.40.0/24`). Ela é separada da LAN entre os computadores.

---

## 3. Tornar o núcleo 5G acessível aos computadores da RAN

O núcleo 5G continua na bridge Docker dele. Nada muda no núcleo. O AMF e o UPF **não** usam a rede do computador. Motivo: as funções de rede compartilham a porta SBI 8080 e se encontram pela bridge. Com a rede do computador, essa comunicação entre elas quebraria. Em vez disso, a sub-rede do núcleo 5G é roteada pela LAN.

No **computador do núcleo 5G**, execute uma vez:

```bash
sudo ./scripts/usrp_core_routing.sh <ip-do-núcleo-na-LAN>
```

O script liga o encaminhamento IPv4 e libera `192.168.70.128/26` na cadeia FORWARD. No final, ele mostra o comando de rota para os computadores da RAN. Em **cada computador da RAN**, execute:

```bash
sudo ip route add 192.168.70.128/26 via <ip-do-núcleo-na-LAN>
ping -c1 192.168.70.132   # o AMF responde?
ping -c1 192.168.70.134   # o UPF (N3) responde?
```

As gNBs e CUs usam `amf_ip_address = AMF_N2_IP`, que é o IP do AMF na bridge. O SMF informa a elas o endereço N3 do UPF (`192.168.70.134`). Com a rota criada, os dois endereços respondem.

---

## 4. Chip SIM e rádios

- Programe o chip SIM do celular e confira cada X310 conforme o [guia do USRP X310 com UE comercial](guide-usrp-x310-cots.pt-BR-simples.md). Execute `./scripts/check_usrp.sh` em cada computador com rádio, com `SDR_ADDR` apontando para o rádio daquele computador.
- Todo computador com rádio precisa de quadros jumbo e de buffers de socket grandes. Veja aquele guia.

---

## 5. Subir

1. Suba o núcleo 5G no computador do núcleo, pelo processo de sempre.
2. Configure as rotas (seção 3).
3. Suba cada papel no seu computador.

O `usrp_site_up.sh` sobe o papel e espera ele ficar pronto no computador. Nos papéis de CU e de gNB, ele também espera a associação NG.

**F1** (3 computadores da RAN):
```bash
# computador da CU
./scripts/usrp_site_up.sh f1 cu
# computador da DU0
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du0
# computador da DU1
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh f1 du1
```

**N2 monolítico** (2 computadores da RAN):
```bash
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0   # computador da gnb0
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb1   # computador da gnb1
```

**N2 CU/DU** (4 computadores da RAN):
```bash
./scripts/usrp_site_up.sh n2-cu-du cu0                            # computador da cu0
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du0          # computador da du0
./scripts/usrp_site_up.sh n2-cu-du cu1                            # computador da cu1
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-cu-du du1          # computador da du1
```

No computador do núcleo 5G, confirme a associação NG: `docker logs oai-amf 2>&1 | grep -i NGSetup`. Depois, ligue o celular, para que ele se conecte à célula de origem.

---

## 6. Comandar o handover

Execute o comando em qualquer computador que alcance o Telnet do nó de origem, como o computador do núcleo ou de controle. Aponte o script de handover para o IP do nó de origem na LAN.

**F1** (origem: a CU):
```bash
CU_TELNET_HOST=<CU_HOST_IP> ./scripts/trigger_handover.sh f1
```

**N2 monolítico** (origem: a gnb0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<GNB0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-monolithic
```

**N2 CU/DU** (origem: a cu0):
```bash
N2_SOURCE_GNB_TELNET_HOST=<CU0_HOST_IP> N2_TARGET_PCI=1 N2_UE_RRC_ID=1 \
  ./scripts/trigger_handover.sh n2-cu-du
```

O `N2_UE_RRC_ID` é o identificador RRC do UE no nó de origem. Com um único UE, em geral, ele vale `1`. Na dúvida, leia-o no log da origem.

O celular também envia relatórios de medição reais. Por isso, depois que as células vizinhas estiverem configuradas, a rede pode iniciar o handover sozinha.

---

## 7. Conferir o handover

- **Logs da origem e do destino:** a origem mostra o Handover Required ou, no F1, o comando de handover. O destino mostra o UE aceito e o acesso aleatório (CFRA/RA) concluído.
- **Computador do núcleo 5G:** no handover inter-gNB, o `docker logs oai-amf` mostra a troca de caminho (*path switch*) no N2.
- **Celular:** a sessão de dados continua. Um download ou um ping em andamento segue funcionando durante a troca. A medição no celular é manual.

Para parar um papel no seu computador, use:
```bash
./scripts/usrp_site_down.sh <topologia> <papel>
```

---

## 8. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| A gNB ou a CU nunca se associa no NG. | O computador da RAN não alcança o AMF. | Confira se o `usrp_core_routing.sh` foi executado. Execute `ping 192.168.70.132` no computador da RAN. Confira o firewall. |
| A DU nunca se conecta à CU. | Endereços F1 ou rotas na LAN | Confira `DUx_HOST_IP` e `CUx_HOST_IP`. Confira se os dois computadores estão na LAN e se o SCTP está liberado. |
| O UE se conecta, mas não há dados. | O computador da DU ou da gNB não alcança o N3 do UPF. | Execute `ping 192.168.70.134`. Confira a rota e as regras FORWARD. |
| O handover nunca acontece. | Vizinha, PCI ou identificador RRC errado | Confira o `neighbour-config.conf`, o PCI de destino (1) e o `N2_UE_RRC_ID` no log da origem. |
| Falta ou excesso de amostras no rádio (`U`/`O`/`L`) | Buffers ou MTU do enlace de 10 Gbit/s | Aplique os buffers e o MTU 9000 no computador (veja o guia do UE comercial). |
| O celular só vê uma célula. | Ganhos, antena ou banda | Aumente o ganho de transmissão da célula fraca. Confirme que as duas células estão na banda n78. |

---

## 9. Fora do escopo

- Vários rádios em um único computador. Este guia supõe um rádio por computador.
- Medição automática com ping ou iperf a partir do celular. Por enquanto, ela é manual.
- O OAI NR-UE com rádio próprio no papel de UE.
