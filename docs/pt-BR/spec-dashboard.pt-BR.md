# Especificação do painel: monitor do testbed de handover da OAI em RFSim

> Tradução para o português. O original em inglês é o [spec-dashboard.md](../en/spec-dashboard.md). Em caso de divergência, prevalece o original.

## Visão geral

Um painel web personalizado para monitoramento e controle em tempo real do testbed de handover 5G da OAI em RFsim. Inspirado no OAIBOX™ Dashboard (da Allbesmart), adaptado à nossa arquitetura RFsim com divisão CU/DU e capacidade de handover.

Material de referência em `docs/OAIBOX_info/` — capturas de tela e PDF do produto comercial OAIBOX.

## Arquitetura

### Topologia do testbed (o que monitoramos)

```
                    ┌─────────┐
                    │  CN5G   │ (AMF, SMF, UPF, NRF, etc.)
                    └────┬────┘
                         │ N2/N3
                    ┌────┴────┐
                    │   CU    │ (gNB-CU, telnet on port 9090)
                    ├────┬────┤
                    │ F1 │ F1 │
               ┌────┴──┐ ┌──┴────┐
               │  DU0  │ │  DU1  │ (each with own PCI, ARFCN)
               └───┬───┘ └───┬───┘
                   │ RFsim   │ RFsim
               ┌───┴─────────┴───┐
               │       UE        │ (RFsim server, OAI nrUE)
               └─────────────────┘
```

Todos os componentes rodam como contêineres Docker via docker-compose.

### Pilha do painel

```
┌─────────────────────────────────────────────┐
│              React Frontend                  │
│  (Recharts, Tailwind, WebSocket client)      │
├─────────────────────────────────────────────┤
│              FastAPI Backend                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Telnet   │ │ Docker   │ │ Log Watcher  │ │
│  │ Poller   │ │ Monitor  │ │ (HO events)  │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │ Config   │ │ WebSocket broadcast      │  │
│  │ Parser   │ │ (real-time KPI stream)   │  │
│  └──────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────┤
│         Docker Engine / Containers           │
│  (CN5G, CU, DU0, DU1, UE, oai-ext-dn)          │
└─────────────────────────────────────────────┘
```

### Estrutura de diretórios (dentro deste repositório)

```
dashboard/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Dashboard configuration (ports, container names)
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── telnet_poller.py     # Async telnet client for gNB MAC/RRC stats
│   │   ├── docker_monitor.py    # Docker SDK container status polling
│   │   ├── log_watcher.py       # Docker log tailing for HO events + message flow
│   │   └── config_parser.py     # OAI .conf file parser (CU, DU0, DU1 configs)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── kpi.py               # Pydantic models for UE KPIs
│   │   ├── handover.py          # HO event, HO duration models
│   │   └── topology.py          # Network topology state model
│   ├── api/
│   │   ├── __init__.py
│   │   ├── containers.py        # REST endpoints: container lifecycle
│   │   ├── config.py            # REST endpoints: read/write OAI configs
│   │   ├── handover.py          # REST endpoints: trigger HO, get HO history
│   │   └── websocket.py         # WebSocket endpoint: real-time KPI + events
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
│   │   │   │   └── TopologyDiagram.jsx    # SVG network diagram with live status
│   │   │   ├── kpi/
│   │   │   │   ├── KpiCard.jsx            # Summary card (value + min/max/avg)
│   │   │   │   └── TimeSeriesChart.jsx    # Recharts line chart
│   │   │   ├── handover/
│   │   │   │   ├── HandoverTimeline.jsx   # Event timeline
│   │   │   │   ├── HandoverDuration.jsx   # Duration table
│   │   │   │   └── HandoverTrigger.jsx    # Trigger button
│   │   │   ├── containers/
│   │   │   │   └── ContainerControl.jsx   # Start/Stop/Restart per container
│   │   │   ├── logs/
│   │   │   │   ├── MessageFlow.jsx        # 5G SA message flow table
│   │   │   │   └── RawLogs.jsx            # Raw gNB log viewer
│   │   │   └── config/
│   │   │       └── GnbConfig.jsx          # Configuration display/editor
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
├── docker-compose.dashboard.yml   # Dashboard services only
└── README.md
```

## Fontes de dados

### 1. Interface telnet da gNB (fonte principal de KPIs)

A gNB da OAI expõe um servidor telnet na porta 9090 (quando compilada com `--build-lib telnetsrv`).
O telnet da CU fornece estatísticas no nível do RRC; os telnets das DUs fornecem estatísticas de MAC/PHY.

**Intervalo de consulta:** ~1 segundo

**Principais comandos e padrões de saída esperados:**

```
# MAC stats (per DU)
mac stats → per-RNTI: DLSCH/ULSCH bytes, MCS, BLER, CQI, rounds, retx

# RRC stats (CU)
rrc stats → UE contexts, RNTI, state, associated DU

# Handover trigger (CU)
handover → triggers round-robin HO across DUs
handover <cu-ue-id> → triggers HO for specific UE
```

**KPIs extraíveis por UE (por ciclo de consulta):**
- MCS DL/UL (do escalonador do MAC)
- CQI (informado pelo UE via MAC)
- BLER DL/UL (baseado em HARQ)
- Vazão DL/UL (delta de bytes / delta de tempo)
- PHR (MAC CE)
- Rodadas/retransmissões HARQ
- DU servidora atual (do contexto RRC)

### 2. API do Docker

**Intervalo de consulta:** ~5 segundos

**Contêineres monitorados** (nomes do docker-compose):
- Serviços do CN5G: oai-amf, oai-smf, oai-upf, oai-nrf (+ outros)
- RAN: oai-cu, oai-du0, oai-du1
- UE: oai-nr-ue
- Externo: oai-ext-dn

**Por contêiner:** status (running/stopped/restarting), health check, tempo de atividade

### 3. Observador de logs (eventos de handover)

**Fonte:** `docker logs --follow oai-cu`

**Padrões a detectar:**

```python
# Handover request sent
r"\[NR_RRC\].*HandoverRequest.*RNTI\s+(0x[0-9a-fA-F]+).*target.*DU\s+(\d+)"

# Handover request acknowledged
r"\[NR_RRC\].*HandoverRequestAcknowledge.*RNTI\s+(0x[0-9a-fA-F]+)"

# RRC Reconfiguration complete (HO success)
r"\[NR_RRC\].*RRCReconfigurationComplete.*RNTI\s+(0x[0-9a-fA-F]+)"

# UE context release (cleanup after HO)
r"\[NR_RRC\].*UEContextRelease.*RNTI\s+(0x[0-9a-fA-F]+)"

# General NGAP/NAS messages for the message flow table
r"\[(NGAP|NAS)\].*"
```

**Duração do handover:** timestamp(RRCReconfigurationComplete) - timestamp(HandoverRequest)

### 4. Parser dos arquivos de configuração

**Arquivos a processar, por topologia:**

O painel não deve presumir um único layout fixo de configuração da OAI. Ele deve detectar a topologia ativa, ou ser configurado com ela, e então processar os arquivos Compose/de configuração correspondentes.

### Topologia de handover F1: `f1`

Arquivos principais:

* Compose da RAN: `gnb-docker-compose.yaml`
* Configuração da CU: `conf-cu.conf`
* Configuração base da DU: `conf-du.conf`
* Configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-cu`
* `oai-du0`
* `oai-du1`
* `oai-nr-ue`
* Contêineres do núcleo de `oai-cn5g/docker-compose.yaml`, incluindo `oai-amf`, `oai-smf`, `oai-upf`, `oai-nrf`, `oai-udr`, `oai-udm`, `oai-ausf`, `mysql` e `oai-ext-dn`

Observações importantes:

* `oai-du0` e `oai-du1` montam ambos o `conf-du.conf`.
* A `oai-du1` tem substituições específicas da topologia injetadas pelo `gnb-docker-compose.yaml` via `USE_ADDITIONAL_OPTIONS`, incluindo ID da DU, ID da célula, PCI, frequência do SSB, PointA, bitmap do SSB e endereço F1 local.
* O telnet da CU está disponível em `192.168.70.150:9090`.
* O telnet da DU não está habilitado no arquivo Compose F1 atual.
* O comando de disparo do handover F1 é `ci trigger_f1_ho`.

### Topologia N2 monolítica: `n2-monolithic`

Arquivos principais:

* Compose da RAN: `experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml`
* Configuração da gNB de origem: `experiments/n2_handover/topology_a_monolithic/conf-gnb0.conf`
* Configuração da gNB de destino: `experiments/n2_handover/topology_a_monolithic/conf-gnb1.conf`
* Configuração de vizinhança: `experiments/n2_handover/topology_a_monolithic/neighbour-config.conf`
* Configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-gnb0`
* `oai-gnb1`
* `oai-nr-ue`
* Contêineres do núcleo de `oai-cn5g/docker-compose.yaml`

Observações importantes:

* `oai-gnb0` e `oai-gnb1` são gNBs monolíticas completas.
* As duas gNBs expõem telnet pelos endereços de escuta configurados.
* O comando de disparo do handover N2 é `ci trigger_n2_ho <target_pci>,<ue_rrc_id>`.

### Topologia N2 CU/DU: `n2-cu-du`

Arquivos principais:

* Compose da RAN: `experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml`
* Configuração da CU de origem: `experiments/n2_handover/topology_b_cu_du/conf-cu0.conf`
* Configuração da DU de origem: `experiments/n2_handover/topology_b_cu_du/conf-du0.conf`
* Configuração da CU de destino: `experiments/n2_handover/topology_b_cu_du/conf-cu1.conf`
* Configuração da DU de destino: `experiments/n2_handover/topology_b_cu_du/conf-du1.conf`
* Configuração de vizinhança: `experiments/n2_handover/topology_b_cu_du/neighbour-config.conf`
* Configuração do UE: `conf-nr-ue.conf`

Contêineres:

* `oai-cu0`
* `oai-du0`
* `oai-cu1`
* `oai-du1`
* `oai-nr-ue`
* Contêineres do núcleo de `oai-cn5g/docker-compose.yaml`

Observações importantes:

* Esta topologia tem dois pares CU/DU.
* Os endpoints telnet são configurados por CU/DU no arquivo Compose.
* Na N2 CU/DU, o endpoint telnet de origem deve seguir a mesma lógica usada pelo `scripts/trigger_handover.sh`.
* O comando de disparo do handover N2 é `ci trigger_n2_ho <target_pci>,<ue_rrc_id>`.

### Requisitos do parser

O parser de configuração deve retornar um modelo de topologia normalizado, independentemente do tipo de topologia. No mínimo, extrair, quando disponível:

* nome da topologia
* tipo de nó: CN, CU, DU, gNB monolítica, UE, oai-ext-dn
* nome do contêiner
* endereço IP
* host/porta do telnet, se habilitado
* ID da gNB
* ID da DU
* nome da gNB
* ID da célula NR
* ID físico da célula (PCI)
* PLMN: MCC, MNC, comprimento do MNC, S-NSSAI
* código de área de rastreamento (TAC)
* banda
* absoluteFrequencySSB
* dl_absoluteFrequencyPointA
* largura de banda da portadora
* espaçamento entre subportadoras
* padrão TDD
* endereços F1 / N2 / N3, quando presentes
* configuração de células vizinhas, quando presente
* comando de disparo do handover para a topologia ativa
* configuração de medição (eventos A2/A3)

O parser também precisa inspecionar o `USE_ADDITIONAL_OPTIONS` do docker-compose, porque alguns valores de execução substituem ou complementam os arquivos `.conf`.


## Páginas do painel

### Página 1: Visão geral

**Layout:** 3 colunas (barra lateral | topologia ao centro | fluxo de mensagens à direita)

**Barra lateral esquerda:**
- Cartões de status dos contêineres para: CN5G (agrupado), CU, DU0, DU1, UE, oai-ext-dn
- Cada cartão: nome, indicador de status (verde/vermelho/laranja), botões Start/Stop/Restart
- Botão de disparo do handover (em destaque, envia o comando telnet à CU)

**Centro:**
- **Barra superior:** número de DUs, número de UEs, vazão DL agregada, vazão UL agregada
- **Diagrama de topologia (SVG):**
  - Bloco CN5G (em cima) → bloco CU → blocos DU0 / DU1 → bloco UE
  - Ícone do UE posicionado na DU à qual ele está conectado no momento (a partir das estatísticas de RRC)
  - Transição animada quando o UE passa de uma DU para outra durante o handover
  - Linhas de conexão: N2/N3, F1, RFsim
  - Código de cores: verde=rodando, vermelho=parado, laranja=iniciando
  - Por UE: mostrar IMSI, RNTI e vazão DL/UL na própria linha

**Painel direito:**
- **Tabela de duração dos handovers** (em cima): IMSI, ID do UE, DU de origem, DU de destino, RNTI antigo, RNTI novo, duração (ms)
- **Fluxo de mensagens do 5G SA** (embaixo): tabela com rolagem, com as colunas TIME, Protocol, Message

### Página 2: gNB

**Topo:** barra de status (status da CU, status da DU0/DU1, vazão agregada)

**Metade esquerda:**
- Painel de configuração (lido dos arquivos .conf)
  - Banda, largura de banda, configuração MIMO
  - Padrão de slots TDD (visual: blocos coloridos D D D F U)
  - Ordem de modulação DL/UL
- Tabela de detalhes por DU: PCI, ARFCN, frequência, ID da gNB DU

**Metade direita:**
- Gráfico da taxa de bits agregada (Recharts, últimos 10 min)
- Tabela de UEs conectados: RNTI, IMSI, DU servidora, RSSI, RSRP, CQI, vazão

**Rodapé:** visualizador de logs da gNB (docker logs bruto, rolagem automática, filtro por camada: MAC/RRC/NGAP)

### Página 3: UE

**Linha superior:** cartões de resumo de KPIs (valor atual + mín./máx./méd.):
- CQI, MCS DL, MCS UL, BLER DL, BLER UL, taxa de bits DL, taxa de bits UL, PHR, DU servidora

**Área principal:** gráficos de séries temporais (Recharts, alternáveis com um clique no cartão):
- CQI ao longo do tempo
- MCS DL/UL ao longo do tempo (linha dupla)
- BLER DL/UL ao longo do tempo (linha dupla)
- Taxa de bits DL/UL ao longo do tempo (linha dupla)
- PHR ao longo do tempo

**Observação sobre KPIs no RFsim:** RSSI, RSRP, RSRQ, SINR e SNR são sintéticos no modo RFsim (estáveis/quase ideais sem modelo de canal). Exiba-os se estiverem disponíveis nas estatísticas do telnet, mas rotule-os como "RFsim (synthetic)" e dê-lhes menos destaque visual. Os KPIs principais são os da camada MAC listados acima.

### Página 4: Handover (mobilidade)

**Esquerda:**
- Exibição da configuração de handover (extraída da configuração da CU):
  - Lista de células vizinhas por DU
  - Parâmetros dos eventos de medição A2/A3 (limiar, offset, histerese, time-to-trigger)
- Controle de disparo do handover:
  - Botão: "Trigger Handover" → envia `echo "handover" | nc localhost 9090` ao contêiner da CU
  - Opcional: seletor de ID do UE para cenários com vários UEs

**Centro:**
- Diagrama de topologia (igual ao da Visão geral, porém maior e focado na RAN)
- Mostra a animação de migração do UE durante o HO

**Direita:**
- **Tabela de duração dos handovers:** todos os eventos de HO registrados, com a temporização
- **Linha do tempo dos eventos de handover:** linha do tempo vertical mostrando:
  - HandoverRequest (DU de origem → DU de destino)
  - HandoverRequestAcknowledge
  - RRCReconfigurationComplete
  - Anotação da duração
- **Comparação de KPIs por DU:** gráficos de MCS/CQI/BLER lado a lado, mostrando o momento da troca de DU como um marcador vertical

## Fases de implementação

> **Observação de status.** O plano de fases abaixo é a sequência de projeto original e é mantido como
> contexto histórico. Desde então, a estrutura de páginas entregue foi consolidada de sete
> abas para três — Overview, Results (Runs e Campaigns) e Controls —, de modo que as páginas separadas
> UE, gNB e Handover descritas nas Fases 2 e 3 não existem mais como páginas; seu
> conteúdo foi para a Visão geral e para o explorador de execuções unificado, e os KPIs de rádio por UE
> (CQI/MCS/BLER/PHR) foram descartados porque nenhum caminho de telemetria os alimenta. Veja
> `dashboard/README.md` para o inventário atual de páginas, a detecção de topologia e o modelo de
> coleta de estado.

### Fase 1: MVP — pipeline de dados + página Visão geral
**Objetivo:** fazer os dados fluírem do testbed até o navegador.

1. Esqueleto do app FastAPI com endpoint WebSocket
2. Coletor do monitor do Docker (status dos contêineres)
3. Coletor de consulta ao telnet (estatísticas básicas de MAC da CU/DUs)
4. Parser de configuração (ler os arquivos .conf para obter informações da topologia)
5. App React com a página Visão geral:
   - Barra lateral com cartões de status dos contêineres (ainda sem controles, apenas status)
   - Barra superior com número de DUs/UEs e vazão
   - SVG de topologia estático (ainda sem animação)
6. Hook WebSocket conectando o frontend ao backend
7. `docker-compose.dashboard.yml` para backend + frontend

### Fase 2: gráficos de KPIs + página gNB
1. Leitura completa das estatísticas do telnet (todos os KPIs por UE)
2. Buffer de histórico de KPIs (buffer circular em memória, últimos 10 min)
3. Página UE com cartões de KPI e gráficos de séries temporais
4. Página gNB com exibição da configuração e gráfico da taxa de bits
5. Tabela de UEs conectados

### Fase 3: monitoramento de handover
1. Observador de logs para eventos de HO
2. Cálculo da duração do handover
3. Página Handover com tabela de duração e linha do tempo dos eventos
4. Botão de disparo do handover (REST → telnet)
5. Posição dinâmica do UE no diagrama de topologia
6. Painel de fluxo de mensagens

### Fase 4: refinamento
1. Controles de ciclo de vida dos contêineres (Start/Stop/Restart via API do Docker)
2. Exibição da configuração de handover
3. Gráficos de comparação por DU com marcadores de HO
4. Visualizador de logs brutos com filtro por camada
5. Exportação de dados em JSON
6. Animação de migração do UE na topologia

## Direção de design

**Paleta de cores:** primária em azul-petróleo/ciano (#0097A7), barra lateral escura (#1a1a2e), área de conteúdo branca, indicadores de status verde/vermelho/laranja. Uma energia parecida com a do OAIBOX, mas não uma cópia.

**Tipografia:** Inter para a interface, JetBrains Mono para os visualizadores de log e valores técnicos.

**Layout:** denso, mas organizado — esta é uma ferramenta de monitoramento para pesquisadores, e não um produto de consumo. Maximize a densidade de informação sem poluição visual.

## Observações técnicas

- **A leitura do telnet é frágil:** o formato de saída do telnet da OAI varia entre versões. O parser deve levar a versão em conta e falhar de forma controlada, com avisos, em vez de travar.
- **Os nomes dos contêineres devem corresponder ao docker-compose:** a configuração do painel deve mapear os nomes dos contêineres a partir do docker-compose.yml do testbed.
- **UE RFsim como servidor:** na montagem de handover, o UE roda como servidor RFsim (importante para a topologia de rede e o fluxo de conexão).
- **A ordem de inicialização importa:** primeiro a DU0, depois o UE se conecta, depois a DU1. O painel deve lidar de forma controlada com cenários de pilha parcial.
- **Todos os dados são efêmeros:** não há banco de dados persistente no MVP. Buffers em memória para o histórico de KPIs. Exportação em JSON para análise posterior.
