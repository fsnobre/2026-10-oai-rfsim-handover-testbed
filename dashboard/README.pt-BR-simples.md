# Painel web do testbed OAI em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [README.md](README.md). Se houver diferença entre os dois, vale o original.

Painel web do testbed de handover da OAI no simulador de rádio (rfsim). A fase 5 acrescenta a observação de campanhas e de execuções repetidas, com análise comparativa. Ela se soma ao que já existia:

- visão geral ao vivo;
- histórico de indicadores;
- explorador de execuções;
- páginas da gNB e do UE;
- observação do handover e da mobilidade;
- controles seguros de experimento, desligados por padrão.

## O que o painel faz

- Backend FastAPI com:
  - `GET /health`
  - `GET /api/topology`
  - `GET /api/config`
  - `WebSocket /ws`, que envia o estado a cada segundo
- Consulta do estado do Docker por `/var/run/docker.sock`.
- Leitura da configuração do F1 a partir de `conf-cu.conf`, `conf-du.conf`, `conf-nr-ue.conf` e dos ajustes da DU1 no `gnb-docker-compose.yaml`.
- Detecção automática da topologia em execução. Assim, o painel acompanha uma subida ou uma derrubada sem precisar reiniciar.
- Consulta opcional, sem garantia, pelo Telnet do nó de controle da topologia atual: a CU do F1 em `192.168.70.150:9090`, ou a gNB/CU de origem no N2. Ela vem desligada por padrão, para a estabilidade da CU da OAI.
- Resumo da última execução, a partir de `results/runs/*/summary.json`.
- Histórico de indicadores em memória, guardado por 10 minutos.
- Número atual de UEs, só quando uma fonte de telemetria atual mostra o contexto de UE conectado.
- Observação separada dos eventos de registro no AMF, a partir dos logs recentes do AMF.
- Explorador dos arquivos das execuções em `results/runs/*`.
- Observação do handover e da mobilidade, a partir dos arquivos das execuções e de leituras limitadas de logs, sem alterar nada.
- Ações seguras de experimento, desligadas por padrão, para scripts confiáveis de handover, de teste rápido e de subida e derrubada de topologias.
- Subida e derrubada de uma pilha completa (F1, N2 monolítica ou N2 CU/DU) com um clique, na página Overview. Assim, o operador troca de topologia sem usar a linha de comando.
- Resumos de campanhas, a partir de `results/repeated/*` e dos arquivos ligados em `results/runs/*`.
- Comparação estatística entre grupos de campanhas e entre topologias.
- Ação segura de campanha de testes rápidos repetidos, desligada por padrão.
- Três páginas React: Overview (visão geral), Results (resultados: execuções e campanhas) e Controls (controles).

## Rodar com o Docker Compose

Na raiz do repositório:

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

O backend usa a rede do computador (*host networking*). Assim, o painel sobe mesmo com o testbed da OAI e as redes Docker fora do ar.

A consulta periódica pelo Telnet da CU vem desligada por padrão. Comandos `help` repetidos pelo Telnet podem deixar instáveis algumas versões da CU da OAI. Para ligá-la de propósito, suba o backend com:

```bash
DASHBOARD_ENABLE_TELNET_POLLING=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

Ligada, a consulta tem limite de frequência e guarda em cache a descoberta das capacidades do Telnet, em vez de enviar `help` a cada segundo. As ações explícitas de experimento, como os testes rápidos e os comandos de handover, continuam separadas da consulta periódica.

## Páginas

Uma página para cada pergunta que o operador de fato faz.

| Página | Rota | Conteúdo |
|---|---|---|
| Overview | `/` | Barra lateral com a saúde dos contêineres, diagrama da topologia (as quatro topologias), mobilidade ao vivo, latência do UE ao vivo, contexto do UE, subida e derrubada, handover rápido, captura da interrupção e configuração das células (recolhível) |
| Results | `/results/runs`, `/results/campaigns` | Explorador de execuções (métricas, traço do ping com marcas do handover, linha do tempo dos eventos e fluxo de mensagens) e campanhas de execuções repetidas, com comparação |
| Controls | `/controls` | Capacidades das ações, garantias de segurança, conferências de execução, token da API, teste rápido, lista de tarefas e últimas linhas da saída |

As sete abas antigas viraram três:

- as páginas da gNB e do UE foram para a visão geral;
- a página de handover se juntou ao explorador de execuções, porque as duas liam os mesmos arquivos `results/runs/*` e mostravam o mesmo traço de RTT.

Os caminhos antigos (`/gnb`, `/ue`, `/handover`, `/runs/:id`, `/campaigns/:id`) redirecionam para os novos. Assim, os favoritos antigos continuam funcionando.

Algumas coisas foram tiradas, e não movidas:

- O painel de estado da RAN, na página da gNB, repetia a barra lateral da visão geral.
- O gráfico "throughput history" (histórico de vazão), na página da gNB, mostrava o `latest_run.iperf_mbps` guardado no buffer de indicadores. Por isso, era uma linha reta, que só mudava quando uma execução terminava. Ele parecia uma série de vazão ao vivo, mas não era.
- Os cartões de CQI, MCS de descida e de subida, BLER de descida e de subida, PHR e DU atual, na página do UE, saíram. Nenhum caminho de telemetria atual os preenche, então eles mostravam "Unavailable" para sempre. O número de UEs e os eventos de registro no AMF, que têm fontes, foram para o cartão de contexto do UE na visão geral.

## Detecção da topologia

O painel descobre a topologia em execução pelos contêineres presentes. Ele usa a mesma ordem de busca do `detect_topology()` em `scripts/lib.sh`:

- `oai-cu` → F1;
- `oai-gnb0` → N2 monolítica;
- `oai-cu0` → N2 CU/DU;
- `oai-gnb` → USRP.

O próprio painel pode subir e derrubar pilhas. Por isso, ele acompanha uma troca de topologia sem reiniciar. Mudam juntos: o conjunto de contêineres acompanhados, o endpoint Telnet de controle e a topologia enviada às ações de handover.

A variável `DASHBOARD_TOPOLOGY` fixa a topologia, em vez de detectá-la:

| Valor | Comportamento |
|---|---|
| não definida ou `auto` (padrão) | detecta pelos contêineres em execução |
| `f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots` | fixa a topologia, sem detectar |

O painel informa como chegou à topologia, em vez de supor. O estado traz o campo `topology_detection`, com:

- `mode`: `auto` ou `pinned` (fixada);
- `detected`: a topologia observada, ou `null`;
- `source`: `container_probe`, `fallback` ou `DASHBOARD_TOPOLOGY`.

Quando nada identificável está rodando, o painel mostra a topologia padrão, com `detected: null` e um aviso. Ele nunca apresenta um palpite como observação.

O endpoint Telnet de controle segue a topologia:

- F1: a CU (`192.168.70.150:9090`);
- N2 monolítica: a gNB de origem (`192.168.70.160:9090`);
- N2 CU/DU: a CU de origem (`192.168.70.150:9090`);
- `usrp-cots`: não tem nó de controle por Telnet, e o painel informa isso.

O teste de latência do UE ao vivo só roda quando a topologia detectada tem um contêiner de UE e esse contêiner está rodando. Antes, ele executava um `docker exec` com falha a cada segundo:

- sempre que o testbed estava fora do ar;
- no `usrp-cots`, em que o UE é um celular comercial externo e não existe contêiner `oai-nr-ue`.

Quando não dá para testar, o `live_latency.probing` fica `false`, com um `skip_reason`. As amostras antigas são descartadas, em vez de ficarem num gráfico que pareceria ao vivo.

## Coleta do estado

Uma única tarefa em segundo plano coleta o estado e publica uma cópia. O WebSocket e os endpoints REST baseados no estado (`/api/topology`, `/api/overview`, `/api/gnb`, `/api/handover`) leem essa cópia, em vez de cada um montá-la de novo. Assim, o custo da coleta não depende de quantos navegadores estão conectados. As chamadas que bloqueiam (SDK do Docker e leitura de arquivos) rodam fora do laço de eventos.

As fontes são agrupadas em níveis de atualização, conforme a rapidez com que mudam de fato:

| Nível | Intervalo padrão | Variável | Fontes |
|---|---|---|---|
| rápido | 1 s | `DASHBOARD_POLL_INTERVAL_SECONDS` | estado dos contêineres, teste de latência ao vivo, Telnet e tarefas de ação |
| médio | 5 s | `DASHBOARD_MEDIUM_INTERVAL_SECONDS` | leituras limitadas dos logs do Docker: eventos recentes de handover, registros no AMF e mobilidade na CU |
| lento | 30 s | `DASHBOARD_SLOW_INTERVAL_SECONDS` | configuração lida, lista de execuções, última execução, gráfico do handover e campanhas |

O nível lento é atualizado antes do tempo quando aparece uma pasta nova em `results/runs`. Assim, um experimento terminado aparece sem esperar o intervalo.

O coletor guarda uma amostra do histórico de indicadores a cada ciclo rápido. Antes, a amostra era guardada a cada nova montagem do estado por um leitor. Isso fazia a densidade da série depender do número de abas abertas no navegador. Agora, o `GET /api/kpi/history` é uma série uniforme, de cerca de 1 Hz, qualquer que seja o número de leitores.

As leituras de detalhe sob demanda (`/api/runs/{id}`, `/api/handover/runs/{id}`, detalhe de campanha e `/api/config`) são servidas diretamente, e não pela cópia. Assim, elas sempre mostram os arquivos atuais.

## Rodar no computador local, para desenvolver com partes fora do ar

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

O frontend pode mostrar só o fundo, com o erro `React is not defined` no console do navegador. Nesse caso:

1. Confira se o `dashboard/frontend/vite.config.js` existe e inclui o `@vitejs/plugin-react`.
2. Recompile o contêiner do frontend sem cache:

   ```bash
   docker compose -f dashboard/docker-compose.dashboard.yml build --no-cache dashboard-frontend
   ```

O painel deve subir mesmo com o testbed da OAI fora do ar. Contêineres faltando, problemas no socket do Docker, Telnet da CU indisponível e configurações faltando aparecem como avisos, e não como erros fatais do backend. A falta de arquivos `results/runs/*/summary.json` históricos é normal e gera `latest_run: null`.

## Endpoints da fase 2

- `GET /api/runs` lista as pastas das execuções, com as métricas do resumo quando existirem.
- `GET /api/runs/{run_id}` retorna o resumo, os resumos opcionais de ping e de iperf, os eventos e uma quantidade limitada de amostras de ping.
- `GET /api/kpi/history` retorna o buffer circular de indicadores em memória.
- `GET /api/ues` retorna a tabela atual de UEs lida, se o Telnet da CU a fornecer.
- `GET /api/gnb` retorna a configuração da CU e das DUs, o estado dos contêineres, o estado do Telnet e o histórico de indicadores.
- `/ws` inclui a topologia atual, os contêineres, o estado do Telnet, a última execução, um histórico curto de indicadores, os avisos e a atualidade de cada fonte.

Os arquivos grandes, como os logs brutos completos, não vão pelo WebSocket, de propósito.

## Endpoints de handover da fase 3

- `GET /api/handover` retorna a prontidão atual para mobilidade (sem garantia), o acesso ao Telnet da CU ou da origem, os eventos recentes tirados de leituras limitadas dos logs e os avisos.
- `GET /api/handover/runs` retorna resumos voltados ao handover de todas as pastas `results/runs/*`.
- `GET /api/handover/runs/{run_id}` retorna, de uma execução, os eventos padronizados, o fluxo de mensagens, as marcas de interrupção no ping, uma quantidade limitada de amostras de ping e os avisos.
- `GET /api/handover/message-flow/{run_id}` retorna só as etapas reconstruídas do fluxo de mensagens.
- `GET /api/handover/durations` retorna as linhas de duração do handover, prontas para tabela.

Valores de confiança dos eventos de handover:

- `observed`: está direto no `events.csv` ou em outro arquivo estruturado.
- `parsed`: foi tirado de um trecho limitado de texto dos logs do Docker ou do Telnet.
- `inferred`: foi calculado a partir das métricas do resumo, como `estimated_interruption_ms` ou `first_ping_after_handover_ms`.

A reconstrução do fluxo de mensagens não tem garantia:

- O `events.csv` é a fonte principal.
- Os `docker_logs/*.log` coletados e os trechos finais dos logs ao vivo do Docker podem acrescentar indicações lidas.
- A leitura dos logs Docker guardados só lê os últimos 512 KiB de cada arquivo e guarda no máximo 30 eventos encontrados por arquivo.
- A leitura dos logs ao vivo do Docker usa trechos finais limitados.
- Os pontos de origem e de destino desconhecidos continuam `Unknown`. Eles não são deduzidos pelos nomes da topologia.

## Controles seguros da fase 4

As ações ficam desligadas, a menos que o backend suba com:

```bash
DASHBOARD_ENABLE_ACTIONS=true
```

Nas ações do painel que sobem pilhas Docker Compose da OAI, o backend controla o Docker do computador por `/var/run/docker.sock`. Quem interpreta os caminhos das montagens é o Docker do computador. Por isso, a `DASHBOARD_REPO_ROOT` deve ser um caminho absoluto que existe no computador, e não só um apelido dentro do contêiner, como `/repo`. Use o arquivo Compose de exemplo para ações, a partir da raiz do repositório:

> **Isso é garantido, e não só documentado.** O Docker não falha quando falta a origem de uma montagem. Ele cria uma pasta vazia sem avisar. Sem o arquivo de exemplo, uma pilha subida pelo painel monta pastas vazias no lugar do `config.yaml` e da base de assinantes. O núcleo 5G nunca sobe, e sobra lixo com dono root no computador.
>
> Por isso, o backend compara a `DASHBOARD_REPO_ROOT` com a origem, no computador, da montagem dele mesmo. Se não forem iguais, ele **recusa a subida, a derrubada, o teste rápido e o teste rápido repetido com HTTP 409** e mostra o comando correto. As ações que só usam Telnet ou ping (comando de handover e captura da interrupção) não são afetadas. O bloqueio exige prova positiva da diferença: se não der para examinar a montagem, ou se o backend não rodar em contêiner, as ações seguem como antes.

```bash
DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml \
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build
```

O arquivo Compose base monta o `/dev/net/tun` no `dashboard-backend`. Só o `network_mode: host` não mostra os dispositivos de `/dev`. O arquivo de exemplo mantém a mesma montagem do TUN e monta o repositório no caminho absoluto do computador, com escrita só em `results/`.

Se o painel já estiver rodando com as ações desligadas, recrie só o backend:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend
```

Ou reinicie o painel inteiro:

```bash
DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

O backend lê a variável quando sobe. Definir a variável no shell com o backend já rodando não liga as ações nesse processo.

Endpoints das ações:

- `GET /api/actions/capabilities` informa se as ações estão ligadas e lista as garantias de segurança.
- `POST /api/actions/trigger-handover` inicia uma tarefa confiável de handover na topologia ativa, se as ações estiverem ligadas e o pedido vier confirmado.
- `POST /api/actions/deploy-topology` sobe uma pilha completa com `scripts/up.sh <topologia>` (`f1`, `n2-monolithic`, `n2-cu-du`, `usrp-cots`), se ligada e confirmada.
- `POST /api/actions/teardown-topology` derruba uma pilha com `scripts/down.sh <topologia>`, se ligada e confirmada.
- `POST /api/actions/smoke-test` inicia uma tarefa confiável de teste rápido para `f1`, `n2-monolithic` ou `n2-cu-du`, se ligada e confirmada.
- `POST /api/actions/repeated-smoke-test` inicia uma campanha confiável de testes rápidos repetidos, se ligada e confirmada.
- `GET /api/actions/jobs` lista as tarefas iniciadas pelo painel, sem as últimas linhas completas da saída.
- `GET /api/actions/jobs/{job_id}` retorna os detalhes da tarefa, com as últimas linhas limitadas do stdout e do stderr.

Garantias de segurança:

- Desligadas por padrão.
- Nenhum comando arbitrário.
- Nenhuma execução em shell. Os subprocessos usam listas fixas de argumentos.
- Só scripts de uma lista permitida: `scripts/trigger_handover.sh`, `scripts/measure_interruption.sh`, `scripts/up.sh`, `scripts/down.sh`, `scripts/run_smoke_test.sh` e `scripts/run_repeated_smoke_tests.sh`. Cada um é chamado com uma lista fixa de argumentos. O único parâmetro livre é o nome da topologia, conferido contra uma lista fechada. Não há controle arbitrário do ciclo de vida dos contêineres: a subida e a derrubada só rodam esses dois scripts, para uma topologia da lista permitida.
- As ações rodam dentro do contêiner do backend do painel.
- A raiz do repositório é a pasta de trabalho dos subprocessos.
- A montagem padrão em `/repo` basta para usar o painel só para leitura. Nas ações que chamam o Docker Compose do computador, use o `dashboard/docker-compose.dashboard.host-actions.example.yml`, para a `DASHBOARD_REPO_ROOT` existir no computador.
- A montagem do repositório continua só para leitura, menos `results/`. Essa pasta é montada com escrita, para os testes rápidos criarem os arquivos `results/runs/*` e o `trigger_handover.sh` acrescentar eventos na `RUN_DIR` de um teste rápido.
- O `/dev/net/tun` é montado no contêiner do backend, para os scripts que precisam do TUN do UE.
- A imagem do backend inclui as ferramentas mínimas de linha de comando e de rede que os scripts confiáveis usam: `bash`, a CLI do Docker com o Compose v2, `nc`, `ip`, `ss`, `ping` e `python3`.
- O socket do Docker montado serve para falar com o Docker do computador. Nenhum Docker roda dentro do contêiner do backend.
- As ações que sobem pilhas Compose são recusadas quando o Docker do computador não vê a raiz do repositório no mesmo caminho. Isso aparece em `runtime_checks.repo_root_host_visible` e como faixa de aviso na página Controls.
- Só uma tarefa iniciada pelo painel roda por vez.
- As últimas linhas do stdout e do stderr ficam limitadas a 200 cada.
- O tempo limite das ações encerra todo o grupo de processos: primeiro com SIGTERM e, depois de um curto prazo, com SIGKILL.
- O estado das tarefas fica só na memória e se perde quando o backend reinicia.

> **ATENÇÃO:** Não exponha o painel em redes não confiáveis com as ações ligadas. O backend comanda o Docker do computador.

## Autenticação e CORS

A autenticação é opcional e vem desligada por padrão (padrão de laboratório). Nada muda se você não a configurar.

- `DASHBOARD_API_TOKEN`: com um valor não vazio, todos os endpoints `/api/actions/*` e o WebSocket `/ws` exigem o token.
  - As chamadas REST devem enviar `Authorization: Bearer <token>`.
  - O WebSocket deve se conectar com `?token=<token>`.
  - Sem a variável, não há autenticação.
  - Pedidos sem token ou com token errado recebem HTTP 401. No WebSocket, o código de fechamento é 1008.
- `DASHBOARD_CORS_ORIGINS`: lista de origens permitidas, separadas por vírgula (por exemplo, `https://ops.example.com,https://lab.internal`). O padrão é `*`, para manter o comportamento anterior do laboratório. Defina uma lista explícita para tudo o que for acessível além do `localhost`. O CORS com credenciais não está ligado: o token vai no cabeçalho `Authorization`, e não num cookie. Além disso, os navegadores já recusam `*` junto com credenciais.

No frontend, informe o token na página **Controls** (cartão "API token"). O navegador o guarda e o envia nos pedidos de ação e no WebSocket ao vivo. Depois de mudar o token, recarregue a página, para o socket se autenticar de novo.

Isso é uma defesa a mais, e não substitui o isolamento da rede. Mesmo assim, não exponha o painel em redes não confiáveis com as ações ligadas, porque o backend comanda o Docker do computador.

Exemplo de subida do backend com autenticação:

```bash
DASHBOARD_API_TOKEN="$(openssl rand -hex 24)" \
DASHBOARD_CORS_ORIGINS="http://localhost:5173" \
DASHBOARD_ENABLE_ACTIONS=true \
  docker compose -f dashboard/docker-compose.dashboard.yml up --build
```

## Campanhas da fase 5

Endpoints das campanhas:

- `GET /api/campaigns` lista as campanhas de execuções repetidas encontradas.
- `GET /api/campaigns/{campaign_id}` retorna uma campanha, com as linhas de cada execução, as estatísticas, os valores fora do padrão e os avisos.
- `GET /api/campaigns/compare` retorna resumos prontos para comparação, agrupados por topologia e por campanha.
- `GET /api/campaigns/export` retorna linhas JSON planas, que o navegador pode converter em CSV. Ele não grava arquivos.

Premissas sobre os arquivos:

- As campanhas ficam em `results/repeated/*`.
- O script de testes rápidos repetidos grava `runs.txt`, `summary.csv`, `summary.json` e os logs de cada execução na pasta de cada campanha.
- As pastas das execuções ligadas, em `results/runs/*`, continuam sendo a fonte oficial das métricas de cada execução, quando o `summary.json` existe.
- Arquivos opcionais faltando ou malformados geram avisos, e não falhas do backend.

Estatísticas:

- As estatísticas numéricas das campanhas são calculadas para a interrupção do handover, o primeiro ping depois do handover, a perda de pacotes, o RTT médio e a vazão do iperf.
- Os valores `null` ou faltando são ignorados nas estatísticas numéricas.
- Se uma métrica não tiver nenhum valor válido, as estatísticas dela ficam `null`.
- As estatísticas mostradas são `min`, `mean` (média), `median` (mediana), `p95` pelo posto mais próximo e `max`.
- Os valores fora do padrão são listas ordenadas simples. Elas mostram as execuções:
  - com falha;
  - sem comando de handover;
  - sem métricas de ping;
  - com a maior interrupção, a maior perda de pacotes ou o maior RTT;
  - com a menor vazão do iperf.

Ação de testes rápidos repetidos:

- Endpoint: `POST /api/actions/repeated-smoke-test`.
- Formato do pedido: `{"confirm": true, "topology": "f1", "count": 5}`.
- Topologias permitidas: `f1`, `n2-monolithic` e `n2-cu-du`.
- O número de execuções vai de 1 a 20.
- O script confiável é chamado com argumentos fixos e com `RUNS=<número>` num ambiente controlado.
- A ação usa as mesmas proteções da fase 4: desligada por padrão, uma tarefa por vez, tempo limite por grupo de processos e últimas linhas da saída limitadas.

## Estado ocioso

Quando não existe nenhum contêiner de CU, DU, gNB ou UE, não há topologia para desenhar. A visão geral mostra um painel explícito "No topology deployed" (nenhuma topologia no ar), com a lista das topologias que podem ser subidas. Antes, ela desenhava a topologia padrão com todos os nós parados. Isso dava a entender que "a pilha F1 está no ar e quebrada" e citava uma pilha que o operador nunca escolheu.

A barra lateral também esconde os nós da RAN da topologia padrão e só mantém os contêineres do núcleo 5G. Eles são compartilhados por todas as topologias e, por isso, são uma observação real. Um núcleo 5G rodando sem RAN é indicado à parte, porque a próxima subida vai reaproveitá-lo.

A existência de uma topologia no ar é julgada pelos contêineres observados, e não pelo nome da topologia detectada. Assim, o resultado também fica correto com a topologia fixada. Se o próprio Docker não responder, a visão normal continua: falta de evidência não é evidência de falta.

O campo `status`, no nível mais alto, mostra isso com um terceiro valor:

| Valor | Significado |
|---|---|
| `ok` | uma topologia está no ar, e os contêineres necessários estão rodando |
| `idle` | não existe nenhum contêiner da RAN: nada está no ar |
| `degraded` | surgiu um aviso, ou uma pilha no ar tem um contêiner necessário parado |

O `topology_detection` separa `warning` de `note`:

- `warning` é um problema real: o Docker não responde, ou o `DASHBOARD_TOPOLOGY` tem um valor desconhecido;
- `note` indica um computador ocioso.

Só o `warning` entra na lista geral de avisos. Assim, uma máquina ociosa não aparece mais como degradada.

## Significado da prontidão para mobilidade

O `handover.readiness` separa o que foi observado do que nunca foi consultado:

| Valor | Significado |
|---|---|
| `ready` | o Telnet foi consultado, e o nó de controle respondeu |
| `degraded` | o Telnet foi consultado e não respondeu |
| `not_observed` | nada consultou o nó de controle: a consulta periódica está desligada (o padrão), ou a topologia não tem endpoint Telnet |
| `unavailable` | um contêiner necessário não está rodando |

O `handover.cu_telnet_status` faz a mesma separação, com os valores `reachable`, `unreachable`, `polling_disabled` e `no_endpoint`. Só o `unreachable` (uma consulta que falhou de verdade) gera aviso.

Antes, o caso desligado por padrão aparecia como "not reachable". Isso afirmava uma falha que nunca foi observada. E, como os avisos definem o campo geral `status`, uma pilha totalmente saudável ficava marcada como `degraded` para sempre.

Pelo mesmo motivo, uma topologia cujos arquivos `.conf` não são lidos recebe uma `note` na configuração, e não um aviso. Um limite de escopo conhecido não é uma anomalia.

## Significado da telemetria do UE

- O `live_kpis.ue_count` só conta o contexto de UE conectado agora. Ele vem do Telnet da CU, ou de outra fonte de estado atual que venha a ser acrescentada.
- Se o Telnet da CU não estiver disponível ou não mostrar um contexto de UE que dê para ler, o `live_kpis.ue_count` fica `null`, e a interface mostra Unavailable.
- Os registros encontrados nos logs recentes do AMF aparecem à parte, em `live_kpis.amf_registration_events_seen`, com a fonte `amf_logs_tail` e a janela `last_500_log_lines`.
- Os eventos de registro no AMF não são um número de UEs conectados agora. Testes repetidos, ciclos de desconexão e reconexão e tentativas com falha podem fazê-los diferir dos UEs conectados.

## Validação

Confira se o registro do painel ainda bate com os arquivos Compose atuais:

```bash
cd dashboard/backend
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_registry.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase2.py
PYTHONPATH=. DASHBOARD_REPO_ROOT=../.. python validate_phase3.py
```

Validação completa, a partir da raiz do repositório:

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

O UE do rfsim usa:

- IMSI `001010000000001`;
- chave `fec86ba6eb707ed08905757b1bb44b8f`;
- OPC `C42449363BBAD02B66D16BC975D77CC1`;
- DNN `oai`;
- slice com SST `1` e SD `FFFFFF`.

O SQL de carga inicial tem os dois formatos de identificação para a autenticação: o numérico, `001010000000001`, e o SUPI canônico, `imsi-001010000000001`.

Valide a carga que está no repositório com:

```bash
python3 scripts/validate_cn_subscriber.py
```

Se o `wait_ue_data_ready.sh` estourar o tempo sem a `oaitun_ue1`, ele agora mostra diagnósticos focados do UE, do AMF, do AUSF, do UDM, do UDR e do MySQL. Se os logs mostrarem `CONTEXT_NOT_FOUND`, ou se o MySQL estiver não saudável, recrie a base do núcleo 5G a partir do SQL atualizado:

```bash
./scripts/down.sh f1 --volumes
./scripts/up.sh f1
```

> **CUIDADO:** O `--volumes` apaga o estado guardado nos volumes do Compose. Só use para reiniciar o laboratório ou o testbed.

## Limitações

- Não há botões de ciclo de vida.
- Não há edição de configuração.
- Não há controles amplos do ciclo de vida dos contêineres.
- A fase 4 só comanda scripts confiáveis com `DASHBOARD_ENABLE_ACTIONS=true`.
- A fase 5 só inicia campanhas de testes rápidos repetidos com `DASHBOARD_ENABLE_ACTIONS=true`.
- Há autenticação opcional por token (`DASHBOARD_API_TOKEN`), desligada por padrão. Mesmo assim, não exponha as ações em redes não confiáveis.
- O handover rápido e a captura da interrupção na visão geral seguem a topologia detectada (`f1`, `n2-monolithic`, `n2-cu-du`), pelas ações da lista permitida. O N2 usa o PCI de destino e o identificador RRC do UE padrão da configuração. Não há tela para escolher a origem e o destino. Repetir o handover N2 no mesmo sentido exige recriar a topologia.
- O diagrama é desenhado para as quatro topologias, a partir do registro de contêineres. Os endereços dos nós vêm do registro, e não da configuração lida. Por isso, eles ficam corretos mesmo onde a leitura dos `.conf` não existe. O leitor detalhado de configuração continua só para o F1. Assim, só os nós do F1 mostram parâmetros de célula, como o PCI. As outras topologias dizem isso, em vez de mostrar uma configuração no formato do F1.
- O destaque da célula atual só aparece quando uma fonte de telemetria de fato a informa. Na prática, isso é o F1, com a leitura dos logs da CU. As topologias N2 mostram "serving cell not observed" (célula atual não observada), em vez de destacar um palpite. O diagrama do USRP marca o celular comercial como fora da pilha acompanhada, porque ele não tem contêiner.
- As comparações de campanhas vêm dos arquivos. Elas não inventam métricas que faltam nem deduzem um estado de campanha indisponível.
- Não há leitura do Telnet das DUs no F1. As DUs atuais do F1 não abrem Telnet.
- Os eventos de handover e as etapas do fluxo de mensagens tirados dos logs não têm garantia e são limitados. Os logs guardados são lidos a partir dos últimos 512 KiB. Os detalhes de protocolo indisponíveis ficam `null`, vazios ou Unavailable.
- Os indicadores de rádio e de MAC ao vivo só aparecem quando a saída do Telnet da OAI em execução os mostra. Nos outros casos, ficam `null` ou Unavailable. Nenhum caminho de telemetria atual preenche CQI, MCS, BLER, PHR ou DU atual. Por isso, esses cartões saíram da interface, em vez de ficarem sempre indisponíveis. Os campos `live_kpis` continuam na API, para uma futura fonte por Telnet ou por xApp.
- Um contexto de UE atual indisponível continua `null`. Os registros tirados dos logs do AMF aparecem à parte, como eventos recentes.
- Os indicadores de rádio do rfsim, como RSRP, RSRQ e SINR, podem ser sintéticos ou indisponíveis.
- A leitura de configuração continua focada no F1. As outras topologias estão no registro só para a descoberta dos contêineres.
