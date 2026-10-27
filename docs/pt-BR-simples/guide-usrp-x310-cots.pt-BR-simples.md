# Guia do USRP X310 com UE comercial

> Tradução para o português em Linguagem Simples. O original em inglês é o [guide-usrp-x310-cots.md](../en/guide-usrp-x310-cots.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** guia
>
> **Leitura prévia:** [F00 — Quem cria as redes Docker](foundation-f00-docker-network-ownership.pt-BR-simples.md), [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md) e [F04 — Valores enumerados da configuração da OAI e tempos de rádio](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md)

Este guia cobre a topologia `usrp-cots`. Nela, uma gNB monolítica da OAI controla um rádio definido por software (SDR) **USRP X310**. Um **celular comercial (UE comercial, COTS)** se conecta pelo ar, no papel de UE. É a versão com rádio real dos experimentos de handover em rfsim. Não há rfsim, modelo de canal nem contêiner `oai-nr-ue`.

> **Escopo:** este guia cobre a subida de uma gNB com uma célula no X310 e a conferência da conexão do celular. Ele **não** inclui medição automática com ping ou iperf a partir do celular. Por enquanto, essa medição é manual, no próprio celular. Para handover com rádio real (F1 e N2, um rádio por computador), veja o [guia de handover distribuído com USRP](guide-usrp-distributed-handover.pt-BR-simples.md). A topologia de uma célula deste guia é a base para subir aquela.

Veja também: [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md) · [Pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md).

---

## 1. Topologia

```
            AMF / SMF / UPF (oai-cn5g, bridge Docker 192.168.70.0/26)
                              |
                       N2 (NGAP/SCTP)         rede do computador
                              |
                    gNB (contêiner, sem rfsim)
                              |
                       USRP X310  (10GbE, 192.168.40.2)
                              |  ~~ pelo ar (banda n78) ~~
                         celular comercial (chip SIM programável)
```

- O contêiner da gNB usa `network_mode: host`. Assim, ele controla o X310 pela placa de rede de 10 Gbit/s do computador e ainda alcança o núcleo 5G na bridge Docker.
- O UE é um celular real. Ele precisa de um chip SIM cadastrado na base de assinantes da OAI.

---

## 2. Montar o hardware

1. **Ligue o enlace de 10 Gbit/s.** Conecte a porta SFP+ de 10 Gbit/s do X310 a uma placa de rede de 10 Gbit/s do computador. Dê à placa do computador um endereço fixo na mesma rede `/24` do rádio. Exemplo: computador em `192.168.40.1`, X310 em `192.168.40.2`.
2. **Configure quadros jumbo e buffers.** O X310 precisa deles para atingir a vazão necessária. Essas configurações valem para o computador inteiro. Faça-as no **computador**, e não no Compose:
   ```bash
   sudo ip link set <interface-10gbe> mtu 9000
   sudo sysctl -w net.core.rmem_max=33554432
   sudo sysctl -w net.core.wmem_max=33554432
   ```
3. **Monte a parte de radiofrequência.** Use as portas de transmissão e recepção da banda n78 (3,6 GHz), com antenas adequadas ou com cabo e atenuador.

   > **ATENÇÃO:** Nunca transmita em espectro licenciado sem autorização. Use uma montagem blindada ou com cabo, ou uma banda de teste licenciada.

4. **Escolha a referência de relógio.** Com uma célula, `clock_src`/`time_src = "internal"` funciona. Só use `"external"` (10 MHz e PPS) ou `"gpsdo"` se a referência estiver instalada.
5. **Confira o rádio antes de subir:**
   ```bash
   ./scripts/check_usrp.sh
   ```
   O script faz ping no rádio e executa o `uhd_usrp_probe`. Se o UHD não estiver instalado no computador, ele usa o UHD da imagem da gNB.

---

## 3. Programar o chip SIM

O celular precisa de um **chip SIM programável** (por exemplo, sysmoUSIM). Grave nele um assinante que exista em `oai-cn5g/database/oai_db.sql`. A base já cadastra os IMSIs `001010000000001` a `001010000000004`. Use o primeiro:

| Campo | Valor |
|---|---|
| IMSI | `001010000000001` |
| Ki (chave) | `fec86ba6eb707ed08905757b1bb44b8f` |
| OPc | `C42449363BBAD02B66D16BC975D77CC1` |
| MCC / MNC | `001` / `01` |
| DNN/APN | `oai` |

Programe com a sua ferramenta de SIM (por exemplo, o `pySim`):

```bash
pySim-prog.py -p 0 -t sysmoISIM-SJA2 \
  --mcc 001 --mnc 01 \
  --imsi 001010000000001 \
  --ki fec86ba6eb707ed08905757b1bb44b8f \
  --opc C42449363BBAD02B66D16BC975D77CC1
```

No celular, crie um APN chamado `oai`. Se o celular não escolher a rede sozinho, escolha a PLMN `001/01` à mão.

---

## 4. Configuração

- `experiments/usrp_x310/conf-gnb-usrp.conf`: gNB monolítica, banda n78, 106 PRBs, espaçamento entre subportadoras de 30 kHz, TDD com 7 slots de descida e 2 de subida. O bloco `RUs` escolhe o rádio (`sdr_addrs = "addr=192.168.40.2"`) e define os ganhos. **Não** há bloco `rfsimulator` nem `channelmod`.
- `NETWORK_INTERFACES.GNB_IPV4_ADDRESS_FOR_NG_AMF` e `_FOR_NGU` usam, por padrão, `192.168.70.129`. Esse é o endereço do computador na bridge `oai-cn5g-public-net`. Confira o seu:
  ```bash
  docker network inspect oai-cn5g-public-net -f '{{(index .IPAM.Config 0).Gateway}}'
  ```
  Se for diferente, atualize o arquivo de configuração.
- `experiments/usrp_x310/gnb-docker-compose.yaml`: um único serviço `gnb`, com a rede do computador, limites `memlock`/`rtprio` e sem `--rfsim`. Ajuste os ganhos na hora de subir, com `USE_ADDITIONAL_OPTIONS`. Exemplo: `--RUs.[0].max_rxgain 105`.
- `experiments/usrp_x310/config.yaml`: valores de referência do rádio, do UE e do chip SIM.

---

## 5. Subir

```bash
./scripts/preflight_check.sh usrp-cots     # verificações próprias do USRP (rádio, buffers, UHD)
./scripts/up.sh usrp-cots                  # núcleo 5G e gNB; espera a associação NG com o AMF
```

O `up.sh` sobe o núcleo 5G e depois a gNB. Em seguida, ele espera a associação NG (N2) com o AMF. Ele **não** espera nenhum UE, porque o celular é externo. Quando o script mostrar que a gNB está associada, ligue o celular ou alterne o modo avião. Assim, o celular procura a rede e se conecta.

Para ver o estado, use o comando abaixo. Ele descobre a topologia sozinho:

```bash
./scripts/status.sh
```

No modo USRP, o script mostra a associação NG da gNB e os registros de UE encontrados nos logs do AMF. A mensagem "No UE attached yet" só informa. Ela não é uma falha, porque quem conecta o celular é o operador.

Para confirmar a conexão diretamente nos logs do AMF, use:

```bash
docker logs oai-amf 2>&1 | grep -iE 'Registration|5GMM-REGISTERED'
```

Depois, confira o plano de usuário no celular: abra o navegador, faça um teste de velocidade ou um ping para um endereço público.

Para parar tudo, use:

```bash
./scripts/down.sh                          # descobre a topologia usrp-cots sozinho
```

---

## 6. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| O `up.sh` nunca chega à associação NG. | A gNB caiu ao iniciar o rádio. | Veja `docker logs oai-gnb`. Confira o `check_usrp.sh`, os ganhos e o relógio. |
| `No LO lock` ou `RuntimeError` no log da gNB | Falta a referência de relógio. | Use `clock_src/time_src = "internal"`, a menos que haja uma referência instalada. |
| `U`, `O` ou `L` repetidos no console da gNB | Falta ou excesso de amostras no USRP | Aumente os buffers e o MTU do computador (seção 2). Reduza a carga do computador. Confira o enlace de 10 Gbit/s. |
| O `uhd_usrp_probe` não encontra o rádio. | Problema no enlace, no IP ou no MTU | Confira se a placa do computador está na mesma `/24` do rádio, com MTU 9000. Confira os cabos. |
| O celular fica sem serviço ou não acha a célula. | Banda, PLMN ou ganho | Confirme que o celular aceita a banda n78 e a PLMN 001/01. Aumente o ganho de transmissão. Confira o caminho da antena. |
| O celular vê a célula, mas não se registra. | Dados do chip SIM não conferem. | Compare o IMSI, o Ki e o OPc com o `oai_db.sql`. Veja `docker logs oai-amf`. |
| A gNB sobe, mas o AMF nunca se associa. | O endereço NG não tem rota no computador. | Defina `GNB_IPV4_ADDRESS_FOR_NG_AMF` como o gateway da bridge do núcleo 5G (seção 4). |

---

## 7. O que esta topologia não faz

- Não tem teste rápido automático com ping ou iperf. O `run_smoke_test.sh` usa o UE em contêiner do rfsim. Por enquanto, meça à mão, no celular.
- Não tem handover, porque há uma só célula. O handover com rádio real precisa de vários rádios e de mobilidade do UE comercial.
- Não tem o `oai-nr-ue` da OAI. O UE é um celular comercial, por projeto.
