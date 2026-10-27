# Handoff: `fsnobre/oai-rfsim-handover-testbed`

> Tradução para o português. O original em inglês é o [handoff-xapp-integration.md](handoff-xapp-integration.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Handoff
>
> **Leitura obrigatória:** [guia de handover N2](guide-n2-handover.pt-BR.md), [resultados de referência](report-baseline-results.pt-BR.md) e [histórico de desenvolvimento](record-development-history.pt-BR.md)

> Documento de contexto para o chat de pesquisa do artigo_doc_1. Escrito para que uma sessão
> sem acesso a este repositório consiga raciocinar sobre a integração do
> método de handover do artigo_doc_1 a este testbed como uma xApp.

## O que é este repositório

Um testbed de handover 5G SA da OAI (OpenAirInterface), de nível de pesquisa e totalmente
conteinerizado. Os experimentos de handover rodam no RFsimulator — um único host, sem hardware
de rádio, tudo em Docker Compose (há também um caminho opcional com rádio real USRP X310
e UE COTS; o trabalho com xApp descrito abaixo tem como alvo o fluxo em RFsim). Ele
automatiza os experimentos de handover de ponta a ponta:
subida da pilha, verificações de prontidão, disparo do handover, medição da interrupção
com ping, iperf TCP/UDP simultâneo opcional, coleta de logs e agregação estatística
de execuções repetidas. Seu
roteiro declarado (README) é: **"DRL, GNN, and xApp integration are planned for
future milestones"** (integração com DRL, GNN e xApp está planejada para marcos futuros) — ele foi construído para, no futuro, abrigar exatamente o tipo de
método que estamos desenvolvendo.

## Experimentos suportados

| Experimento | Topologia | Mecanismo de disparo | Versão da OAI |
|---|---|---|---|
| Handover F1 (intra-gNB) | 1 CU + 2 DUs | Telnet da CU: `ci trigger_f1_ho` | v2.4.0 / develop |
| Handover N2 (inter-gNB) | 2 gNBs monolíticas (`oai-gnb0`/`oai-gnb1`) **ou** 2 pares CU+DU | Telnet da gNB de origem: `ci trigger_n2_ho <target_pci>,<ue_rrc_id>` | v2.4.0 |

Todos compartilham um 5GC da OAI (AMF/SMF/UPF/oai-ext-dn, imagens `develop`) e um UE
RFsim. **O UE é o servidor rfsim** (porta 4043), para que várias gNBs possam se conectar ao
mesmo UE — isso é necessário para o handover em rfsim, já que o UE rfsim da OAI
não consegue disparar o handover por relatórios de medição; o handover é sempre
disparado manual/programaticamente pelo telnet da gNB.

## Arranjo de rede (bridge Docker `oai-cn5g-public-net`, 192.168.70.128/26)

- AMF `192.168.70.132`, destino de ping no oai-ext-dn `192.168.71.135`
- F1: CU `.150`, oai-du0 `.171`, oai-du1 `.172`
- N2 monolítica: oai-gnb0 `.160` (PCI 0, gNB_ID 0xe00), oai-gnb1 `.161` (PCI 1, 0xe01), telnet em `:9090`
- N2 CU+DU: oai-cu0 `.150`, oai-cu1 `.155`, oai-du0 `.171`, oai-du1 `.172`
- UE `oai-nr-ue` `.181`, interface da sessão PDU `oaitun_ue1`, IP `10.0.0.2`, telnet do UE `:8091` (módulo `ciUE`)
- Banda 78, 106 PRBs, SCS de 30 kHz; SSB ARFCN da oai-gnb0 641280, da oai-gnb1 643296; relações de vizinhança declaradas via `neighbour-config.conf`, incluído no arquivo de configuração de cada gNB

## Principais interfaces operacionais (primitivas de atuação/observação)

- **Disparar o handover:** `./scripts/trigger_handover.sh` (detecta a topologia automaticamente) ou, diretamente: `echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090`
- **Consultar UEs conectados + IDs RRC:** `echo "ue" | nc -N <gnb_ip> 9090`
- **Modelos de canal:** os blocos de configuração de `rfsimu_channel_ue0/ue1` estão presentes, mas a ativação do `chanmod` em tempo de execução pela linha de comando está desativada na imagem validada atualmente, porque essa opção é rejeitada. Reative o controle de modelo de canal somente depois de validar a sintaxe da opção na imagem da OAI selecionada.
- **Ciclo de vida:** `./scripts/up.sh {f1|n2-monolithic|n2-cu-du}`, `down.sh`, `status.sh`, `preflight_check.sh` / `poststart_check.sh`
- **Experimentos:** `./scripts/run_smoke_test.sh <topologia>`, `RUNS=5 ./scripts/run_repeated_smoke_tests.sh <topologia>`; padrões em `experiments/n2_handover/config.yaml`, todos substituíveis por variáveis de ambiente (`N2_TARGET_PCI`, `N2_UE_RRC_ID`, `PING_TARGET`, `IPERF_ENABLED`, `IPERF_MODE` etc.)

## Pipeline de medição e referência

Cada execução produz um diretório com carimbo de tempo em `results/runs/`, com `events.csv`
(linha do tempo, incluindo `n2_handover_trigger_start`), `ping.csv`, `ping_summary.json`
(`estimated_interruption_ms`, `first_ping_after_handover_ms`, perda, estatísticas de
RTT), `iperf_summary.json` opcional (vazão, jitter, perda UDP, retransmissões
TCP), `summary.json` (aprovado/reprovado) e os logs completos dos contêineres. As execuções repetidas
agregam as métricas de ping e as de iperf disponíveis em `results/repeated/`. **Referência F1
validada: interrupção média de 207,07 ms, 0,0% de perda em 5 execuções**
(`docs/report-baseline-results.md`).

## O que ele NÃO tem (lacunas para o trabalho com xApp)

1. **Não há RIC, nem E2, nem camada de xApp.** Não há RIC FlexRIC/OSC, nem bloco `e2_agent`
   em nenhum arquivo de configuração de gNB, nem modelos de serviço E2SM. O disparo de HO é o
   shim CI proprietário da OAI via telnet, e não o E2SM-RC.
2. **Imagens padrão** (`oaisoftwarealliance/oai-gnb:develop`/`v2.4.0`) — é preciso
   verificar se incluem o agente E2 (a OAI principal o compila com
   `--build-e2`); no pior caso, basta recompilar uma imagem. A OAI publica uma imagem oficial
   `oai-flexric` para o lado do RIC.
3. **Não há envio de relatórios de medição a um controlador** — hoje a observação é feita
   por raspagem de telnet/logs; uma xApp real precisa do E2SM-KPM ou dos SMs personalizados do FlexRIC
   (MAC/RLC/PDCP) para obter atributos por UE.
4. **Um único UE**, e o padrão de UE como servidor rfsim não se generaliza para
   muitos UEs × muitas gNBs — a maior restrição estrutural, se o método precisar de
   estado de vários UEs (relevante para abordagens com GNN).

## Avaliação de integração acordada

Veredito: **utilizável como o futuro testbed da xApp** — ele resolve o ambiente, a
atuação e o rigor de medição; só é preciso acrescentar a camada do RIC (2–3
contêineres na rede Docker existente + mudanças nos arquivos de configuração). Caminho recomendado em fases,
tendo como alvo a topologia **N2 monolítica** (dois nós E2 limpos; o HO inter-gNB
é o que uma xApp de HO da O-RAN controla, semanticamente):

- **Fase 0 (sem E2):** executar o método do artigo_doc_1 como um contêiner controlador
  "tipo xApp" na mesma rede — observar via
  telnet/logs/channelmod e atuar pela primitiva telnet existente `trigger_n2_ho`.
  Valida imediatamente a lógica de decisão de ponta a ponta, reutilizando
  toda a automação de medição e a referência existente como ponto de comparação.
- **Fase 1:** adicionar o FlexRIC + `e2_agent = { near_ric_ip_addr = ...; sm_dir = ... }`
  nos arquivos de configuração das gNBs; o método passa a ser uma xApp real que consome indicações do E2SM-KPM/SMs
  personalizados; manter a atuação por telnet como ponte.
- **Fase 2:** passar a atuação para o controle de handover do E2SM-RC (a peça menos madura
  na OAI/FlexRIC — verifique antes que qualquer afirmação de artigo dependa dela; o Near-RT RIC da
  OSC é a alternativa mais pesada e conforme aos padrões).

Dois riscos a delimitar antes de comprometer o método com este testbed: a
**restrição de múltiplos UEs no rfsim** e a **maturidade do controle de HO via E2SM-RC** na
versão da OAI fixada.

## Mapa do repositório (arquivos mais relevantes)

```
experiments/n2_handover/config.yaml          # N2 experiment defaults (PCIs, telnet IPs, ping params)
experiments/n2_handover/topology_a_monolithic/   # gnb0/gnb1 confs + compose + neighbour-config
experiments/n2_handover/topology_b_cu_du/        # cu0/cu1/du0/du1 confs + compose
gnb-docker-compose.yaml                      # F1 topology (CU + 2 DU + UE)
oai-cn5g/                                    # 5GC compose + conf + subscriber DB
scripts/trigger_handover.sh, run_smoke_test.sh, run_repeated_smoke_tests.sh, lib.sh
tools/parse_ping.py                          # interruption-time computation
docs/guide-n2-handover.md, report-baseline-results.md, record-development-history.md
```

## Observações para o chat que recebe este handoff

- Trate o **controlador da Fase 0** como a primeira entrega concreta
  de integração.
- Determine cedo se o método do artigo_doc_1 exige **observações de vários
  UEs** — essa é a única restrição aqui que não pode ser resolvida apenas com
  configuração.
