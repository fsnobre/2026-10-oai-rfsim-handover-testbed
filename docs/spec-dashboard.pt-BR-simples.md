# Especificação do painel web: monitor do testbed de handover da OAI em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [spec-dashboard.md](spec-dashboard.md). Se houver diferença entre os dois, vale o original.

## Visão geral

O painel web é um painel feito sob medida para acompanhar e controlar, em tempo real, o testbed de handover 5G da OAI em rfsim. Ele se inspira no painel do OAIBOX™ (da Allbesmart), adaptado à nossa arquitetura em rfsim, com divisão CU/DU e handover.

Material de referência em `docs/OAIBOX_info/`: capturas de tela e um PDF do produto comercial OAIBOX.

## Arquitetura

### Topologia do testbed (o que o painel acompanha)

```
                    ┌─────────┐
                    │  CN5G   │ (AMF, SMF, UPF, NRF etc.)
                    └────┬────┘
                         │ N2/N3
                    ┌────┴────┐
                    │   CU    │ (gNB-CU, Telnet na porta 9090)
                    ├────┬────┤
                    │ F1 │ F1 │
               ┌────┴──┐ ┌──┴────┐
               │  DU0  │ │  DU1  │ (cada uma com PCI e ARFCN próprios)
               └───┬───┘ └───┬───┘
                   │ rfsim   │ rfsim
               ┌───┴─────────┴───┐
               │       UE        │ (servidor rfsim, OAI NR-UE)
               └─────────────────┘
```

Todos os componentes rodam como contêineres Docker, pelo docker-compose.

### Pilha do painel

```
┌─────────────────────────────────────────────┐
│              Frontend React                  │
│  (Recharts, Tailwind, cliente WebSocket)     │
├─────────────────────────────────────────────┤
│              Backend FastAPI                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Consulta │ │ Monitor  │ │ Leitor de    │ │
│  │ Telnet   │ │ Docker   │ │ logs (HO)    │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │ Leitor   │ │ Difusão por WebSocket    │  │
│  │ de conf. │ │ (indicadores ao vivo)    │  │
│  └──────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────┤
│         Docker Engine / contêineres          │
│  (CN5G, CU, DU0, DU1, UE, oai-ext-dn)        │
└─────────────────────────────────────────────┘
```

### Estrutura de pastas (neste repositório)

```
dashboard/
├── backend/
│   ├── main.py                  # ponto de entrada do app FastAPI
│   ├── config.py                # configuração do painel (portas, nomes dos contêineres)
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── telnet_poller.py     # cliente Telnet assíncrono para estatísticas MAC/RRC da gNB
│   │   ├── docker_monitor.py    # consulta do estado dos contêineres pelo SDK do Docker
│   │   ├── log_watcher.py       # leitura dos logs do Docker: eventos de HO e fluxo de mensagens
│   │   └── config_parser.py     # leitor dos arquivos .conf da OAI (CU, DU0, DU1)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── kpi.py               # modelos Pydantic dos indicadores do UE
│   │   ├── handover.py          # modelos de evento e de duração de HO
│   │   └── topology.py          # modelo do estado da topologia da rede
│   ├── api/
│   │   ├── __init__.py
│   │   ├── containers.py        # endpoints REST: ciclo de vida dos contêineres
│   │   ├── config.py            # endpoints REST: ler e gravar as configurações da OAI
│   │   ├── handover.py          # endpoints REST: comandar HO, histórico de HO
│   │   └── websocket.py         # endpoint WebSocket: indicadores e eventos ao vivo
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── TopBar.jsx
│   │   │   │   └── NavTabs.jsx
│   │   │   ├── topology/
│   │   │   │   └── TopologyDiagram.jsx    # diagrama SVG da rede com estado ao vivo
│   │   │   ├── kpi/
│   │   │   │   ├── KpiCard.jsx            # cartão de resumo (valor, mínimo, máximo, média)
│   │   │   │   └── TimeSeriesChart.jsx    # gráfico de linha do Recharts
│   │   │   ├── handover/
│   │   │   │   ├── HandoverTimeline.jsx   # linha do tempo dos eventos
│   │   │   │   ├── HandoverDuration.jsx   # tabela de durações
│   │   │   │   └── HandoverTrigger.jsx    # botão de comando
│   │   │   ├── containers/
│   │   │   │   └── ContainerControl.jsx   # Start/Stop/Restart de cada contêiner
│   │   │   ├── logs/
│   │   │   │   ├── MessageFlow.jsx        # tabela do fluxo de mensagens 5G SA
│   │   │   │   └── RawLogs.jsx            # visor dos logs brutos da gNB
│   │   │   └── config/
│   │   │       └── GnbConfig.jsx          # exibição e edição da configuração
│   │   ├── pages/
│   │   │   ├── Overview.jsx
│   │   │   ├── GnbPage.jsx
│   │   │   ├── UePage.jsx
│   │   │   └── HandoverPage.jsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   └── useKpiHistory.js
│   │   ├── utils/
│   │   │   └── constants.js
│   │   └── App.jsx
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.dashboard.yml   # só os serviços do painel
└── README.md
```

## Fontes de dados

### 1. Interface Telnet da gNB (principal fonte de indicadores)

A gNB da OAI abre um servidor Telnet na porta 9090, quando compilada com `--build-lib telnetsrv`. O Telnet da CU fornece estatísticas de RRC. O Telnet das DUs fornece estatísticas de MAC e de PHY.

**Intervalo de consulta:** cerca de 1 segundo

**Comandos principais e padrões de saída esperados:**

```
# estatísticas de MAC (em cada DU)
mac stats → por RNTI: bytes de DLSCH/ULSCH, MCS, BLER, CQI, rodadas, retransmissões

# estatísticas de RRC (CU)
rrc stats → contextos dos UEs, RNTI, estado, DU associada

# comando de handover (CU)
handover → comanda HO em rodízio entre as DUs
handover <cu-ue-id> → comanda HO de um UE específico
```

**Indicadores que dá para extrair de cada UE (em cada consulta):**

- MCS de descida e de subida (do escalonador MAC)
- CQI (informado pelo UE, pelo MAC)
- BLER de descida e de subida (pelo HARQ)
- vazão de descida e de subida (diferença de bytes / diferença de tempo)
- PHR (MAC CE)
- rodadas e retransmissões HARQ
- DU atual (do contexto RRC)

### 2. API do Docker

**Intervalo de consulta:** cerca de 5 segundos

**Contêineres acompanhados** (nomes do docker-compose):

- serviços do núcleo 5G: oai-amf, oai-smf, oai-upf, oai-nrf (e outros)
- RAN: oai-cu, oai-du0, oai-du1
- UE: oai-nr-ue
- externo: oai-ext-dn

**Em cada contêiner:** estado (rodando, parado, reiniciando), health check e tempo no ar

### 3. Leitor de logs (eventos de handover)

**Fonte:** `docker logs --follow oai-cu`

**Padrões a detectar:**

```python
# pedido de handover enviado
r"\[NR_RRC\].*HandoverRequest.*RNTI\s+(0x[0-9a-fA-F]+).*target.*DU\s+(\d+)"

# pedido de handover confirmado
r"\[NR_RRC\].*HandoverRequestAcknowledge.*RNTI\s+(0x[0-9a-fA-F]+)"

# RRC Reconfiguration concluída (HO bem-sucedido)
r"\[NR_RRC\].*RRCReconfigurationComplete.*RNTI\s+(0x[0-9a-fA-F]+)"

# liberação do contexto do UE (limpeza depois do HO)
r"\[NR_RRC\].*UEContextRelease.*RNTI\s+(0x[0-9a-fA-F]+)"

# mensagens NGAP/NAS gerais, para a tabela do fluxo de mensagens
r"\[(NGAP|NAS)\].*"
```

**Duração do handover:** horário(RRCReconfigurationComplete) − horário(HandoverRequest)

### 4. Leitor dos arquivos de configuração

**Arquivos a ler, por topologia:**

O painel não pode supor uma única organização fixa das configurações da OAI. Ele deve detectar a topologia ativa, ou recebê-la por configuração, e então ler os arquivos Compose e de configuração correspondentes.

### Topologia de handover F1: `f1`

Arquivos principais:

* Compose da RAN: `gnb-docker-compose.yaml`
* configuração da CU: `conf-cu.conf`
* configuração base das DUs: `conf-du.conf`
* configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-cu`
* `oai-du0`
* `oai-du1`
* `oai-nr-ue`
* contêineres do núcleo 5G, de `oai-cn5g/docker-compose.yaml`: `oai-amf`, `oai-smf`, `oai-upf`, `oai-nrf`, `oai-udr`, `oai-udm`, `oai-ausf`, `mysql` e `oai-ext-dn`

Notas importantes:

* A `oai-du0` e a `oai-du1` montam o mesmo `conf-du.conf`.
* A `oai-du1` recebe ajustes próprios da topologia pelo `USE_ADDITIONAL_OPTIONS` do `gnb-docker-compose.yaml`: identificador da DU, identificador da célula, PCI, frequência do SSB, PointA, bitmap do SSB e endereço F1 local.
* O Telnet da CU fica em `192.168.70.150:9090`.
* O Telnet das DUs não está ligado no arquivo Compose atual do F1.
* O comando de handover F1 é `ci trigger_f1_ho`.

### Topologia N2 monolítica: `n2-monolithic`

Arquivos principais:

* Compose da RAN: `experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml`
* configuração da gNB de origem: `experiments/n2_handover/topology_a_monolithic/conf-gnb0.conf`
* configuração da gNB de destino: `experiments/n2_handover/topology_a_monolithic/conf-gnb1.conf`
* configuração das vizinhas: `experiments/n2_handover/topology_a_monolithic/neighbour-config.conf`
* configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-gnb0`
* `oai-gnb1`
* `oai-nr-ue`
* contêineres do núcleo 5G, de `oai-cn5g/docker-compose.yaml`

Notas importantes:

* A `oai-gnb0` e a `oai-gnb1` são gNBs monolíticas completas.
* As duas gNBs abrem o Telnet nos endereços de escuta configurados.
* O comando de handover N2 é `ci trigger_n2_ho <pci_de_destino>,<id_rrc_do_ue>`.

### Topologia N2 CU/DU: `n2-cu-du`

Arquivos principais:

* Compose da RAN: `experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml`
* configuração da CU de origem: `experiments/n2_handover/topology_b_cu_du/conf-cu0.conf`
* configuração da DU de origem: `experiments/n2_handover/topology_b_cu_du/conf-du0.conf`
* configuração da CU de destino: `experiments/n2_handover/topology_b_cu_du/conf-cu1.conf`
* configuração da DU de destino: `experiments/n2_handover/topology_b_cu_du/conf-du1.conf`
* configuração das vizinhas: `experiments/n2_handover/topology_b_cu_du/neighbour-config.conf`
* configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-cu0`
* `oai-du0`
* `oai-cu1`
* `oai-du1`
* `oai-nr-ue`
* contêineres do núcleo 5G, de `oai-cn5g/docker-compose.yaml`

Notas importantes:

* Esta topologia tem dois pares CU/DU.
* O Telnet de cada CU e DU é configurado no arquivo Compose.
* No N2 CU/DU, o endpoint Telnet de origem deve seguir a mesma lógica do `scripts/trigger_handover.sh`.
* O comando de handover N2 é `ci trigger_n2_ho <pci_de_destino>,<id_rrc_do_ue>`.

### Requisitos do leitor de configuração

O leitor de configuração deve retornar um modelo de topologia padronizado, qualquer que seja o tipo de topologia. No mínimo, ele deve extrair, quando existirem:

* nome da topologia
* tipo do nó: núcleo 5G, CU, DU, gNB monolítica, UE ou oai-ext-dn
* nome do contêiner
* endereço IP
* endereço e porta do Telnet, se ligado
* identificador da gNB
* identificador da DU
* nome da gNB
* identificador da célula NR
* identificador físico da célula (PCI)
* PLMN: MCC, MNC, tamanho do MNC e S-NSSAI
* código da área de rastreamento (TAC)
* banda
* absoluteFrequencySSB
* dl_absoluteFrequencyPointA
* largura de banda da portadora
* espaçamento entre subportadoras
* padrão TDD
* endereços F1, N2 e N3, quando existirem
* configuração das células vizinhas, quando existir
* comando de handover da topologia ativa
* configuração de medição (eventos A2 e A3)

O leitor também deve examinar o `USE_ADDITIONAL_OPTIONS` do docker-compose, porque alguns valores de execução substituem ou completam os arquivos `.conf`.


## Páginas do painel

### Página 1: Overview (visão geral)

**Layout:** 3 colunas (barra lateral | topologia no centro | fluxo de mensagens à direita)

**Barra lateral à esquerda:**

- cartões de estado dos contêineres: núcleo 5G (agrupado), CU, DU0, DU1, UE e oai-ext-dn;
- em cada cartão: nome, indicador de estado (verde, vermelho ou laranja) e botões Start/Stop/Restart;
- botão de comando de handover (em destaque; envia o comando Telnet à CU).

**Centro:**

- **Barra do topo:** número de DUs, número de UEs, vazão total de descida e vazão total de subida.
- **Diagrama da topologia (SVG):**
  - bloco do núcleo 5G (no alto) → bloco da CU → blocos da DU0 e da DU1 → bloco do UE;
  - ícone do UE posicionado na DU a que ele está conectado (pelas estatísticas de RRC);
  - transição animada quando o UE muda de DU durante o handover;
  - linhas de conexão: N2/N3, F1 e rfsim;
  - código de cores: verde = rodando, vermelho = parado, laranja = subindo;
  - em cada UE: IMSI, RNTI e vazão de descida e de subida, na própria linha.

**Painel à direita:**

- **Tabela de duração dos handovers** (em cima): IMSI, ID do UE, DU de origem, DU de destino, RNTI antigo, RNTI novo e duração (ms).
- **Fluxo de mensagens 5G SA** (embaixo): tabela com rolagem, com as colunas TIME (horário), Protocol (protocolo) e Message (mensagem).

### Página 2: gNB

**Em cima:** barra de estado (estado da CU, da DU0 e da DU1, vazão total)

**Metade esquerda:**

- painel de configuração (lido dos arquivos .conf):
  - banda, largura de banda e configuração MIMO;
  - padrão de slots TDD (visual: blocos coloridos D D D F U);
  - ordem de modulação de descida e de subida;
- tabela de detalhes de cada DU: PCI, ARFCN, frequência e identificador da DU da gNB.

**Metade direita:**

- gráfico da taxa total (Recharts, últimos 10 min);
- tabela dos UEs conectados: RNTI, IMSI, DU atual, RSSI, RSRP, CQI e vazão.

**Embaixo:** visor dos logs da gNB (logs brutos do Docker, com rolagem automática e filtro por camada: MAC, RRC, NGAP)

### Página 3: UE

**Linha de cima:** cartões de resumo dos indicadores (valor atual, mínimo, máximo e média):

- CQI, MCS de descida, MCS de subida, BLER de descida, BLER de subida, taxa de descida, taxa de subida, PHR e DU atual

**Área principal:** gráficos ao longo do tempo (Recharts; um clique no cartão mostra ou esconde o gráfico):

- CQI
- MCS de descida e de subida (duas linhas)
- BLER de descida e de subida (duas linhas)
- taxa de descida e de subida (duas linhas)
- PHR

**Nota sobre os indicadores no rfsim:** no rfsim, o RSSI, o RSRP, o RSRQ, o SINR e o SNR são sintéticos. Sem modelo de canal, eles ficam estáveis e quase ideais. Mostre-os se as estatísticas do Telnet os trouxerem, mas com o rótulo "RFsim (synthetic)" e com menos destaque visual. Os indicadores principais são os da camada MAC, listados acima.

### Página 4: Handover (mobilidade)

**Esquerda:**

- exibição da configuração de handover (lida da configuração da CU):
  - lista de células vizinhas de cada DU;
  - parâmetros dos eventos de medição A2 e A3 (limiar, deslocamento, histerese e tempo para disparo);
- controle de comando do handover:
  - botão "Trigger Handover" (comandar handover) → envia `echo "handover" | nc localhost 9090` ao contêiner da CU;
  - opcional: seletor de ID do UE, para cenários com vários UEs.

**Centro:**

- diagrama da topologia (igual ao da visão geral, mas maior e focado na RAN);
- mostra a animação da troca do UE durante o handover.

**Direita:**

- **tabela de duração dos handovers:** todos os eventos de handover registrados, com os tempos;
- **linha do tempo dos eventos de handover:** linha vertical com:
  - HandoverRequest (DU de origem → DU de destino);
  - HandoverRequestAcknowledge;
  - RRCReconfigurationComplete;
  - anotação da duração;
- **comparação dos indicadores por DU:** gráficos lado a lado de MCS, CQI e BLER, com uma marca vertical no momento da troca de DU.

## Fases de implementação

> **Nota de situação.** O plano de fases abaixo é a sequência original do projeto e fica aqui como contexto histórico. A estrutura de páginas entregue foi reduzida de sete abas para três: Overview, Results (Runs e Campaigns) e Controls. Por isso:
>
> - as páginas separadas de UE, gNB e Handover descritas nas fases 2 e 3 não existem mais como páginas. O conteúdo delas foi para a visão geral e para o explorador de execuções unificado;
> - os indicadores de rádio por UE (CQI, MCS, BLER, PHR) saíram, porque nenhum caminho de telemetria os preenche.
>
> Veja no `dashboard/README.md` a lista atual de páginas, a detecção da topologia e o modelo de coleta do estado.

### Fase 1: MVP (fluxo de dados e página de visão geral)

**Objetivo:** levar os dados do testbed até o navegador.

1. Esqueleto do app FastAPI, com um endpoint WebSocket.
2. Coletor do monitor Docker (estado dos contêineres).
3. Coletor da consulta Telnet (estatísticas básicas de MAC da CU e das DUs).
4. Leitor de configuração (ler os arquivos .conf para obter a topologia).
5. App React com a página de visão geral:
   - barra lateral com cartões de estado dos contêineres (só o estado, ainda sem controles);
   - barra do topo com o número de DUs e de UEs e a vazão;
   - SVG fixo da topologia (ainda sem animação).
6. Hook de WebSocket que liga o frontend ao backend.
7. `docker-compose.dashboard.yml` para o backend e o frontend.

### Fase 2: gráficos de indicadores e página da gNB

1. Leitura completa das estatísticas do Telnet (todos os indicadores por UE).
2. Buffer do histórico de indicadores (buffer circular em memória, últimos 10 min).
3. Página do UE com cartões de indicadores e gráficos ao longo do tempo.
4. Página da gNB com a exibição da configuração e o gráfico da taxa.
5. Tabela dos UEs conectados.

### Fase 3: acompanhamento do handover

1. Leitor de logs para os eventos de handover.
2. Cálculo da duração do handover.
3. Página de handover com a tabela de durações e a linha do tempo dos eventos.
4. Botão de comando do handover (REST → Telnet).
5. Posição dinâmica do UE no diagrama da topologia.
6. Painel do fluxo de mensagens.

### Fase 4: acabamento

1. Controles do ciclo de vida dos contêineres (Start/Stop/Restart pela API do Docker).
2. Exibição da configuração de handover.
3. Gráficos de comparação por DU, com marcas do handover.
4. Visor dos logs brutos, com filtro por camada.
5. Exportação dos dados em JSON.
6. Animação da troca do UE na topologia.

## Direção de design

**Paleta de cores:** ciano-azulado como cor principal (#0097A7), barra lateral escura (#1a1a2e), área de conteúdo branca e indicadores de estado em verde, vermelho e laranja. Com a mesma energia do OAIBOX, mas sem copiá-lo.

**Tipografia:** Inter na interface e JetBrains Mono nos visores de logs e nos valores técnicos.

**Layout:** denso, mas organizado. É uma ferramenta de monitoração para pesquisadores, e não um produto de consumo. Mostre o máximo de informação sem poluir a tela.

## Notas técnicas

- **A leitura do Telnet é frágil.** O formato da saída do Telnet da OAI muda entre versões. O leitor deve conhecer a versão e falhar com avisos, sem derrubar o painel.
- **Os nomes dos contêineres devem ser os do docker-compose.** A configuração do painel deve usar os nomes de contêiner do docker-compose.yml do testbed.
- **UE do rfsim como servidor.** Na montagem de handover, o UE é o servidor do rfsim. Isso importa para a topologia da rede e para o fluxo das conexões.
- **A ordem de subida importa:** primeiro a DU0, depois o UE se conecta, depois a DU1. O painel deve lidar bem com a pilha parcialmente no ar.
- **Todos os dados são temporários.** Não há base de dados permanente no MVP. O histórico de indicadores fica em buffers na memória. A exportação em JSON serve para a análise posterior.
