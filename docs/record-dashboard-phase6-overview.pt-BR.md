# Painel, Fase 6: visão geral do operador

> Tradução para o português. O original em inglês é o [record-dashboard-phase6-overview.md](record-dashboard-phase6-overview.md). Em caso de divergência, prevalece o original.

Data: 01/07/2026

## Objetivo

A Fase 6 transforma a Visão geral do painel no principal cockpit do operador para demonstrações F1 em RFsim. O painel existente já expõe a saúde dos contêineres, os artefatos das execuções, a observabilidade do handover, as campanhas e controles seguros. A Visão geral deve combinar as partes mais úteis para que o operador possa ver o testbed atual, disparar um handover F1 seguro em RFsim e inspecionar visualmente a interrupção na entrega de pacotes sem trocar de aba.

## Fluxo de trabalho do operador

1. Inicie o painel com as ações habilitadas quando forem necessárias ações controladas de experimento:

   ```bash
   DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
     docker compose -f dashboard/docker-compose.dashboard.yml \
       -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
   ```

2. Abra a Visão geral.
3. Confirme que os contêineres do núcleo/RAN/UE estão saudáveis na barra lateral agrupada e recolhível e no diagrama da topologia.
4. Use o destaque da topologia para ver a DU servidora quando os logs da CU a expuserem.
5. Use o controle "Quick handover" (handover rápido) nas demonstrações em RFsim.
6. Inspecione o gráfico de latência do UE ao vivo. Sondas bem-sucedidas mostram o RTT; sondas perdidas criam lacunas/marcadores vermelhos, de modo que uma interrupção de handover aparece como pacotes entregues, depois uma lacuna e, em seguida, a recuperação.

A Visão geral evita intencionalmente mostrar todos os campos disponíveis. A faixa superior de informações da topologia, os cartões de saúde duplicados, os cartões de status de ações duplicados, o cartão de detalhes de mobilidade e os cartões de resumo de execuções salvas foram omitidos de propósito. As tabelas detalhadas continuam nas páginas gNB, UE, Runs, Handover, Controls e Campaigns.

## Modelo de dados

O backend expõe um objeto orientado à Visão geral por meio de:

- `GET /api/overview`
- `/ws` como `state.overview`

O objeto contém:

- `ue_paths`: linhas com o caminho mais bem conhecido de cada UE, com a DU servidora atual mostrada somente quando observada.
- `latest_metrics`: métricas da última execução para interrupção, RTT, perda de pacotes e iperf.
- `handover_chart`: amostras de ping de execuções salvas prontas para gráfico, para as APIs que precisarem delas; a Visão geral prioriza as sondas de latência ao vivo.
- `live_latency`: histórico limitado de sondas ICMP ao vivo do `oai-nr-ue`, pela `oaitun_ue1`, para `192.168.71.135`.
- `actions`: se o disparo rápido é suportado/está habilitado e qual job está em execução no momento.
- `handover`: campos compactos de prontidão de mobilidade ao vivo, incluindo o estado de mobilidade extraído de forma limitada dos logs da CU, quando disponível.
- `warnings`: avisos específicos da Visão geral.

Cada linha de caminho de UE inclui:

- `ue_id`
- `serving_du`
- `path`, por exemplo `["UE", "DU1", "CU", "UPF", "EXT-DN"]`
- `metrics`
- `source`
- `confidence`
- `warnings`

Valores de confiança:

- `observed`: vem diretamente da telemetria atual processada do UE, como o contexto do UE no telnet da CU.
- `parsed`: extraído de logs limitados ou de telemetria textual.
- `inferred`: derivado dos artefatos da última execução.
- `unknown`: existe contexto de contêiner/configuração, mas nenhuma fonte atual ou de artefato consegue identificar a conexão.

Regras de exibição no frontend:

- Se a DU servidora não for observada, a Visão geral não deve renderizar `UE → Unknown → CU` como caminho principal. Ela deve mostrar "DU not observed" (DU não observada) e explicar que o estado atual da DU servidora não está disponível pela telemetria habilitada.
- As métricas da última execução ainda podem ser mostradas como evidência, mas devem ficar visualmente separadas do estado atual de conexão.
- Quando os logs da CU expõem a conclusão do handover F1, a DU servidora é extraída mapeando o `cellID` pós-handover para os IDs de célula da configuração das DUs. Na configuração F1 atual, `12345678` corresponde à DU0 e `11111111` à DU1.
- A Visão geral não deve mostrar métricas de execuções salvas como cartões principais. Os dados de execuções salvas pertencem a Handover/Runs, com no máximo uma pequena referência, se útil.
- O gráfico principal da Visão geral é o de entrega de pacotes/latência ao vivo. Ele não deve rotular a duração do comando de handover no log da CU como interrupção de pacotes.

## Comportamento de segurança

- O disparo "Quick handover" da Visão geral usa o endpoint existente `POST /api/actions/trigger-handover`.
- Ele nunca introduz um comando de handover genérico.
- Ele só fica habilitado quando:
  - as ações do backend estão habilitadas com `DASHBOARD_ENABLE_ACTIONS=true`;
  - a topologia é F1/RFsim;
  - nenhum job de ação iniciado pelo painel já está em execução;
- a pilha F1 está intencionalmente ativa.
- Ele mantém as garantias de segurança da Fase 4:
  - nenhum comando arbitrário;
  - nenhuma execução de shell;
  - argv fixo de script confiável;
  - concorrência de um único job;
  - finais de saída limitados.

O handover rápido é uma ação de controle. Ele usa um aviso embutido em vez de uma caixa de confirmação, para que demonstrações repetidas em RFsim continuem rápidas. Ele pode atualizar o estado de mobilidade ao vivo extraído dos logs da CU. O gráfico de latência da Visão geral é independente dos testes rápidos salvos e amostra continuamente a entrega de pacotes enquanto o painel está aberto.

## Limites da telemetria

- O telnet da DU F1 continua sem uso.
- A DU servidora só é mostrada quando observada ou extraída. Caso contrário, ela é `Unknown`.
- KPIs de RF/MAC como CQI, MCS, BLER, PHR, RSRP, RSRQ e SINR continuam indisponíveis, a menos que a OAI os exponha por uma fonte de telemetria atual e segura.
- As métricas derivadas de artefatos são rotuladas como `inferred` e não devem ser apresentadas como estado atual de conexão ao vivo.
- Um handover rápido pode atualizar o campo da DU servidora quando os logs da CU incluem linhas de conclusão de handover que possam ser processadas. Se esses padrões mudarem ou os logs estiverem indisponíveis, a DU servidora continua como "DU not observed".
- A latência ao vivo usa sondas limitadas `docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135`. Se o Docker, o contêiner do UE, a interface do túnel ou o EXT-DN estiverem indisponíveis, as amostras são registradas como perdidas/indisponíveis, em vez de derrubar o painel.
- A consulta passiva ao telnet da CU continua desativada por padrão com `DASHBOARD_ENABLE_TELNET_POLLING=false`.

## Expectativas de validação

Backend:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase6.py
```

Frontend:

```bash
cd dashboard/frontend
npm install
npm run build
```

Teste rápido em execução:

- A Visão geral é renderizada com a pilha da OAI desligada.
- A Visão geral é renderizada sem execuções históricas.
- O gráfico de latência ao vivo da Visão geral renderiza amostras de sondas entregues/perdidas quando o plano de dados do UE está disponível e, caso contrário, estados úteis de vazio/indisponível.
- O disparo rápido fica desabilitado quando as ações estão desabilitadas.
- O disparo rápido inicia um job quando as ações estão habilitadas.
