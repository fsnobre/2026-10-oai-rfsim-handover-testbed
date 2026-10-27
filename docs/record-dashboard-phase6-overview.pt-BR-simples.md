# Painel web, fase 6: visão geral para o operador

> Tradução para o português em Linguagem Simples. O original em inglês é o [record-dashboard-phase6-overview.md](record-dashboard-phase6-overview.md). Se houver diferença entre os dois, vale o original.

Data: 01/07/2026

## Finalidade

A fase 6 transforma a página Overview (visão geral) do painel web na principal tela de comando do operador nas demonstrações do F1 em rfsim. O painel já mostrava:

- a saúde dos contêineres;
- os arquivos das execuções;
- a observação do handover;
- as campanhas;
- controles seguros.

A visão geral deve juntar as partes mais úteis. Assim, sem trocar de aba, o operador consegue:

- ver o testbed atual;
- comandar um handover F1 seguro em rfsim;
- ver a interrupção na entrega de pacotes.

## Como o operador usa

1. Se precisar das ações controladas do experimento, suba o painel web com as ações ligadas:

   ```bash
   DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
     docker compose -f dashboard/docker-compose.dashboard.yml \
       -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
   ```

2. Abra a página Overview.
3. Confirme, na barra lateral agrupada e no diagrama da topologia, que os contêineres do núcleo 5G, da RAN e do UE estão saudáveis.
4. Veja no destaque da topologia qual DU atende o UE, quando os logs da CU mostram essa informação.
5. Use o controle "Quick handover" (handover rápido) nas demonstrações em rfsim.
6. Acompanhe o gráfico de latência do UE ao vivo. Os pings que deram certo mostram o RTT. Os pings perdidos criam falhas na linha ou marcas vermelhas. Assim, a interrupção do handover aparece como pacotes entregues, depois uma falha, depois a recuperação.

A visão geral não mostra todos os campos disponíveis, de propósito. Ela deixa de fora:

- a faixa de informações da topologia no topo;
- os cartões repetidos de saúde e de estado das ações;
- o cartão de detalhes da mobilidade;
- os cartões de resumo das execuções salvas.

As tabelas detalhadas continuam nas páginas gNB, UE, Runs, Handover, Controls e Campaigns.

## Modelo de dados

O backend envia um objeto próprio da visão geral por:

- `GET /api/overview`;
- `/ws`, no campo `state.overview`.

O objeto tem:

- `ue_paths`: o caminho mais provável de cada UE. A DU atual só aparece quando foi observada.
- `latest_metrics`: as métricas da última execução: interrupção, RTT, perda de pacotes e iperf.
- `handover_chart`: amostras de ping das execuções salvas, prontas para gráfico, para as APIs que precisam delas. A visão geral dá prioridade aos testes de latência ao vivo.
- `live_latency`: histórico limitado dos testes ICMP ao vivo, do `oai-nr-ue` pela `oaitun_ue1` até `192.168.71.135`.
- `actions`: se o comando rápido está disponível e ligado, e qual tarefa está rodando.
- `handover`: campos resumidos da prontidão para mobilidade ao vivo. Quando possível, inclui o estado de mobilidade lido de um trecho limitado dos logs da CU.
- `warnings`: avisos próprios da visão geral.

Cada linha de caminho de UE tem:

- `ue_id`;
- `serving_du`;
- `path`, por exemplo `["UE", "DU1", "CU", "UPF", "EXT-DN"]`;
- `metrics`;
- `source`;
- `confidence`;
- `warnings`.

Valores de confiança (`confidence`):

- `observed`: vem direto da telemetria atual do UE, como o contexto do UE no Telnet da CU.
- `parsed`: vem de um trecho limitado dos logs ou de telemetria em texto.
- `inferred`: vem dos arquivos da última execução.
- `unknown`: há contexto de contêiner ou de configuração, mas nenhuma fonte atual ou salva identifica a conexão.

Regras de exibição no frontend:

- Se a DU atual não foi observada, a visão geral não pode mostrar `UE → Unknown → CU` como caminho principal. Ela deve mostrar "DU not observed" (DU não observada). Ela também deve explicar que a telemetria ligada não informa a DU atual.
- As métricas da última execução podem aparecer como evidência. Mas elas devem ficar visualmente separadas do estado atual de conexão.
- Quando os logs da CU mostram a conclusão de um handover F1, o painel descobre a DU atual pelo `cellID` depois do handover. Ele compara esse valor com os identificadores de célula das configurações das DUs. Na configuração atual do F1, `12345678` é a DU0, e `11111111` é a DU1.
- A visão geral não deve mostrar métricas de execuções salvas como cartões principais. Esses dados ficam nas páginas Handover e Runs. Na visão geral, no máximo, cabe uma referência pequena.
- O gráfico principal da visão geral mostra a entrega de pacotes e a latência ao vivo. Ele não deve chamar de interrupção de pacotes a duração do comando de handover lida nos logs da CU.

## Segurança

- O "Quick handover" da visão geral usa o endpoint que já existe, `POST /api/actions/trigger-handover`.
- Ele nunca cria um comando de handover genérico.
- Ele só fica ligado quando:
  - as ações do backend estão ligadas com `DASHBOARD_ENABLE_ACTIONS=true`;
  - a topologia é F1 em rfsim;
  - nenhuma tarefa iniciada pelo painel está rodando;
  - a pilha do F1 está ativa, de propósito.
- Ele mantém as garantias de segurança da fase 4:
  - nenhum comando arbitrário;
  - nenhuma execução em shell;
  - lista fixa e confiável de argumentos do script;
  - uma tarefa por vez;
  - saída limitada às últimas linhas.

O handover rápido é uma ação de controle. Ele mostra um aviso na própria tela, em vez de pedir para marcar uma caixa. Assim, as demonstrações repetidas em rfsim ficam rápidas. Ele pode atualizar o estado de mobilidade lido dos logs da CU. O gráfico de latência da visão geral não depende dos testes rápidos salvos. Ele mede a entrega de pacotes sem parar, enquanto o painel está aberto.

## Limites da telemetria

- O Telnet da DU no F1 continua sem uso.
- A DU atual só aparece quando foi observada ou lida dos logs. Nos outros casos, ela aparece como `Unknown`.
- Os indicadores de rádio e de MAC, como CQI, MCS, BLER, PHR, RSRP, RSRQ e SINR, continuam indisponíveis. Eles só aparecem se a OAI os expuser por uma fonte de telemetria atual e segura.
- As métricas tiradas de arquivos salvos são marcadas como `inferred`. Elas não podem aparecer como estado de conexão atual.
- Um handover rápido pode atualizar a DU atual, se os logs da CU tiverem linhas de conclusão do handover que o painel saiba ler. Se esses padrões mudarem ou os logs faltarem, a DU atual continua como "DU not observed".
- A latência ao vivo usa testes limitados: `docker exec oai-nr-ue ping -I oaitun_ue1 -c 1 -W 1 192.168.71.135`. Se o Docker, o contêiner do UE, a interface do túnel ou o EXT-DN não estiverem disponíveis, o painel registra as amostras como perdidas ou indisponíveis. O painel não cai.
- A consulta periódica pelo Telnet da CU continua desligada por padrão, com `DASHBOARD_ENABLE_TELNET_POLLING=false`.

## O que validar

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

Teste rápido com o sistema rodando:

- A visão geral aparece com a pilha da OAI desligada.
- A visão geral aparece sem nenhuma execução histórica.
- O gráfico de latência ao vivo mostra amostras entregues e perdidas quando o plano de usuário do UE está disponível. Nos outros casos, ele mostra estados úteis de vazio ou de indisponível.
- O comando rápido fica desligado quando as ações estão desligadas.
- O comando rápido inicia uma tarefa quando as ações estão ligadas.
