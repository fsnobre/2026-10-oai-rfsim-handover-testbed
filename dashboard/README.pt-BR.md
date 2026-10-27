# Painel do OAI RFsim

> Tradução para o português. O original em inglês é o [README.md](README.md). Em caso de divergência, prevalece o original.

Painel do testbed de handover da OAI em RFsim. A Fase 5 acrescenta observabilidade de campanhas/execuções repetidas e análise comparativa sobre a visão geral ao vivo, o histórico de KPIs, o explorador de execuções, a página gNB, a página UE, a observabilidade de handover/mobilidade e os controles seguros de experimento desabilitados por padrão.

## O que ele faz

- Backend FastAPI com:
  - `GET /health`
  - `GET /api/topology`
  - `GET /api/config`
  - `WebSocket /ws`, transmitindo o estado a cada segundo
- Consulta ao status do Docker por meio de `/var/run/docker.sock`.
- Leitura da configuração F1 a partir de `conf-cu.conf`, `conf-du.conf`, `conf-nr-ue.conf` e das substituições da DU1 em `gnb-docker-compose.yaml`.
- Detecção automática da topologia em execução, para que o painel acompanhe uma implantação ou desmontagem sem reiniciar.
- Consulta opcional, em regime de melhor esforço, ao telnet do nó de controle da topologia atual (a CU F1 em `192.168.70.150:9090`; caso contrário, a gNB/CU de origem da N2), desativada por padrão para preservar a estabilidade da CU da OAI.
- Resumo da última execução a partir de `results/runs/*/summary.json`.
- Histórico de KPIs em memória, com retenção de 10 minutos.
- Número atual de UEs somente quando uma fonte de telemetria atual expõe o contexto de UE conectado.
- Observação separada dos eventos de registro no AMF a partir dos logs recentes do AMF.
- Explorador de artefatos de execução para `results/runs/*`.
- Observabilidade de handover/mobilidade a partir dos artefatos de execução existentes e de leituras de log limitadas e somente leitura.
- Ações de experimento seguras, desabilitadas por padrão, para os scripts confiáveis de handover, teste rápido e implantação/desmontagem de topologia.
- Implantação/desmontagem com um clique de uma pilha completa (F1, N2 monolítica, N2 CU/DU) a partir da página Visão geral, para que os operadores possam trocar de topologia sem a CLI.
- Resumos de campanhas a partir de `results/repeated/*` e dos artefatos vinculados em `results/runs/*`.
- Comparação estatística de grupos de campanhas e topologias.
- Ação segura de campanha de testes rápidos repetidos, desabilitada por padrão.
- Três páginas React: Overview (Visão geral), Results (Runs e Campaigns) e Controls.

## Executar com Docker Compose

A partir da raiz do repositório:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

Abra:

```text
http://localhost:5173
```

API do backend:

```text
http://localhost:8000/api/topology
http://localhost:8000/api/config
http://localhost:8000/api/runs
http://localhost:8000/api/kpi/history
http://localhost:8000/api/ues
http://localhost:8000/api/gnb
http://localhost:8000/api/handover
http://localhost:8000/api/handover/runs
http://localhost:8000/api/handover/durations
http://localhost:8000/api/campaigns
http://localhost:8000/api/campaigns/compare
http://localhost:8000/api/campaigns/export
http://localhost:8000/api/actions/capabilities
http://localhost:8000/api/actions/jobs
```

O backend usa a rede do host, para que o painel ainda consiga iniciar quando o testbed da OAI e as redes Docker estiverem desligados. A consulta passiva ao telnet da CU fica desativada por padrão, porque comandos telnet `help` repetidos podem desestabilizar algumas compilações da CU da OAI. Para ativá-la intencionalmente, inicie o backend com:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

Quando ativada, o backend limita a taxa de consulta e guarda em cache a descoberta de capacidades do telnet, em vez de enviar `help` a cada segundo. As ações explícitas de experimento, como execuções de teste rápido e disparos de handover, continuam separadas da consulta passiva ao telnet.

## Páginas

Uma página por pergunta que o operador de fato faz.

| Página | Rota | Conteúdo |
|---|---|---|
| Overview | `/` | Barra lateral de saúde dos contêineres, diagrama de topologia (as quatro topologias), mobilidade ao vivo, latência do UE ao vivo, contexto do UE, implantação/desmontagem, handover rápido, captura da interrupção, configuração da célula recolhível |
| Results | `/results/runs`, `/results/campaigns` | Explorador de execuções (métricas, traçado do ping com marcadores de handover, linha do tempo dos eventos, fluxo de mensagens) e campanhas de execuções repetidas com comparação |
| Controls | `/controls` | Capacidades das ações, garantias de segurança, verificações em tempo de execução, token da API, teste rápido, lista de jobs e finais de saída |

Consolidado a partir de sete abas. As páginas gNB e UE foram incorporadas à Visão geral; Handover foi unida
ao explorador de execuções, já que ambas leem os mesmos artefatos `results/runs/*` e ambas plotavam
o mesmo traçado de RTT. Os caminhos antigos (`/gnb`, `/ue`, `/handover`, `/runs/:id`, `/campaigns/:id`)
redirecionam, para que os favoritos existentes continuem funcionando.

Duas coisas foram descartadas, em vez de movidas:

- O painel de status da RAN da página gNB duplicava a barra lateral da Visão geral.
- O gráfico de "histórico de vazão" da página gNB plotava `latest_run.iperf_mbps` a partir do buffer circular
  de KPIs, de modo que era uma linha plana que só mudava de degrau quando uma execução terminava. Ele parecia uma
  série de vazão ao vivo, e não era.
- Os blocos de CQI, MCS DL/UL, BLER DL/UL, PHR e DU servidora da página UE foram removidos: nenhum caminho
  de telemetria atual os alimenta, então ficavam permanentemente como "Unavailable". O número de UEs e os eventos
  de registro no AMF, que têm fontes, foram para o cartão de contexto do UE na Visão geral.

## Detecção de topologia

O painel detecta qual topologia está rodando a partir dos contêineres presentes, usando a
mesma ordem de verificação do `detect_topology()` em `scripts/lib.sh` (`oai-cu` → F1, `oai-gnb0` →
N2 monolítica, `oai-cu0` → N2 CU/DU, `oai-gnb` → USRP). Como o próprio painel pode
implantar e desmontar pilhas, isso significa que ele acompanha uma troca de topologia sem reiniciar:
o conjunto de contêineres monitorados, o endpoint de controle telnet e a topologia enviada às
ações de handover mudam todos juntos.

`DASHBOARD_TOPOLOGY` fixa a topologia em vez de detectá-la:

| Valor | Comportamento |
|---|---|
| não definido ou `auto` (padrão) | detecta a partir dos contêineres em execução |
| `f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots` | fixa, pulando a detecção |

A detecção é informada, e não presumida. O estado traz `topology_detection` com
`mode` (`auto`/`pinned`), `detected` (a topologia observada, ou `null`) e `source`
(`container_probe`, `fallback`, `DASHBOARD_TOPOLOGY`). Quando nada identificável está
rodando, a topologia padrão é exibida com `detected: null` e um aviso — nunca um palpite
apresentado como observação.

O endpoint de controle telnet acompanha a topologia: a CU (`192.168.70.150:9090`) na F1,
a gNB de origem (`192.168.70.160:9090`) na N2 monolítica e a CU de origem
(`192.168.70.150:9090`) na N2 CU/DU. O `usrp-cots` não tem nó de controle telnet e informa isso.

A sonda de latência do UE ao vivo só roda quando a topologia detectada tem um contêiner de UE e esse
contêiner está rodando. Antes, ela emitia um `docker exec` com falha a cada segundo sempre que
o testbed estava desligado, e também no `usrp-cots`, em que o UE é um aparelho COTS externo e não existe
contêiner `oai-nr-ue`. Quando a sondagem não é possível, `live_latency.probing` é
`false`, com um `skip_reason`, e as amostras antigas são descartadas, em vez de permanecerem num gráfico
que pareceria ao vivo.

## Coleta de estado

Uma única tarefa em segundo plano coleta o estado e publica um snapshot; o WebSocket e os
endpoints REST baseados em estado (`/api/topology`, `/api/overview`, `/api/gnb`, `/api/handover`)
leem esse snapshot, em vez de cada um reconstruí-lo. O custo da coleta é, portanto, independente
de quantos navegadores estão conectados, e as leituras bloqueantes do SDK do Docker e dos artefatos são
despachadas para fora do loop de eventos.

As fontes são agrupadas em níveis de atualização conforme a velocidade com que de fato mudam:

| Nível | Intervalo padrão | Variável de ambiente | Fontes |
|---|---|---|---|
| rápido | 1 s | `DASHBOARD_POLL_INTERVAL_SECONDS` | status dos contêineres, sonda de latência ao vivo, telnet, jobs de ação |
| médio | 5 s | `DASHBOARD_MEDIUM_INTERVAL_SECONDS` | leituras limitadas de logs do Docker: eventos de handover recentes, registros no AMF, mobilidade na CU |
| lento | 30 s | `DASHBOARD_SLOW_INTERVAL_SECONDS` | configuração processada, lista de execuções, última execução, gráfico de handover, campanhas |

O nível lento é invalidado antes do prazo quando um novo diretório aparece em `results/runs`, para que um
experimento concluído apareça sem esperar o fim do intervalo.

O histórico de KPIs é amostrado uma vez por ciclo rápido pelo coletor. Antes, ele era amostrado
dentro da reconstrução feita por cada leitor, o que fazia a densidade da série depender do número de
abas abertas no navegador; agora, `GET /api/kpi/history` é uma série uniforme de ~1 Hz, independentemente dos leitores.

As leituras de detalhe sob demanda (`/api/runs/{id}`, `/api/handover/runs/{id}`, detalhe de campanha,
`/api/config`) são servidas diretamente, e não a partir do snapshot, para que sempre reflitam
os artefatos atuais.

## Executar localmente para desenvolvimento em modo degradado/offline

Backend:

```bash
cd dashboard/backend
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DASHBOARD_REPO_ROOT=../.. uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd dashboard/frontend
npm install
npm run dev
```

Se o frontend renderizar só o fundo e o console do navegador mostrar `React is not defined`, verifique se `dashboard/frontend/vite.config.js` existe e inclui `@vitejs/plugin-react` e, então, recompile o contêiner do frontend sem cache:

```bash
docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend
```

Espera-se que o painel inicie mesmo quando o testbed da OAI estiver desligado. Contêineres ausentes, problemas no socket do Docker, telnet da CU indisponível e configurações ausentes são expostos como avisos, e não como erros fatais do backend.
A ausência de arquivos históricos `results/runs/*/summary.json` é normal e produz `latest_run: null`.

## Endpoints da Fase 2

- `GET /api/runs` lista os diretórios de execução, com as métricas do resumo quando disponíveis.
- `GET /api/runs/{run_id}` retorna o resumo, os resumos opcionais de ping/iperf, os eventos e amostras de ping limitadas.
- `GET /api/kpi/history` retorna o buffer circular de KPIs em memória.
- `GET /api/ues` retorna a tabela de UEs atual processada, se o telnet da CU a expuser.
- `GET /api/gnb` retorna a configuração da CU/DU, o status dos contêineres, o status do telnet e o histórico de KPIs.
- O `/ws` inclui a topologia atual, os contêineres, o status do telnet, a última execução, um histórico curto de KPIs, avisos e o frescor das fontes.

Artefatos grandes, como os logs brutos completos, intencionalmente não são enviados pelo WebSocket.

## Endpoints de handover da Fase 3

- `GET /api/handover` retorna a prontidão de mobilidade atual (melhor esforço), o alcance do telnet da CU/origem, eventos recentes derivados de logs limitados e avisos.
- `GET /api/handover/runs` retorna resumos orientados a handover de todos os diretórios `results/runs/*`.
- `GET /api/handover/runs/{run_id}` retorna os eventos normalizados, o fluxo de mensagens, os marcadores de interrupção do ping, amostras de ping limitadas e os avisos de uma execução.
- `GET /api/handover/message-flow/{run_id}` retorna apenas as etapas reconstruídas do fluxo de mensagens.
- `GET /api/handover/durations` retorna linhas de duração de handover prontas para tabela.

Valores de confiança dos eventos de handover:

- `observed`: presente diretamente no `events.csv` ou em outro artefato estruturado.
- `parsed`: extraído de texto limitado de log do Docker ou do telnet.
- `inferred`: derivado de métricas do resumo, como `estimated_interruption_ms` ou `first_ping_after_handover_ms`.

A reconstrução do fluxo de mensagens é de melhor esforço. O `events.csv` é a fonte principal; os `docker_logs/*.log` coletados e os finais de log do Docker ao vivo podem acrescentar indícios extraídos. A leitura dos logs Docker dos artefatos lê apenas os últimos 512 KiB de cada arquivo de log e mantém no máximo 30 eventos extraídos correspondentes por arquivo. A leitura dos logs Docker ao vivo usa finais de log limitados. Endpoints desconhecidos permanecem `Unknown`, em vez de serem inferidos a partir dos nomes da topologia.

## Controles seguros da Fase 4

As ações ficam desabilitadas, a menos que o backend seja iniciado com:

```bash
DASHBOARD_ENABLE_ACTIONS=true
```

Para ações disparadas pelo painel que iniciam pilhas Docker Compose da OAI, o backend controla o daemon Docker do host por meio de `/var/run/docker.sock`. Os caminhos de bind mount do Docker são interpretados pelo daemon do host, então `DASHBOARD_REPO_ROOT` precisa ser um caminho absoluto que exista no host, e não apenas um apelido dentro do contêiner, como `/repo`. Use o override host-actions a partir da raiz do repositório:

> **Isto é garantido, e não apenas documentado.** O Docker não falha quando a origem de um bind mount não existe — ele cria silenciosamente um diretório vazio. Sem o override, uma pilha iniciada pelo painel monta diretórios vazios onde deveriam estar o `config.yaml` e o banco de dados de assinantes, o 5GC nunca sobe e sobra lixo pertencente ao root no host. Por isso, o backend compara `DASHBOARD_REPO_ROOT` com a origem, do lado do host, do seu próprio bind mount e **recusa implantação, desmontagem, teste rápido e teste rápido repetido com HTTP 409** quando eles não coincidem, indicando o comando correto. As ações que usam só telnet/ping (disparo de handover, captura da interrupção) não são afetadas. O bloqueio exige evidência positiva de divergência: se o mount não puder ser inspecionado, ou se o backend não estiver em contêiner, as ações seguem como antes.

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

O arquivo Compose base monta `/dev/net/tun` no `dashboard-backend`; `network_mode: host` sozinho não expõe os dispositivos de `/dev`. O override mantém a mesma montagem do TUN e monta o repositório no caminho absoluto visível no host, com apenas `results/` gravável.

Se o painel já estiver rodando com as ações desabilitadas, recrie apenas o backend com:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Ou reinicie o painel completo com:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

O indicador de habilitação é lido na inicialização do backend. Definir a variável no shell depois que o backend já está rodando não habilita as ações nesse processo em execução.

Endpoints de ação:

- `GET /api/actions/capabilities` informa se as ações estão habilitadas e lista as garantias de segurança.
- `POST /api/actions/trigger-handover` inicia um job confiável de handover para a topologia ativa, quando habilitado e confirmado.
- `POST /api/actions/deploy-topology` sobe uma pilha completa via `scripts/up.sh <topologia>` (`f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots`), quando habilitado e confirmado.
- `POST /api/actions/teardown-topology` derruba uma pilha via `scripts/down.sh <topologia>`, quando habilitado e confirmado.
- `POST /api/actions/smoke-test` inicia um job confiável de teste rápido para `f1`, `n2-monolithic` ou `n2-cu-du`, quando habilitado e confirmado.
- `POST /api/actions/repeated-smoke-test` inicia uma campanha confiável de testes rápidos repetidos, quando habilitado e confirmado.
- `GET /api/actions/jobs` lista os jobs iniciados pelo painel, sem os finais de saída completos.
- `GET /api/actions/jobs/{job_id}` retorna os detalhes do job, com finais limitados de stdout/stderr.

Garantias de segurança:

- Desabilitado por padrão.
- Nenhum comando arbitrário.
- Nenhuma execução de shell; os subprocessos usam arrays de argumentos fixos.
- Somente scripts da lista de permissões: `scripts/trigger_handover.sh`, `scripts/measure_interruption.sh`, `scripts/up.sh`, `scripts/down.sh`, `scripts/run_smoke_test.sh` e `scripts/run_repeated_smoke_tests.sh`. Cada um é invocado com um array de argumentos fixo; o único parâmetro livre é um nome de topologia verificado contra uma lista fechada. Nenhum ciclo de vida arbitrário de contêineres: a implantação/desmontagem só pode executar esses dois scripts para uma topologia da lista.
- As ações são executadas dentro do contêiner do backend do painel.
- A raiz do repositório é usada como diretório de trabalho dos subprocessos.
- A montagem padrão em `/repo` basta para o uso do painel somente leitura. Para ações que invocam o Docker Compose do host, use `dashboard/docker-compose.dashboard.host-actions.example.yml`, para que `DASHBOARD_REPO_ROOT` seja visível no host.
- A montagem do repositório permanece somente leitura, exceto `results/`, que é montado com leitura e escrita para que os testes rápidos possam criar os artefatos `results/runs/*` e o `trigger_handover.sh` possa acrescentar eventos no `RUN_DIR` de um teste rápido.
- `/dev/net/tun` é montado no contêiner do backend para os scripts que precisam do suporte a TUN do UE.
- A imagem do backend inclui as ferramentas mínimas de CLI/rede exigidas pelos scripts confiáveis: `bash`, Docker CLI com Compose v2, `nc`, `ip`, `ss`, `ping` e `python3`.
- O socket do Docker montado é usado para interagir com o daemon Docker local; nenhum daemon Docker roda dentro do contêiner do backend.
- As ações que criam pilhas Compose são recusadas quando a raiz do repositório não está visível para o daemon Docker do host no mesmo caminho (`runtime_checks.repo_root_host_visible`, exibido como um aviso na página Controls).
- Apenas um job de ação iniciado pelo painel pode rodar por vez.
- Os finais de stdout/stderr são limitados a 200 linhas cada.
- O tratamento de tempo limite das ações encerra o grupo de processos inteiro, primeiro com SIGTERM e depois com SIGKILL, após um curto período de tolerância.
- O estado dos jobs fica apenas em memória e é zerado quando o backend reinicia.

Não exponha o painel em redes não confiáveis quando as ações estiverem habilitadas.

## Autenticação e CORS

A autenticação é opcional e fica desativada por padrão (padrão de laboratório); portanto, nada muda a menos que você a configure.

- `DASHBOARD_API_TOKEN` — quando definida com um valor não vazio, todos os endpoints `/api/actions/*` e o WebSocket `/ws` exigem o token. As chamadas REST precisam enviar `Authorization: Bearer <token>`; o WebSocket precisa conectar com `?token=<token>`. Quando não definida, nenhuma autenticação é exigida. Requisições sem token ou com token errado recebem HTTP 401 (código de fechamento 1008 no WebSocket).
- `DASHBOARD_CORS_ORIGINS` — origens permitidas, separadas por vírgula (por exemplo, `https://ops.example.com,https://lab.internal`). O padrão é `*`, para preservar o comportamento anterior de laboratório. Defina uma lista explícita para qualquer coisa acessível além do localhost. O CORS com credenciais não é habilitado: o token trafega num cabeçalho `Authorization`, e não num cookie, e `*` combinado com credenciais é uma configuração que os navegadores rejeitam de qualquer forma.

No frontend, defina o token na página **Controls** (cartão "API token"). Ele é armazenado no navegador e anexado às requisições de ação e ao WebSocket ao vivo; recarregue a página depois de alterá-lo, para que o socket se autentique novamente.

Isto é defesa em profundidade, e não um substituto do isolamento de rede: continue sem expor o painel em redes não confiáveis quando as ações estiverem habilitadas, porque o backend comanda o daemon Docker do host.

Inicie o backend com a autenticação habilitada, por exemplo:

```bash
DASHBOARD_API_TOKEN="$(openssl rand -hex 24)" \
DASHBOARD_CORS_ORIGINS="http://localhost:5173" \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

## Campanhas da Fase 5

Endpoints de campanhas:

- `GET /api/campaigns` lista as campanhas de execuções repetidas encontradas.
- `GET /api/campaigns/{campaign_id}` retorna uma campanha, com linhas por execução, estatísticas, valores atípicos e avisos.
- `GET /api/campaigns/compare` retorna resumos prontos para comparação, agrupados por topologia e campanha.
- `GET /api/campaigns/export` retorna linhas JSON planas, adequadas para conversão em CSV no cliente. Ele não grava arquivos.

Premissas sobre os artefatos:

- As campanhas são encontradas em `results/repeated/*`.
- O script de testes rápidos repetidos grava `runs.txt`, `summary.csv`, `summary.json` e logs por execução em cada diretório de campanha.
- Os diretórios de execução vinculados em `results/runs/*` continuam sendo a fonte de verdade das métricas por execução quando o `summary.json` está disponível.
- Artefatos opcionais ausentes ou malformados geram avisos, em vez de falhas do backend.

Estatísticas:

- As estatísticas numéricas das campanhas são calculadas para a interrupção do handover, o primeiro ping após o handover, a perda de pacotes, a média do RTT e a vazão do iperf.
- Valores `null`/ausentes são ignorados nas estatísticas numéricas.
- Se não houver valores válidos para uma métrica, suas estatísticas são `null`.
- As estatísticas informadas são `min`, `mean`, `median`, `p95` por posição mais próxima (nearest-rank) e `max`.
- Os valores atípicos são listas ordenadas simples: execuções com falha, disparo de handover ausente, métricas de ping ausentes, maior interrupção, maior perda de pacotes, maior RTT e menor vazão do iperf.

Ação de testes rápidos repetidos:

- Endpoint: `POST /api/actions/repeated-smoke-test`.
- Formato da requisição: `{"confirm": true, "topology": "f1", "count": 5}`.
- As topologias permitidas são `f1`, `n2-monolithic` e `n2-cu-du`.
- O número de repetições é limitado de 1 a 20.
- O script confiável é chamado com argumentos fixos e `RUNS=<count>` numa substituição controlada do ambiente.
- A ação usa a mesma proteção desabilitada por padrão, a concorrência de um único job, o tratamento de tempo limite por grupo de processos e os finais de saída limitados da Fase 4.

## Estado ocioso

Quando não existe nenhum contêiner de CU, DU, gNB ou UE, não há topologia para desenhar. A Visão geral
mostra um painel explícito "No topology deployed" (nenhuma topologia implantada), listando as topologias que podem ser implantadas, em vez
de renderizar a topologia padrão com todos os nós parados — o que se lia como "a pilha F1
está implantada e quebrada" e nomeava uma pilha que o operador nunca escolheu. Da mesma forma, a barra lateral
oculta os nós de RAN da topologia padrão e mantém apenas os contêineres do núcleo, que são compartilhados por todas as
topologias e, portanto, uma observação real. Um núcleo rodando sem RAN é sinalizado
separadamente, já que a implantação vai reutilizá-lo.

A implantação é avaliada pela existência observada dos contêineres, e não pelo nome da topologia
detectada; por isso, também fica correta quando a topologia está fixada. Se o próprio Docker estiver inalcançável,
a visão normal é mantida: ausência de evidência não é evidência de ausência.

O campo `status` de nível superior reflete isso com um terceiro valor:

| Valor | Significado |
|---|---|
| `ok` | uma topologia está implantada e seus contêineres obrigatórios estão no ar |
| `idle` | não existe nenhum contêiner de RAN — nada está implantado |
| `degraded` | um aviso foi emitido, ou uma pilha implantada tem um contêiner obrigatório parado |

O `topology_detection` separa `warning` (um problema real: Docker inalcançável, ou uma fixação
`DASHBOARD_TOPOLOGY` desconhecida) de `note` (um host ocioso). Apenas o `warning` alimenta a
lista global de avisos, de modo que uma máquina ociosa não se informa mais como degradada.

## Semântica da prontidão de mobilidade

O `handover.readiness` distingue o que foi observado do que nunca foi verificado:

| Valor | Significado |
|---|---|
| `ready` | o telnet foi consultado e o nó de controle respondeu |
| `degraded` | o telnet foi consultado e não respondeu |
| `not_observed` | nada sondou o nó de controle — a consulta passiva está desativada (o padrão), ou a topologia não tem endpoint telnet |
| `unavailable` | um contêiner obrigatório não está rodando |

O `handover.cu_telnet_status` traz a mesma distinção como `reachable`, `unreachable`,
`polling_disabled` ou `no_endpoint`. Apenas `unreachable` — uma sondagem que de fato falhou —
gera um aviso. Informar o caso desativado por padrão como "não alcançável" afirmava uma
falha que nunca foi observada e, como os avisos determinam o campo `status` geral,
deixava uma pilha perfeitamente saudável marcada como `degraded` indefinidamente.

Pelo mesmo motivo, uma topologia cujos arquivos `.conf` não são processados traz uma `note` na
carga de configuração, em vez de um aviso: um limite de escopo conhecido não é uma anomalia.

## Semântica da telemetria do UE

- `live_kpis.ue_count` significa apenas o contexto de UE conectado atual. Ele é preenchido a partir do telnet da CU, ou de outra fonte de estado atual verdadeira, se uma for adicionada no futuro.
- Se o telnet da CU estiver indisponível ou não expuser um contexto de UE que possa ser processado, `live_kpis.ue_count` permanece `null` e a interface o mostra como Unavailable.
- As correspondências recentes nos logs do AMF são expostas separadamente como `live_kpis.amf_registration_events_seen`, com fonte `amf_logs_tail` e janela `last_500_log_lines`.
- As correspondências de eventos de registro no AMF não são uma contagem de conexões atuais. Testes repetidos, ciclos de desconexão/reconexão e tentativas com falha podem fazer com que elas difiram dos UEs conectados no momento.

## Validação

Verifique se o registro do painel ainda corresponde aos arquivos Compose atuais:

```bash
cd dashboard/backend
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_registry.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase2.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase3.py
```

Validação completa a partir da raiz do repositório:

```bash
python3 -m compileall dashboard/backend
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_registry.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase2.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase3.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase4.py
PYTHONPATH=dashboard/backend DASHBOARD_REPO_ROOT=. python3 dashboard/backend/validate_phase5.py
docker compose -f dashboard/docker-compose.dashboard.yml config
python3 scripts/validate_cn_subscriber.py
cd dashboard/frontend && npm install && npm run build
git diff --check
```

## Diagnóstico do assinante no teste rápido F1

O UE RFsim usa o IMSI `001010000000001`, a chave `fec86ba6eb707ed08905757b1bb44b8f`, o OPC `C42449363BBAD02B66D16BC975D77CC1`, a DNN `oai` e a fatia SST `1` / SD `FFFFFF`. O seed SQL inclui os dois apelidos de autenticação do SUPI, o numérico e o canônico: `001010000000001` e `imsi-001010000000001`.

Valide o seed versionado com:

```bash
python3 scripts/validate_cn_subscriber.py
```

Se o `wait_ue_data_ready.sh` atingir o tempo limite com a `oaitun_ue1` ausente, ele agora imprime diagnósticos focados do UE/AMF/AUSF/UDM/UDR/MySQL. Se os logs mostrarem `CONTEXT_NOT_FOUND` ou se o MySQL não estiver saudável, recrie o banco do núcleo a partir do seed SQL atualizado:

```bash
./scripts/down.sh f1 --volumes
./scripts/up.sh f1
```

O `--volumes` é destrutivo para o estado persistido gerenciado pelo Compose e se destina apenas a reinicializar o laboratório/testbed.

## Limitações

- Sem botões de ciclo de vida.
- Sem edição de configuração.
- Sem controles amplos de ciclo de vida dos contêineres.
- A Fase 4 só pode disparar scripts confiáveis quando `DASHBOARD_ENABLE_ACTIONS=true`.
- A Fase 5 só pode iniciar campanhas de testes rápidos repetidos quando `DASHBOARD_ENABLE_ACTIONS=true`.
- Há autenticação opcional por token bearer (`DASHBOARD_API_TOKEN`), desativada por padrão; mesmo assim, não exponha as ações em redes não confiáveis.
- O handover rápido e a captura da interrupção da Visão geral acompanham a topologia detectada (`f1`, `n2-monolithic`, `n2-cu-du`) por meio das ações da lista de permissões. A N2 usa a PCI de destino / ID RRC do UE padrão configurados; não há interface de seleção de origem/destino, e redisparar a N2 no mesmo sentido exige reinicializar a topologia.
- O diagrama de topologia é desenhado para as quatro topologias a partir do registro de contêineres. Os endereços dos nós são valores do registro, e não da configuração processada, de modo que continuam corretos onde a leitura dos `.conf` não está implementada. O parser de configuração detalhado continua restrito à F1; por isso, só os nós da F1 mostram parâmetros de célula como a PCI; as outras topologias informam isso, em vez de mostrar uma configuração com formato de F1.
- O destaque da célula servidora só aparece quando uma fonte de telemetria de fato a informa. Na prática, isso significa F1 com leitura dos logs da CU; as topologias N2 mostram "serving cell not observed" (célula servidora não observada), em vez de destacar um palpite. O diagrama da USRP marca o aparelho COTS como fora da pilha monitorada, já que ele não tem contêiner.
- As comparações de campanhas são derivadas dos artefatos e não fabricam métricas ausentes nem inferem status de campanha indisponível.
- Não há leitura do telnet da DU na F1; os contêineres de DU F1 atuais não expõem telnet.
- Os eventos de handover e as etapas do fluxo de mensagens derivados de logs são de melhor esforço e limitados; os logs dos artefatos são processados a partir de um final de 512 KiB, e os detalhes de protocolo indisponíveis permanecem `null`, vazios ou Unavailable.
- Os KPIs de RF/MAC ao vivo só são mostrados quando a saída do telnet da OAI em execução os expõe. Caso contrário, são `null`/Unavailable. Nenhum caminho de telemetria atual alimenta CQI, MCS, BLER, PHR ou DU servidora; por isso, esses blocos foram removidos da interface, em vez de aparecerem permanentemente indisponíveis; os campos `live_kpis` continuam na API para uma futura fonte via telnet ou xApp.
- Um contexto de UE atual indisponível permanece `null`; as correspondências de registro derivadas dos logs do AMF são mostradas separadamente, como eventos recentes.
- As métricas de RF do RFsim, como RSRP/RSRQ/SINR, podem ser sintéticas ou indisponíveis.
- A leitura da configuração continua focada na F1; as topologias futuras estão representadas no registro para a descoberta de contêineres.
