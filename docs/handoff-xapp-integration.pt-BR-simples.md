# Passagem de contexto: `fsnobre/oai-rfsim-handover-testbed`

> Tradução para o português em Linguagem Simples. O original em inglês é o [handoff-xapp-integration.md](handoff-xapp-integration.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** passagem de contexto (*handoff*)
>
> **Leitura prévia:** [guia do handover N2](guide-n2-handover.pt-BR-simples.md), [resultado de referência](report-baseline-results.pt-BR-simples.md) e [histórico do desenvolvimento](record-development-history.pt-BR-simples.md)

> Documento de contexto para a conversa de pesquisa do artigo_doc_1. Ele foi escrito para uma sessão sem acesso a este repositório. Com ele, essa sessão consegue avaliar como integrar o método de handover do artigo_doc_1 a este testbed, na forma de um xApp.

## O que é este repositório

É um testbed de handover 5G SA da OpenAirInterface (OAI), feito para pesquisa e todo em contêineres. Os experimentos de handover rodam no simulador de rádio da OAI (rfsim): um único computador, sem rádio, tudo em Docker Compose. Há também um caminho opcional com rádio real (USRP X310) e UE comercial. O trabalho com xApp descrito abaixo usa o caminho do rfsim.

O testbed automatiza os experimentos de handover do começo ao fim:

- subida da pilha;
- espera pela prontidão de cada camada;
- comando do handover;
- medição da interrupção com ping;
- iperf TCP ou UDP opcional, ao mesmo tempo;
- coleta de logs;
- agregação estatística de execuções repetidas.

O plano declarado no README é: **"DRL, GNN e integração com xApps estão previstos para marcos futuros"**. O testbed foi feito para receber, um dia, exatamente o tipo de método que estamos desenvolvendo.

## Experimentos disponíveis

| Experimento | Topologia | Como o handover é comandado | Versão da OAI |
|---|---|---|---|
| Handover F1 (intra-gNB) | 1 CU e 2 DUs | Telnet na CU: `ci trigger_f1_ho` | v2.4.0 / develop |
| Handover N2 (inter-gNB) | 2 gNBs monolíticas (`oai-gnb0`/`oai-gnb1`) **ou** 2 pares CU+DU | Telnet na gNB de origem: `ci trigger_n2_ho <pci_de_destino>,<id_rrc_do_ue>` | v2.4.0 |

Todos usam o mesmo núcleo 5G da OAI (AMF, SMF, UPF e `oai-ext-dn`, com imagens `develop`) e o mesmo UE em rfsim. **O UE é o servidor do rfsim** (porta 4043). Assim, várias gNBs se conectam ao mesmo UE. Isso é necessário para o handover no rfsim, porque o UE da OAI em rfsim não consegue iniciar o handover por relatórios de medição. O handover é sempre comandado à mão ou por programa, pelo Telnet da gNB.

## Organização da rede (bridge Docker `oai-cn5g-public-net`, 192.168.70.128/26)

- AMF em `192.168.70.132`. Destino do ping no `oai-ext-dn`: `192.168.71.135`.
- F1: CU em `.150`, oai-du0 em `.171`, oai-du1 em `.172`.
- N2 monolítico: oai-gnb0 em `.160` (PCI 0, gNB_ID 0xe00), oai-gnb1 em `.161` (PCI 1, 0xe01). Telnet na porta `:9090`.
- N2 CU+DU: oai-cu0 em `.150`, oai-cu1 em `.155`, oai-du0 em `.171`, oai-du1 em `.172`.
- UE `oai-nr-ue` em `.181`. Interface da sessão PDU: `oaitun_ue1`, com IP `10.0.0.2`. Telnet do UE na porta `:8091` (módulo `ciUE`).
- Banda 78, 106 PRBs, espaçamento entre subportadoras de 30 kHz. SSB ARFCN da oai-gnb0: 641280. Da oai-gnb1: 643296. As relações de vizinhança ficam no `neighbour-config.conf`, incluído no arquivo de configuração de cada gNB.

## Interfaces principais de operação (o que dá para comandar e observar)

- **Comandar o handover:** `./scripts/trigger_handover.sh` (descobre a topologia sozinho) ou, direto, `echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090`.
- **Consultar os UEs conectados e os identificadores RRC:** `echo "ue" | nc -N <ip_da_gnb> 9090`.
- **Modelos de canal:** os blocos de configuração `rfsimu_channel_ue0/ue1` existem. Mas a ativação do `chanmod` pela linha de comando está desligada na imagem validada, porque ela rejeita essa opção. Só ligue de novo o controle do modelo de canal depois de validar a sintaxe da opção na imagem da OAI escolhida.
- **Ciclo de vida:** `./scripts/up.sh {f1|n2-monolithic|n2-cu-du}`, `down.sh`, `status.sh`, `preflight_check.sh` e `poststart_check.sh`.
- **Experimentos:** `./scripts/run_smoke_test.sh <topologia>` e `RUNS=5 ./scripts/run_repeated_smoke_tests.sh <topologia>`. Os valores padrão ficam em `experiments/n2_handover/config.yaml`. Todos podem ser trocados por variáveis de ambiente (`N2_TARGET_PCI`, `N2_UE_RRC_ID`, `PING_TARGET`, `IPERF_ENABLED`, `IPERF_MODE` etc.).

## Pipeline de medição e resultado de referência

Cada execução cria uma pasta com data e hora em `results/runs/`. A pasta tem:

- `events.csv`: linha do tempo, inclusive `n2_handover_trigger_start`;
- `ping.csv`;
- `ping_summary.json`: `estimated_interruption_ms`, `first_ping_after_handover_ms`, perda e estatísticas de RTT;
- `iperf_summary.json`, opcional: vazão, jitter, perda UDP e retransmissões TCP;
- `summary.json`: aprovação ou falha;
- os logs completos dos contêineres.

As execuções repetidas juntam as métricas de ping e de iperf em `results/repeated/`. **Resultado de referência validado do F1: interrupção média de 207,07 ms e 0,0% de perda em 5 execuções** (`docs/report-baseline-results.md`).

## O que o testbed NÃO tem (lacunas para o trabalho com xApp)

1. **Não há RIC, E2 nem camada de xApp.** Não há FlexRIC nem RIC da OSC. Nenhum arquivo de configuração de gNB tem o bloco `e2_agent`. Não há modelos de serviço E2SM. O comando de handover usa o atalho Telnet próprio da OAI, e não o E2SM-RC.
2. **As imagens são as oficiais** (`oaisoftwarealliance/oai-gnb:develop`/`v2.4.0`). É preciso conferir se elas incluem o agente E2. A OAI principal o compila com `--build-e2`. No pior caso, basta recompilar uma imagem. A OAI publica uma imagem oficial `oai-flexric` para o lado do RIC.
3. **Não há relatórios de medição para um controlador.** Hoje, a observação é feita pelo Telnet e pela leitura dos logs. Um xApp real precisa do E2SM-KPM ou dos modelos de serviço próprios do FlexRIC (MAC, RLC e PDCP) para ter dados por UE.
4. **Há um só UE.** O padrão do UE como servidor do rfsim não funciona com muitos UEs e muitas gNBs. Essa é a maior limitação estrutural, se o método precisar do estado de vários UEs. Isso é relevante para abordagens com redes neurais em grafos (GNN).

## Avaliação de integração acordada

Conclusão: **o testbed serve como futuro testbed de xApps.** Ele já resolve o ambiente, o comando das ações e o rigor da medição. Só falta acrescentar a camada do RIC: de 2 a 3 contêineres na rede Docker atual e mudanças nos arquivos de configuração.

O caminho recomendado tem fases e usa a topologia **N2 monolítica**. Motivos: ela tem dois nós E2 bem separados, e o handover inter-gNB é o que um xApp de handover do Open RAN controla.

- **Fase 0 (sem E2):** rodar o método do artigo_doc_1 como um contêiner controlador "parecido com um xApp", na mesma rede. Ele observa pelo Telnet, pelos logs e pelo `channelmod`. Ele age pelo comando Telnet `trigger_n2_ho` que já existe. Essa fase valida a lógica de decisão de ponta a ponta na hora. Ela reaproveita todo o sistema de medição e usa o resultado de referência atual como base de comparação.
- **Fase 1:** acrescentar o FlexRIC e o bloco `e2_agent = { near_ric_ip_addr = ...; sm_dir = ... }` nos arquivos de configuração das gNBs. O método vira um xApp real, que recebe indicações do E2SM-KPM ou dos modelos de serviço próprios. O comando pelo Telnet continua como ponte.
- **Fase 2:** passar o comando das ações para o controle de handover do E2SM-RC. Essa é a parte menos madura da OAI e do FlexRIC. Confira-a antes de usar qualquer afirmação dela em um artigo. O Near-RT RIC da OSC é a alternativa mais pesada e mais aderente às normas.

Antes de levar o método para este testbed, avalie dois riscos:

- a **limitação de vários UEs no rfsim**;
- a **maturidade do controle de handover pelo E2SM-RC** na versão fixada da OAI.

## Mapa do repositório (arquivos mais relevantes)

```
experiments/n2_handover/config.yaml              # padrões do experimento N2 (PCIs, IPs do Telnet, parâmetros do ping)
experiments/n2_handover/topology_a_monolithic/   # confs da gnb0/gnb1, compose e neighbour-config
experiments/n2_handover/topology_b_cu_du/        # confs da cu0/cu1/du0/du1 e compose
gnb-docker-compose.yaml                          # topologia F1 (CU, 2 DUs e UE)
oai-cn5g/                                        # compose, conf e base de assinantes do núcleo 5G
scripts/trigger_handover.sh, run_smoke_test.sh, run_repeated_smoke_tests.sh, lib.sh
tools/parse_ping.py                              # cálculo do tempo de interrupção
docs/guide-n2-handover.md, report-baseline-results.md, record-development-history.md
```

## Notas para a conversa que recebe este contexto

- Trate o **controlador da fase 0** como a primeira entrega concreta da integração.
- Descubra cedo se o método do artigo_doc_1 precisa de **observações de vários UEs**. Essa é a única limitação daqui que não se resolve só com configuração.
