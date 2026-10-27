# Handoff da visão geral ao vivo do painel

> Tradução para o português. O original em inglês é o [handoff-dashboard-overview-live.md](../en/handoff-dashboard-overview-live.md). Em caso de divergência, prevalece o original.

Data: 01/07/2026

Este handoff registra a discussão sobre a Visão geral do painel, o que foi implementado, por que as mudanças foram feitas, como foram validadas e o que continua limitado.

## Ponto de partida

O painel já tinha crescido ao longo das fases anteriores:

- observabilidade básica da topologia e da configuração ao vivo;
- histórico de KPIs, páginas gNB/UE/Runs;
- observabilidade de handover/mobilidade;
- controles de experimento desabilitados por padrão;
- análise de campanhas/execuções repetidas;
- acesso remoto e refinamentos de UX/exibição de rádio.

Após o uso real com RFsim, a página Visão geral ainda tinha ruído demais para demonstrações ao vivo. Ela mostrava informações duplicadas, métricas de execuções salvas onde se esperavam valores ao vivo e não deixava visualmente evidente a interrupção do handover durante disparos rápidos de handover F1.

## Feedback do operador

As mudanças solicitadas foram:

1. Deixar mais limpo o Handover Monitor à esquerda:
   - agrupar DU0 e DU1 num único cartão DU;
   - incluir o `oai-ext-dn` em CN5G;
   - permitir recolher/expandir os cartões;
   - adicionar um controle global `Collapse all / Expand all` abaixo do título "Handover Monitor".

2. Remover itens de pouco valor da Visão geral:
   - remover a faixa de topologia do topo;
   - remover os cartões duplicados "System healthy" e "Action enabled";
   - remover da Visão geral principal os cartões de RTT/HO de execuções salvas;
   - remover o cartão Mobility State, porque as partes úteis são mostradas em outro lugar;
   - remover o selo desatualizado `Phase 5 dashboard` do cartão de topologia.

3. Melhorar a usabilidade do handover rápido:
   - manter o modelo existente de ações seguras do backend;
   - remover a caixa de confirmação da Visão geral, para demonstrações repetidas em RFsim;
   - substituí-la por uma mensagem de aviso clara;
   - continuar habilitando o botão somente quando `DASHBOARD_ENABLE_ACTIONS=true`, a topologia for F1 e nenhuma ação iniciada pelo painel estiver em execução.

4. Mostrar a DU servidora atual:
   - o telnet da CU fica desativado por padrão e o telnet da DU não está disponível;
   - a DU servidora atual deve ser extraída de logs limitados da CU quando possível;
   - se a DU servidora não puder ser observada, não apresentar um caminho UE-DU inventado.

5. Substituir a "Live handover duration" pelo que o operador realmente precisa:
   - um gráfico de entrega de pacotes / latência ao vivo;
   - os pacotes bem-sucedidos devem mostrar o RTT ao longo do tempo;
   - a interrupção durante o handover deve aparecer como pacotes faltando/lacunas;
   - a recuperação deve ficar visível quando os pacotes voltarem a ser entregues.

## Mudanças implementadas

### Limpeza da Visão geral no frontend

Arquivos:

- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/frontend/src/components/Sidebar.jsx`
- `dashboard/frontend/src/components/TopologyDiagram.jsx`

Implementado:

- A Visão geral não renderiza mais a faixa de topologia do topo.
- A Visão geral não renderiza mais o painel de resumo de execuções à direita.
- A Visão geral não mostra mais cartões duplicados de saúde/ações/métricas de execuções salvas.
- O layout da Visão geral agora se concentra em:
  - barra lateral Handover Monitor agrupada;
  - resumo curto para o operador;
  - diagrama de topologia com destaque da DU ativa;
  - controle de handover F1 rápido;
  - gráfico de latência/interrupção do UE ao vivo.
- O cartão de topologia não mostra mais `Phase 5 dashboard`.
- Grupos do Handover Monitor:
  - `CN5G`: contêineres do núcleo mais o `oai-ext-dn`;
  - `CU`: contêineres da CU;
  - `DU`: `oai-du0` e `oai-du1`;
  - `UE`: contêineres do UE.
- Cada grupo pode ser expandido/recolhido.
- Um botão global `Collapse all / Expand all` foi adicionado abaixo do título do Handover Monitor.

Motivo:

A Visão geral anterior misturava informações ao vivo críticas para o operador com dados históricos de execuções e cartões de status duplicados. Nas demonstrações, a página precisa responder rapidamente:

- o sistema está rodando?
- a qual DU o UE está conectado agora?
- posso disparar o handover?
- a entrega de pacotes parou e se recuperou?

### UX do handover rápido

Arquivo:

- `dashboard/frontend/src/pages/Overview.jsx`

Implementado:

- A caixa de confirmação foi removida do controle de handover rápido da Visão geral.
- Em seu lugar, é exibido um aviso:
  - isto é executado imediatamente no testbed RFsim local;
  - use somente enquanto a pilha F1 estiver intencionalmente ativa.
- O botão continua chamando o endpoint seguro existente:
  - `POST /api/actions/trigger-handover`
  - corpo: `{ "confirm": true }`
- As proteções de segurança existentes da Fase 4 continuam:
  - ações desabilitadas por padrão;
  - exige iniciar o backend com `DASHBOARD_ENABLE_ACTIONS=true`;
  - apenas um script fixo e confiável;
  - nenhuma execução de comando arbitrário;
  - nenhum controle de ciclo de vida;
  - nenhuma edição de configuração;
  - um único job iniciado pelo painel por vez.

Motivo:

Durante o uso em demonstrações com RFsim, disparar o handover repetidamente é normal. A caixa de confirmação tornava o fluxo mais lento sem acrescentar segurança significativa além da proteção existente no backend e do aviso.

### DU servidora atual a partir dos logs da CU

Arquivos:

- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/backend/validate_phase6.py`

Implementado:

- O backend lê um trecho final limitado do log da CU no `oai-cu`.
- Ele reconhece padrões de log conhecidos relacionados ao handover F1:
  - célula de destino do disparo do handover;
  - ID da célula pós-handover em `RRCReconfigurationComplete`;
  - linha de handover concluído;
  - IP remoto da atualização do túnel GTP-U, como alternativa.
- Ele mapeia IDs de célula e IPs locais F1 para nomes de DU usando a configuração F1 processada:
  - `12345678` / `bc614e` corresponde à DU0;
  - `11111111` / `a98ac7` corresponde à DU1;
  - os endereços F1 locais das DUs também são mapeados de volta para os nomes das DUs.
- A topologia da Visão geral destaca a DU servidora extraída, quando disponível.
- As linhas de caminho do UE usam metadados de origem/confiança:
  - `cu_telnet` / `observed` quando o contexto atual do UE expõe a DU servidora;
  - `cu_logs_tail` / `parsed` quando inferida a partir dos logs da CU;
  - `latest_run_artifacts` / `inferred` apenas para métricas históricas;
  - `unknown` quando não existe fonte atual.

Motivo:

O usuário observou que, após o handover, a Visão geral não mudava e mostrava `Unknown` para as informações de UE-DU. Como o telnet da DU F1 não está disponível e a consulta passiva ao telnet da CU fica desativada por padrão, os logs limitados da CU são a fonte prática do estado atual.

### Gráfico de latência / interrupção do UE ao vivo

Arquivos:

- `dashboard/backend/collectors/live_latency.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/backend/validate_phase6.py`

Implementado:

- Adicionado o `LiveLatencyMonitor`.
- Ele mantém em memória um buffer circular limitado de amostras ao vivo.
- Ele amostra aproximadamente na taxa de atualização do painel, com uma proteção de intervalo mínimo.
- Ele executa um comando fixo, limitado e sem shell:

  ```bash
  docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
  ```

- Sondas bem-sucedidas produzem:
  - `reachable: true`;
  - `rtt_ms` extraído;
  - `status: delivered`.
- Sondas com falha produzem:
  - `reachable: false`;
  - `rtt_ms: null`;
  - um texto curto de erro/status;
  - `status: lost`, `timeout`, `unavailable` ou `error`.
- O gráfico plota o RTT das sondas entregues.
- As sondas perdidas criam lacunas e marcadores vermelhos.
- O gráfico inclui contadores compactos:
  - amostras entregues;
  - amostras perdidas;
  - interface/destino da sonda;
  - origem.

Motivo:

O gráfico anterior "Live handover duration" se baseava na duração do comando de handover no log da CU. Isso não é a mesma coisa que a interrupção do plano de dados. O operador queria ver os pacotes sendo entregues, depois a interrupção e, em seguida, a entrega novamente. O gráfico ao vivo baseado em ping representa diretamente esse comportamento.

## Impacto na API/estado

O seguinte estado agora inclui a latência ao vivo:

- `GET /api/topology`
- `GET /api/overview`
- estado do WebSocket `/ws`

Campos relevantes:

```json
{
  "live_latency": {
    "container": "oai-nr-ue",
    "interface": "oaitun_ue1",
    "target": "192.168.71.135",
    "source": "docker_exec_ping",
    "retention_samples": 300,
    "latest": {
      "timestamp": "...",
      "label": "HH:MM:SS",
      "reachable": true,
      "rtt_ms": 11.5,
      "status": "delivered",
      "error": null
    },
    "samples": [],
    "delivered_count": 0,
    "lost_count": 0,
    "warnings": []
  }
}
```

O objeto da Visão geral também inclui `overview.live_latency`, por conveniência.

## Validação realizada

Validação do backend/frontend:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase6.py
docker compose -f dashboard/docker-compose.dashboard.yml config
cd dashboard/frontend && npm install && npm run build
git diff --check
```

Teste rápido em execução:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build
```

Em seguida:

```bash
curl -fsS http://localhost:8000/api/overview
```

Resultado observado:

- O `/api/overview` retornou amostras de latência ao vivo.
- Última sonda local observada:
  - `oaitun_ue1 -> 192.168.71.135`;
  - `reachable: true`;
  - `rtt_ms: ~11.5`;
  - `source: docker_exec_ping`.

## Registro de PR e merge

A limpeza da Visão geral e as mudanças do gráfico ao vivo foram commitadas e incorporadas por meio de:

- PR: <https://github.com/fsnobre/oai-rfsim-handover-testbed/pull/19>
- Commit de merge: `b0f2c6ca838c6c5262883e720aad36775a940a77`

## Observações operacionais

Para executar o painel com os controles do RFsim local:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

Para acessar remotamente pelo Tailscale:

- execute o painel no mini PC;
- abra o frontend pelo IP do Tailscale do mini PC e pela porta do frontend;
- o frontend deduz o host do backend a partir do host do navegador, a menos que configurado explicitamente.

O gráfico de latência ao vivo exige que:

- o backend do painel possa usar o Docker;
- o contêiner `oai-nr-ue` exista/esteja rodando;
- a `oaitun_ue1` exista dentro do contêiner do UE;
- o destino `192.168.71.135` do EXT-DN esteja alcançável.

Se algum desses itens faltar, o gráfico deve mostrar amostras indisponíveis/perdidas, em vez de falhar.

## Limitações restantes

- O gráfico de latência ao vivo faz sondagem ativa. Ela é limitada e leve, mas não é telemetria passiva.
- A detecção da DU servidora depende dos padrões de texto atuais do log da CU. Se os formatos de log da OAI mudarem, a extração pode parar de funcionar.
- A consulta passiva ao telnet da CU continua desativada por padrão, porque a consulta repetida de `help` já desestabilizou a CU.
- O telnet da DU F1 continua sem uso.
- KPIs de RF/MAC como CQI, MCS, BLER, PHR, RSRP, RSRQ e SINR continuam indisponíveis, a menos que a OAI os exponha por uma fonte de telemetria atual e segura.
- O handover rápido não cria, por si só, uma execução de experimento salva. Os artefatos de execuções salvas continuam vindo dos testes rápidos/repetidos.
- Não há autenticação implementada. Não exponha um painel com ações habilitadas em redes não confiáveis.
