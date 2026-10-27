# Passagem de contexto: visão geral ao vivo do painel web

> Tradução para o português em Linguagem Simples. O original em inglês é o [handoff-dashboard-overview-live.md](../en/handoff-dashboard-overview-live.md). Se houver diferença entre os dois, vale o original.

Data: 01/07/2026

Esta passagem de contexto registra a discussão sobre a página Overview (visão geral) do painel web. Ela mostra o que foi feito, por que as mudanças foram feitas, como foram validadas e o que continua limitado.

## Ponto de partida

O painel web já tinha crescido nas fases anteriores:

- observação básica da topologia e da configuração ao vivo;
- histórico de indicadores e páginas gNB, UE e Runs;
- observação do handover e da mobilidade;
- controles de experimento, desligados por padrão;
- análise de campanhas e de execuções repetidas;
- acesso remoto e melhorias na exibição e nos dados de rádio.

Depois de uso real com rfsim, a visão geral ainda tinha informação demais para demonstrações ao vivo. Ela tinha três problemas:

- mostrava informações repetidas;
- mostrava métricas de execuções salvas onde se esperavam valores ao vivo;
- não deixava a interrupção do handover visível nos comandos rápidos de handover F1.

## Pedidos do operador

As mudanças pedidas foram estas:

1. Deixar mais limpo o Handover Monitor, à esquerda:
   - juntar a DU0 e a DU1 em um único cartão de DU;
   - incluir o `oai-ext-dn` no grupo CN5G;
   - permitir recolher e abrir os cartões;
   - acrescentar um controle geral `Collapse all / Expand all` (recolher tudo / abrir tudo) abaixo do título "Handover Monitor".

2. Tirar da visão geral os itens de pouco valor:
   - a faixa de topologia no topo;
   - os cartões repetidos "System healthy" e "Action enabled";
   - os cartões de RTT e de handover das execuções salvas;
   - o cartão Mobility State, porque as partes úteis já aparecem em outros lugares;
   - a etiqueta desatualizada `Phase 5 dashboard` no cartão da topologia.

3. Facilitar o handover rápido:
   - manter o modelo seguro de ações do backend;
   - tirar a caixa de confirmação da visão geral, para as demonstrações repetidas em rfsim;
   - pôr no lugar uma mensagem de aviso clara;
   - continuar ligando o botão só quando `DASHBOARD_ENABLE_ACTIONS=true`, a topologia for F1 e nenhuma ação iniciada pelo painel estiver rodando.

4. Mostrar a DU que atende o UE no momento:
   - o Telnet da CU vem desligado por padrão, e o Telnet da DU não está disponível;
   - quando possível, ler a DU atual de um trecho limitado dos logs da CU;
   - se não for possível observar a DU atual, não inventar um caminho do UE até a DU.

5. Trocar o "Live handover duration" (duração do handover ao vivo) pelo que o operador precisa de fato:
   - um gráfico ao vivo de entrega de pacotes e de latência;
   - os pacotes entregues mostram o RTT ao longo do tempo;
   - a interrupção durante o handover aparece como pacotes perdidos ou falhas na linha;
   - a recuperação aparece quando os pacotes voltam a ser entregues.

## Mudanças feitas

### Limpeza da visão geral no frontend

Arquivos:

- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/frontend/src/components/Sidebar.jsx`
- `dashboard/frontend/src/components/TopologyDiagram.jsx`

O que mudou:

- A visão geral não mostra mais a faixa de topologia no topo.
- A visão geral não mostra mais o painel de resumo de execuções à direita.
- A visão geral não mostra mais os cartões repetidos de saúde, de ações e de métricas salvas.
- A visão geral agora se concentra em:
  - barra lateral Handover Monitor, agrupada;
  - resumo curto para o operador;
  - diagrama da topologia com a DU ativa em destaque;
  - controle de handover F1 rápido;
  - gráfico ao vivo de latência e de interrupção do UE.
- O cartão da topologia não mostra mais `Phase 5 dashboard`.
- Grupos do Handover Monitor:
  - `CN5G`: contêineres do núcleo 5G e o `oai-ext-dn`;
  - `CU`: contêineres das CUs;
  - `DU`: `oai-du0` e `oai-du1`;
  - `UE`: contêineres do UE.
- Cada grupo pode ser aberto ou recolhido.
- Um botão geral `Collapse all / Expand all` foi acrescentado abaixo do título do Handover Monitor.

Motivo:

A visão geral anterior misturava informação ao vivo essencial com dados históricos e cartões de estado repetidos. Nas demonstrações, a página precisa responder rápido:

- o sistema está rodando?
- a que DU o UE está conectado agora?
- posso comandar o handover?
- a entrega de pacotes parou e voltou?

### Uso do handover rápido

Arquivo:

- `dashboard/frontend/src/pages/Overview.jsx`

O que mudou:

- A caixa de confirmação saiu do controle de handover rápido da visão geral.
- No lugar dela, aparece um aviso:
  - o comando roda na hora, no testbed rfsim local;
  - só use com a pilha do F1 ativa de propósito.
- O botão continua chamando o endpoint seguro que já existe:
  - `POST /api/actions/trigger-handover`;
  - corpo: `{ "confirm": true }`.
- As travas de segurança da fase 4 continuam:
  - ações desligadas por padrão;
  - o backend precisa subir com `DASHBOARD_ENABLE_ACTIONS=true`;
  - só um script fixo e confiável;
  - nenhuma execução de comando arbitrário;
  - nenhum controle de ciclo de vida;
  - nenhuma edição de configuração;
  - uma tarefa iniciada pelo painel por vez.

Motivo:

Nas demonstrações em rfsim, é normal comandar o handover várias vezes. A caixa de confirmação deixava o processo lento. Ela não acrescentava segurança real além da trava do backend e do aviso.

### DU atual lida dos logs da CU

Arquivos:

- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/backend/validate_phase6.py`

O que mudou:

- O backend lê um trecho limitado do fim do log da `oai-cu`.
- Ele procura padrões conhecidos de log do handover F1:
  - célula de destino do comando de handover;
  - identificador da célula no `RRCReconfigurationComplete` depois do handover;
  - linha de conclusão do handover;
  - como reserva, o IP remoto da atualização do túnel GTP-U.
- Ele liga os identificadores de célula e os IPs F1 locais aos nomes das DUs, pela configuração F1:
  - `12345678` / `bc614e` é a DU0;
  - `11111111` / `a98ac7` é a DU1;
  - os endereços F1 locais das DUs também levam aos nomes das DUs.
- O diagrama da visão geral destaca a DU atual lida, quando ela existe.
- As linhas de caminho do UE trazem a fonte e a confiança:
  - `cu_telnet` / `observed`, quando o contexto atual do UE mostra a DU atual;
  - `cu_logs_tail` / `parsed`, quando a DU vem dos logs da CU;
  - `latest_run_artifacts` / `inferred`, só para métricas históricas;
  - `unknown`, quando não há fonte atual.

Motivo:

O usuário notou que, depois do handover, a visão geral não mudava e mostrava `Unknown` na informação de UE e DU. O Telnet da DU no F1 não está disponível, e a consulta periódica pelo Telnet da CU vem desligada. Por isso, um trecho limitado dos logs da CU é a fonte prática do estado atual.

### Gráfico ao vivo de latência e de interrupção do UE

Arquivos:

- `dashboard/backend/collectors/live_latency.py`
- `dashboard/backend/main.py`
- `dashboard/backend/collectors/operator_overview.py`
- `dashboard/frontend/src/pages/Overview.jsx`
- `dashboard/backend/validate_phase6.py`

O que mudou:

- Foi criado o `LiveLatencyMonitor`.
- Ele guarda as amostras ao vivo em memória, em um buffer circular limitado.
- Ele mede mais ou menos na frequência de atualização do painel, com um intervalo mínimo de proteção.
- Ele roda um comando fixo e limitado, sem shell:

  ```bash
  docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135
  ```

- Um teste que dá certo gera:
  - `reachable: true`;
  - o `rtt_ms` lido;
  - `status: delivered`.
- Um teste que falha gera:
  - `reachable: false`;
  - `rtt_ms: null`;
  - um texto curto de erro ou de estado;
  - `status: lost`, `timeout`, `unavailable` ou `error`.
- O gráfico mostra o RTT dos testes entregues.
- Os testes perdidos criam falhas na linha e marcas vermelhas.
- O gráfico tem contadores compactos:
  - amostras entregues;
  - amostras perdidas;
  - interface e destino do teste;
  - fonte.

Motivo:

O gráfico anterior, "Live handover duration", usava a duração do comando de handover lida nos logs da CU. Isso não é a mesma coisa que a interrupção do plano de usuário. O operador queria ver os pacotes sendo entregues, depois a interrupção, depois a entrega de novo. O gráfico ao vivo baseado em ping mostra exatamente isso.

## Efeito na API e no estado

Estes estados agora incluem a latência ao vivo:

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

Por conveniência, o objeto da visão geral também inclui `overview.live_latency`.

## Validação feita

Validação do backend e do frontend:

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

Teste rápido com o sistema rodando:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up -d --build
```

Depois:

```bash
curl -fsS http://localhost:8000/api/overview
```

Resultado observado:

- O `/api/overview` retornou amostras de latência ao vivo.
- Último teste local observado:
  - `oaitun_ue1 -> 192.168.71.135`;
  - `reachable: true`;
  - `rtt_ms`: cerca de 11,5;
  - `source: docker_exec_ping`.

## Registro do PR e do merge

A limpeza da visão geral e o gráfico ao vivo entraram por:

- PR: <https://github.com/fsnobre/oai-rfsim-handover-testbed/pull/19>
- Commit de merge: `b0f2c6ca838c6c5262883e720aad36775a940a77`

## Notas de operação

Para rodar o painel web com os controles locais do rfsim, use:

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

Para acessar de longe pelo Tailscale:

1. Rode o painel web no Mini PC.
2. Abra o frontend pelo IP Tailscale do Mini PC e pela porta do frontend.

O frontend descobre o endereço do backend pelo endereço usado no navegador, a menos que outro esteja configurado.

O gráfico de latência ao vivo exige que:

- o backend do painel consiga usar o Docker;
- o contêiner `oai-nr-ue` exista e esteja rodando;
- a interface `oaitun_ue1` exista dentro do contêiner do UE;
- o destino `192.168.71.135` no EXT-DN responda.

Se faltar algum desses itens, o gráfico deve mostrar amostras indisponíveis ou perdidas, sem derrubar o painel.

## Limites que continuam

- O gráfico de latência ao vivo faz testes ativos. Eles são limitados e leves, mas não são telemetria passiva.
- A detecção da DU atual depende dos padrões de texto atuais dos logs da CU. Se a OAI mudar o formato dos logs, a leitura pode parar de funcionar.
- A consulta periódica pelo Telnet da CU continua desligada por padrão. Antes, consultas repetidas com `help` deixaram a CU instável.
- O Telnet da DU no F1 continua sem uso.
- Os indicadores de rádio e de MAC, como CQI, MCS, BLER, PHR, RSRP, RSRQ e SINR, continuam indisponíveis. Eles só aparecem se a OAI os expuser por uma fonte de telemetria atual e segura.
- O handover rápido não cria uma execução salva. Os arquivos salvos continuam vindo dos testes rápidos e dos testes repetidos.
- Não há autenticação.

> **ATENÇÃO:** Não exponha um painel web com as ações ligadas em redes não confiáveis. Qualquer pessoa na rede pode comandar o testbed.
