# Guia USRP X310 + UE COTS

> Tradução para o português. O original em inglês é o [guide-usrp-x310-cots.md](../en/guide-usrp-x310-cots.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Guia
>
> **Leitura obrigatória:** [F00 — Propriedade das redes Docker](foundation-f00-docker-network-ownership.pt-BR.md), [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) e [F04 — Enumerações de configuração e temporização de rádio na OAI](foundation-f04-oai-config-enums-and-timing.pt-BR.md)

Este guia trata da topologia `usrp-cots`: uma única gNB monolítica da OAI controlando um
rádio definido por software **USRP X310**, com um **celular comercial (COTS)**
conectando-se pelo ar como UE. É a contraparte com RF real dos experimentos de handover
em rfsim — não há rfsim, nem modelo de canal, nem contêiner `oai-nr-ue`.

> Escopo: este guia entrega a subida de uma gNB de célula única na X310 e a verificação
> da conexão do celular COTS. A medição automatizada com ping/iperf a partir do aparelho **não** está incluída (por
> enquanto, ela é feita manualmente no celular). Para handover entre várias células em rádios reais (F1 e N2,
> um rádio por host), veja o
> [guia de handover com USRP (distribuído)](guide-usrp-distributed-handover.pt-BR.md) — esta topologia de célula
> única é a referência de subida para ele.

Relacionados: [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) ·
[Pipeline de medição](guide-measurement-pipeline.pt-BR.md).

---

## 1. Topologia

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

- O contêiner da gNB roda com `network_mode: host`, para poder controlar a X310 pela
  NIC 10GbE do host, e ainda assim alcança o 5GC na bridge Docker.
- O UE é um aparelho real; ele precisa ter um SIM cadastrado no banco de assinantes da OAI.

---

## 2. Montagem do hardware

1. **Enlace 10GbE.** Conecte a porta 10GbE (SFP+) da X310 a uma NIC 10GbE do host. Dê à NIC
   do host um endereço estático na mesma `/24` do rádio, por exemplo, host `192.168.40.1` e X310
   `192.168.40.2`.
2. **Jumbo frames + buffers** (necessários para a vazão da X310; não pertencem a namespace, são definidos no
   **host**, e não no Compose):
   ```bash
   sudo ip link set <10gbe-iface> mtu 9000
   sudo sysctl -w net.core.rmem_max=33554432
   sudo sysctl -w net.core.wmem_max=33554432
   ```
3. **Front-end de RF.** Use as portas TX/RX da banda n78 (3,6 GHz) com antenas adequadas ou um
   caminho cabeado e atenuado. Nunca transmita em espectro licenciado sem autorização — use
   uma montagem blindada/cabeada ou uma banda de teste licenciada.
4. **Relógio/temporização.** `clock_src`/`time_src = "internal"` funciona para uma única célula. Use
   `"external"` (10 MHz + PPS) ou `"gpsdo"` somente se a referência estiver instalada.
5. **Verifique o dispositivo** antes da subida:
   ```bash
   ./scripts/check_usrp.sh
   ```
   Isso faz ping no rádio e executa o `uhd_usrp_probe` (dentro da imagem da gNB, se o UHD não estiver no
   host).

---

## 3. Programação do SIM

O celular COTS precisa de um **SIM programável** (por exemplo, sysmoUSIM) gravado com um assinante que
exista em `oai-cn5g/database/oai_db.sql`. O banco já cadastra os IMSIs
`001010000000001`–`001010000000004`. Use o primeiro:

| Campo | Valor |
|---|---|
| IMSI | `001010000000001` |
| Ki (chave) | `fec86ba6eb707ed08905757b1bb44b8f` |
| OPc | `C42449363BBAD02B66D16BC975D77CC1` |
| MCC / MNC | `001` / `01` |
| DNN/APN | `oai` |

Programe com sua ferramenta de SIM (por exemplo, `pySim`):

```bash
pySim-prog.py -p 0 -t sysmoISIM-SJA2 \
  --mcc 001 --mnc 01 \
  --imsi 001010000000001 \
  --ki fec86ba6eb707ed08905757b1bb44b8f \
  --opc C42449363BBAD02B66D16BC975D77CC1
```

No celular, adicione uma APN chamada `oai` e selecione manualmente a PLMN `001/01`, se ela não for escolhida
automaticamente.

---

## 4. Configuração

- `experiments/usrp_x310/conf-gnb-usrp.conf` — gNB monolítica. Banda n78, 106 PRBs, SCS de 30 kHz,
  TDD 7DL+2UL. O bloco `RUs` seleciona o rádio (`sdr_addrs = "addr=192.168.40.2"`)
  e define os ganhos; **não** há bloco `rfsimulator`/`channelmod`.
- `NETWORK_INTERFACES.GNB_IPV4_ADDRESS_FOR_NG_AMF`/`_FOR_NGU` têm como padrão `192.168.70.129`,
  o endereço do host na bridge `oai-cn5g-public-net`. Confirme o seu:
  ```bash
  docker network inspect oai-cn5g-public-net -f '{{(index .IPAM.Config 0).Gateway}}'
  ```
  e atualize o arquivo de configuração se for diferente.
- `experiments/usrp_x310/gnb-docker-compose.yaml` — um único serviço `gnb`, rede do host,
  ulimits de `memlock`/`rtprio`, sem `--rfsim`. Ajuste os ganhos em tempo de execução via `USE_ADDITIONAL_OPTIONS`
  (por exemplo, `--RUs.[0].max_rxgain 105`).
- `experiments/usrp_x310/config.yaml` — valores de referência de rádio/UE/SIM.

---

## 5. Subida

```bash
./scripts/preflight_check.sh usrp-cots     # USRP-aware checks (device, buffers, UHD)
./scripts/up.sh usrp-cots                  # CN + gNB, waits for NG association to AMF
```

O `up.sh` inicia o 5GC, depois a gNB, e então aguarda a associação NG (N2) com o AMF. Ele
**não** aguarda um UE (o aparelho é externo). Assim que ele informar que a gNB está associada,
ligue o celular (ou alterne o modo avião) para que ele procure a rede e se conecte.

Verifique o status (detecta a topologia automaticamente):

```bash
./scripts/status.sh
```

No modo USRP, isso informa a associação NG da gNB e quaisquer eventos de registro de UE vistos nos
logs do AMF. "No UE attached yet" é informativo, e não uma falha — a conexão é conduzida pelo operador.

Confirme a conexão diretamente nos logs do AMF:

```bash
docker logs oai-amf 2>&1 | grep -iE 'Registration|5GMM-REGISTERED'
```

Em seguida, verifique o plano de dados a partir do celular (navegador / teste de velocidade / ping para um host público).

Pare tudo:

```bash
./scripts/down.sh                          # auto-detects usrp-cots
```

---

## 6. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| O `up.sh` nunca chega à associação NG | A gNB falhou ao inicializar o rádio | `docker logs oai-gnb`; verifique `check_usrp.sh`, ganhos, relógio |
| `No LO lock` / `RuntimeError` no log da gNB | Referência de relógio/temporização ausente | defina `clock_src/time_src = "internal"`, a menos que haja uma referência instalada |
| `U`/`O`/`L` repetidos no console da gNB | Underflow/overflow da USRP | aumente os buffers do host + MTU (§2); reduza a carga do host; verifique o enlace 10GbE |
| O `uhd_usrp_probe` não encontra o dispositivo | Problema de 10GbE/IP/MTU | verifique o IP da NIC do host na `/24` do rádio, MTU 9000, cabeamento |
| O celular mostra "sem serviço" / célula não encontrada | Banda/PLMN/ganho | confirme o suporte à banda n78, a PLMN 001/01, aumente o ganho de TX, verifique o caminho da antena |
| O celular vê a célula, mas não se registra | SIM divergente | confira IMSI/Ki/OPc com o `oai_db.sql`; verifique `docker logs oai-amf` |
| gNB no ar, mas o AMF nunca se associa | Endereço NG não roteável a partir do host | defina `GNB_IPV4_ADDRESS_FOR_NG_AMF` como o gateway da bridge do CN (§4) |

---

## 7. O que esta topologia não faz

- Não há teste rápido automatizado com ping/iperf (o `run_smoke_test.sh` tem como alvo o UE em contêiner do rfsim).
  Por enquanto, meça manualmente a partir do aparelho.
- Não há handover (célula única). Handover em rádio real exige vários rádios / mobilidade do COTS.
- Não há `oai-nr-ue` da OAI — por projeto, o UE é um aparelho COTS.
