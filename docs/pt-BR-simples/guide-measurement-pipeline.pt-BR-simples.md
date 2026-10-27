# Pipeline de medição e ciclo de vida de uma execução

> Tradução para o português em Linguagem Simples. O original em inglês é o [guide-measurement-pipeline.md](../en/guide-measurement-pipeline.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** guia
>
> **Leitura prévia:** [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md) e [F02 — Plano de usuário e acesso à rede de dados](foundation-f02-dn-reachability.pt-BR-simples.md)

Este documento descreve uma execução do teste rápido (*smoke test*) do começo ao fim. Ele explica:

- como o testbed mede o plano de usuário durante um handover;
- como as capturas brutas viram métricas;
- como o testbed garante que a execução dá números confiáveis ou é marcada como inválida.

Ele liga duas referências que já existem:

- [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md): o que "pronto" quer dizer e a camada de cada verificação.
- [Guia do handover N2](guide-n2-handover.pt-BR-simples.md): a configuração de cada topologia e o próprio comando de handover.

Este documento não repete essas referências. Ele cobre a medição e o ciclo de vida que ficam em cima delas.

---

## 1. Princípios do projeto

Dois princípios guiam todo o pipeline:

1. **Nunca use `sleep` e torça para dar certo. Espere por uma condição que dá para observar.** O testbed confirma a prontidão consultando o estado dos contêineres, as portas do plano de controle e o acesso real pelo plano de usuário. Ele não usa esperas fixas. As únicas esperas fixas são as janelas de medição planejadas: uma pausa curta antes do comando e a janela de captura depois do handover.
2. **Uma medição é confiável ou é marcada como inválida. Ela nunca fica errada sem aviso.** O `summary.json` registra cada etapa como verdadeiro ou falso. Uma execução só recebe `pass` depois que o analisador confirma que capturou amostras úteis.

Esses princípios existem porque um processo da OAI pode estar rodando com a pilha de protocolos inutilizável. Veja as regras de prontidão no modelo de prontidão funcional.

---

## 2. Ciclo de vida de uma execução

O script principal é o `scripts/run_smoke_test.sh`. Use-o assim: `./scripts/run_smoke_test.sh <topologia>`. A topologia é `f1`, `n2-monolithic` ou `n2-cu-du`. A função `apply_topology` escolhe o arquivo Compose, a configuração do experimento e a lista de contêineres críticos. O resto do processo é igual para todas as topologias.

A ordem das etapas é esta:

1. **`create_run_dir`:** cria a pasta de resultados `results/runs/<run_id>_<tag>/`, com data e hora no nome. Logo em seguida, instala `trap finish_summary EXIT`. Assim, *qualquer* saída do script grava um `summary.json`.
2. **Verificação prévia** (`preflight_check.sh`): confere os pré-requisitos do computador.
3. **Subida:** confere o `status.sh`. Se o testbed ainda não estiver pronto, o `up.sh` sobe a topologia.
4. **`wait_ready.sh`:** consulta o `status.sh` até todas as verificações críticas passarem. O limite padrão é de 180 s.
5. **`poststart_check.sh`:** faz diagnósticos que não bloqueiam e procura erros fatais nos logs.
6. **`wait_ue_data_ready.sh`:** é a etapa decisiva. Ela repete `docker exec oai-nr-ue ping -c1 -W1 <destino>` até o UE passar tráfego de verdade pela `oaitun_ue1`. O contêiner estar vivo não basta. Essa etapa confirma que a sessão PDU encaminha os pacotes. Se ela falhar, a execução para antes de qualquer handover.
7. **Inicia a captura de ping** (`start_ping_capture.sh`).
8. **Inicia o iperf em segundo plano, se estiver ligado** (`run_iperf_test.sh`).
9. **Pausa:** `sleep 3`, para coletar respostas antes do handover.
10. **Comanda o handover** (`trigger_handover.sh`). Os eventos `before_handover` e `after_handover` marcam o início e o fim do comando.
11. **Janela de recuperação:** continua o ping por `PING_POST_HANDOVER_SECONDS` (10 s por padrão), para registrar a recuperação depois do comando.
12. **Para a captura**, espera o iperf terminar (`wait`) e **analisa** as duas capturas.
13. **Valida** o resultado da análise, **coleta os logs** e fecha o `summary.json`.

A armadilha (`trap`) de `EXIT` sempre executa `finish_summary`. Por isso, uma execução que cai no meio do caminho ainda deixa um registro estruturado. Ele mostra até onde a execução chegou. Cada etapa tem um campo verdadeiro ou falso, como `ue_data_ready`, `ping_precheck_passed` e `handover_triggered`.

---

## 3. Captura do ping

O `scripts/start_ping_capture.sh` roda um ping com horário em cada linha (`ping -D`) dentro do contêiner `oai-nr-ue`, em segundo plano. A saída vai para `ping_raw.log`.

### Arquivos separados para o teste inicial e a captura

Primeiro, um teste com 2 pacotes confirma o acesso antes da captura longa. Esse teste inicial grava em um arquivo **separado**, `ping_precheck_raw.log`. Ele nunca grava em `ping_raw.log`.

Essa separação é essencial. Quando os dois usavam o mesmo `ping_raw.log`, havia uma disputa na gravação da última linha de estatística da captura longa. Por causa dela, o analisador às vezes lia `packets transmitted, 2`, do teste inicial, e não o total real. A execução mostrava `packets_transmitted: 2`, mesmo tendo capturado dezenas de respostas. Com o `ping_raw.log` só para a captura longa, a última linha de estatística não deixa dúvida.

Antes da captura longa, o `ping_raw.log` só recebe as linhas de comentário do cabeçalho: destino, interface, intervalo e contêiner de origem.

Arquivos que ficam na pasta da execução:

- `ping_raw.log`: só a captura longa (cabeçalho e saída do `ping -D`);
- `ping_precheck_raw.log`: a saída do teste inicial com 2 pacotes;
- `ping_command.txt`: o comando exato da captura longa;
- `ping.pid`, `ping_target.txt`, `ping_interface.txt` e `ping_precheck_status.txt`.

---

## 4. Análise do ping e estimativa da interrupção

O `tools/parse_ping.py` transforma o `ping_raw.log` em `ping.csv` e em um `ping_summary.json` com as métricas.

### Leitura das respostas e do resumo

Três expressões regulares leem:

- as linhas de resposta (`[ts] N bytes from … icmp_seq=… time=… ms`);
- a linha final `packets transmitted, … received, …% packet loss`;
- a linha `rtt min/avg/max/mdev`.

Um indicador `long_capture_started` só aceita as linhas de resumo e de RTT *depois* da primeira resposta real. É uma segunda proteção contra a mistura com o teste inicial, além da separação de arquivos descrita acima.

O `packet_loss_percent` vem da comparação entre pacotes enviados e recebidos. As estatísticas de RTT vêm da linha final, se ela existir. Se não existir, o analisador as calcula com as respostas lidas.

### Estimativa da interrupção do handover

Esta é a métrica principal. O analisador cruza os horários das respostas de ping com o `events.csv`:

- Ele encontra o horário do handover pelo evento `handover_trigger_start`. Se esse evento faltar, ele usa `before_handover`.
- Ele separa as respostas em dois grupos: **antes** e **no momento ou depois** do handover.
- `estimated_interruption_ms` = (primeira resposta depois) − (última resposta antes), em milissegundos.
- `first_ping_after_handover_ms` = (primeira resposta depois) − (horário do handover).

> **Dependência do nome do evento:** a estimativa depende do evento `handover_trigger_start` no `events.csv`. O `trigger_handover.sh` usa o mesmo nome de evento em todas as topologias (F1 e as duas variantes do N2). Se uma mudança futura trocar esse nome por um nome próprio de cada topologia, a estimativa vira `null` sem aviso. Não mude o nome do evento.

### Resolução e interpretação

O intervalo entre pings limita a estimativa. O padrão é de 0,2 s. Por isso, ela é uma **referência de funcionamento, e não uma medida precisa da interrupção**. O conjunto de resultados validados a trata assim: uma execução por topologia serve para conferir o funcionamento, e não como resultado de referência com valor estatístico. Um estudo comparativo de verdade precisa de:

- várias execuções com partida a frio;
- carga fixa no computador;
- imagens fixadas pelo identificador (*digest*);
- intervalos de confiança.

### Validação das métricas

O campo `ping_metrics_valid` só é verdadeiro quando `parsed_reply_count > 0`. Depois da análise, o script confere de novo `ping_metrics_valid` e `packets_transmitted != 0`. Se um dos dois falhar, a execução é marcada como falha, com o evento `ping_metrics_invalid`. Isso vale mesmo que o comando de handover tenha sido enviado. Métricas inválidas nunca aparecem como aprovação.

### Captura de alta resolução da interrupção (`measure_interruption.sh`)

O ping padrão do teste rápido, a cada 0,2 s, é grosso demais para medir uma interrupção de dezenas de milissegundos. A estimativa nunca fica abaixo do intervalo entre pings. Assim, um handover sem interrupção e uma interrupção de 150 ms podem mostrar o mesmo valor, de cerca de um intervalo. O `scripts/measure_interruption.sh` existe para medir essa interrupção diretamente.

Ele faz uma **captura curta, com ping frequente, em torno de um único handover**. Ele usa o mesmo `parse_ping.py`. Ao contrário do teste rápido, ele **não** sobe a pilha nem roda o iperf. Ele supõe que a topologia já está ativa. O comando rápido do painel web tem a mesma condição.

As etapas são estas:

1. `wait_ue_data_ready.sh`: a mesma etapa decisiva do plano de usuário.
2. `start_ping_capture.sh` com o intervalo `INTERRUPTION_PING_INTERVAL` (padrão de **0,01 s, ou 10 ms**).
3. `sleep INTERRUPTION_PRE_SECONDS`: captura antes do comando (2 s por padrão).
4. `trigger_handover.sh <topologia>`: grava o mesmo evento `handover_trigger_start` que o analisador usa como referência.
5. `sleep INTERRUPTION_POST_SECONDS`: captura da recuperação (4 s por padrão).
6. `stop_ping_capture` e `parse_ping.py`. No final, o script mostra a linha `INTERRUPTION_RUN_DIR=`, para o painel web encontrar a execução.

| Variável | Padrão | O que faz |
|---|---|---|
| `INTERRUPTION_PING_INTERVAL` | `0.01` | segundos entre pings (10 ms) |
| `INTERRUPTION_PRE_SECONDS` | `2` | captura antes do comando |
| `INTERRUPTION_POST_SECONDS` | `4` | captura depois do comando |
| `UE_DATA_READY_TIMEOUT` | `60` | limite de espera pelo plano de usuário |
| `PING_TARGET` / `PING_INTERFACE` | da configuração | trocam os valores do experimento |

Intervalos menores que 200 ms exigem que o ping rode como root. O contêiner `oai-nr-ue` já roda assim. O script aceita `f1`, `n2-monolithic` ou `n2-cu-du`.

#### Como interpretar o resultado: sem interrupção ou interrupção real

O intervalo entre pings ainda limita a estimativa. Com ping a cada 10 ms, ela mede interrupções a partir de cerca de 10 ms, e não menos. Leia o resultado junto com a perda de pacotes:

- **Estimativa perto de um intervalo, 0% de perda e nenhum `icmp_seq` faltando:** o handover foi **sem interrupção**. Nenhum pacote do plano de usuário se perdeu. A "interrupção" de poucos milissegundos é só o intervalo entre dois pings seguidos que deram certo. Não a cite como tempo de interrupção.
- **Valores de `icmp_seq` faltando (perda maior que zero):** este é o **sinal confiável de interrupção**. A faixa de números de sequência que faltam mostra uma interrupção real, e não a diferença de tempo entre duas respostas.

Em resumo: a estimativa pelo intervalo entre respostas é um número prático. Mas **a perda de pacotes e os números de sequência faltando são a prova de que o tráfego foi interrompido**. O cartão de interrupção da visão geral do painel web segue essa regra. Ele mostra as respostas por `icmp_seq` e interrompe a linha onde faltam sequências. Ele chama de handover sem interrupção um resultado com 0% de perda e estimativa de até cerca de dois intervalos.

---

## 5. Medição opcional com iperf

Com `IPERF_ENABLED=1` (ou `IPERF_REQUIRED=1`), o `run_iperf_test.sh` roda junto com a captura de ping durante o handover. Ele usa o endereço da sessão PDU do UE como origem, com `iperf3 -B <ip_do_ue>`. O iperf3 da imagem da OAI não aceita `--bind-dev`. Assim, o tráfego passa pela `oaitun_ue1`, e não pela `eth0` Docker do contêiner.

O `tools/parse_iperf.py` lê o JSON do iperf3. O resultado depende do protocolo:

- **UDP:** vazão (`mbps`), `jitter_ms`, `lost_packets` e `lost_percent`, tirados de `end.sum`;
- **TCP:** vazão tirada de `sum_received` e retransmissões (`retransmits`) tiradas de `sum_sent`.

Por padrão, uma falha do iperf **não derruba** a execução. Um problema no iperf não anula um resultado válido de ping e de handover. O testbed registra a falha em `iperf_status` e `iperf_error`. Para que uma falha ou falta da medição do iperf derrube a execução inteira, use `IPERF_REQUIRED=1`.

---

## 6. Resumo da execução

O `summary.json` é o único registro estruturado de cada execução. Pequenas funções em `python3` (`json_metric` e `json_shell_string_or_null`) montam o arquivo. Elas preenchem com `null` qualquer métrica que falte. Assim, o formato do arquivo não muda, quaisquer que sejam as medições feitas. O arquivo registra:

- **Identificação e etapas:** `run_id`, `topology`, horário de início e de fim, `status`, `containers_checked` e as etapas verdadeiro/falso (`ue_data_ready`, `ping_capture_started`, `ping_precheck_passed`, `ping_parsed`, `ping_metrics_valid` e `handover_triggered`).
- **Métricas de ping:** pacotes enviados e recebidos, perda, RTT mínimo, médio e máximo, `estimated_interruption_ms` e `first_ping_after_handover_ms`.
- **Métricas de iperf:** estado, protocolo, vazão, jitter, perda e retransmissões.
- **`notes`:** um texto para pessoas sobre como a execução terminou.

A pasta da execução também guarda:

- `ping_summary.json` e `iperf_summary.json`;
- `ping.csv`;
- `events.csv`, a linha do tempo que a estimativa da interrupção usa;
- os logs coletados e o estado do Docker.

O `run_repeated_smoke_tests.sh` executa esse ciclo N vezes. Ele junta os resumos das execuções em `results/repeated/`.

---

## 7. Onde procurar quando uma métrica falta ou está errada

| Sintoma | Causa provável | Onde conferir |
|---|---|---|
| `estimated_interruption_ms: null` | Falta o evento `handover_trigger_start`, ou não houve resposta depois do comando. | `events.csv`. Confirme que o comando deu certo. |
| `packets_transmitted` pequeno demais | O teste inicial se misturou ao `ping_raw.log`. Isso não deve acontecer depois da correção. | Compare `ping_raw.log` com `ping_precheck_raw.log`. |
| `ping_metrics_valid: false` | Nenhuma resposta foi lida. | Prontidão do plano de usuário do UE e `ping_raw.log` |
| A execução falhou antes do comando. | O plano de usuário do UE nunca respondeu. | Eventos `ue_data_ready_*` e o modelo de prontidão funcional |
| `iperf_status: failed`, mas a execução passou | Problema no iperf, que não era obrigatório | `iperf_runner.log` e `iperf_error.txt` |
| `iperf_status: failed`, e a execução falhou | `IPERF_REQUIRED=1`, e o iperf falhou. | Os mesmos arquivos acima |
