# Pipeline de medição e ciclo de vida das execuções

> Tradução para o português. O original em inglês é o [guide-measurement-pipeline.md](../en/guide-measurement-pipeline.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Guia
>
> **Leitura obrigatória:** [F01 — Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) e [F02 — Alcance do plano de usuário e da DN](foundation-f02-dn-reachability.pt-BR.md)

Este documento descreve como uma única execução de teste rápido é orquestrada de ponta a ponta:
como o plano de dados é medido durante um handover, como as capturas brutas se tornam
métricas e como a execução é controlada por verificações para que produza números
confiáveis ou seja marcada explicitamente como inválida.

Ele é o elo entre duas referências existentes:

- [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) — o que significa
  "pronto" e a qual camada pertence cada verificação.
- [Guia de handover N2](guide-n2-handover.pt-BR.md) — a configuração específica de cada topologia
  e o próprio disparo do handover.

Este documento não repete essas referências; ele trata da medição e do ciclo de vida
que ficam acima delas.

---

## 1. Princípios de projeto

Dois princípios moldam todo o pipeline:

1. **Nunca usar `sleep` e torcer — consultar periodicamente uma condição observável.** A prontidão é
   estabelecida consultando o estado dos contêineres, as portas do plano de controle e o alcance
   real do plano de dados, e não por atrasos fixos. Os únicos `sleep` fixos numa execução
   são as janelas de medição deliberadas (uma breve estabilização antes do disparo e
   a janela de captura após o handover).
2. **Uma medição é confiável ou explicitamente inválida — nunca silenciosamente
   errada.** Cada verificação é registrada como um booleano no `summary.json`, e uma execução só
   é declarada `pass` depois que o parser confirma que foram capturadas amostras utilizáveis.

Os dois princípios existem porque um processo da OAI pode estar vivo enquanto a pilha de
protocolos está inutilizável (veja os invariantes de prontidão no modelo de prontidão
funcional).

---

## 2. Ciclo de vida da execução

O controlador é o `scripts/run_smoke_test.sh`, invocado como
`./scripts/run_smoke_test.sh <topologia>`, em que a topologia é `f1`,
`n2-monolithic` ou `n2-cu-du`. O `apply_topology` seleciona o arquivo Compose, a
configuração do experimento e a lista de contêineres críticos; todo o restante é
independente da topologia.

A sequência ordenada:

1. **`create_run_dir`** — é criado um diretório de resultados com carimbo de tempo,
   `results/runs/<run_id>_<tag>/`, e um `trap finish_summary EXIT`
   é instalado imediatamente, para que *todo* caminho de saída grave um `summary.json`.
2. **Preflight** (`preflight_check.sh`) — pré-requisitos do host.
3. **Inicialização** — o `status.sh` é verificado; se a topologia ainda não estiver pronta, o `up.sh`
   a inicia.
4. **`wait_ready.sh`** — consulta o `status.sh` até que todas as verificações críticas passem
   (180 s por padrão).
5. **`poststart_check.sh`** — diagnósticos não bloqueantes e varredura de logs fatais.
6. **`wait_ue_data_ready.sh`** — a verificação decisiva: repete
   `docker exec oai-nr-ue ping -c1 -W1 <destino>` até que o UE consiga de fato passar tráfego
   de usuário pela `oaitun_ue1`. O contêiner estar vivo não basta; isso
   confirma que a sessão PDU encaminha tráfego. Uma falha aqui aborta a execução antes de qualquer
   handover.
7. **Iniciar a captura de ping** (`start_ping_capture.sh`).
8. **Opcionalmente, iniciar o iperf** em segundo plano (`run_iperf_test.sh`).
9. **Estabilização** — `sleep 3` para coletar respostas de referência.
10. **Disparar o handover** (`trigger_handover.sh`), delimitado pelos
    eventos `before_handover` e `after_handover`.
11. **Janela de recuperação** — continuar pingando por `PING_POST_HANDOVER_SECONDS` (10 s
    por padrão) para capturar a recuperação após o disparo.
12. **Parar a captura**, aguardar (`wait`) o iperf e, em seguida, **processar** as duas capturas.
13. **Validar** a saída do parser, **coletar os logs** e finalizar o `summary.json`.

Como o trap de `EXIT` sempre executa o `finish_summary`, uma execução que falha
no meio do caminho ainda deixa um registro estruturado mostrando até onde avançou
(`ue_data_ready`, `ping_precheck_passed`, `handover_triggered` e assim por diante são
registrados, cada um, como booleanos).

---

## 3. Captura de ping

O `scripts/start_ping_capture.sh` executa em segundo plano um ping com carimbo de tempo (`ping -D`) dentro
do contêiner `oai-nr-ue` e grava em `ping_raw.log`.

### Separação entre os arquivos da pré-verificação e da captura

Primeiro roda uma pré-verificação de 2 pacotes para confirmar o alcance antes de iniciar a
captura longa. A pré-verificação grava num arquivo **separado**
(`ping_precheck_raw.log`), nunca no `ping_raw.log`.

Essa separação é essencial. Quando a pré-verificação e a captura longa compartilhavam o
`ping_raw.log`, uma condição de corrida na gravação da linha final de estatísticas da captura longa
podia fazer o parser ler o `packets transmitted, 2` da pré-verificação em vez
da contagem real da captura — informando `packets_transmitted: 2` para uma execução que
na verdade capturou dezenas de respostas. Manter o `ping_raw.log` exclusivo da captura longa
torna inequívoca a linha final de estatísticas.

As linhas de comentário do cabeçalho (destino, interface, intervalo, contêiner de origem) são o
único conteúdo gravado no `ping_raw.log` antes de a captura longa começar.

Arquivos produzidos no diretório da execução:

- `ping_raw.log` — somente a captura longa (cabeçalho + saída do `ping -D`).
- `ping_precheck_raw.log` — a saída da pré-verificação de 2 pacotes.
- `ping_command.txt` — o comando exato da captura longa.
- `ping.pid`, `ping_target.txt`, `ping_interface.txt`,
  `ping_precheck_status.txt`.

---

## 4. Processamento do ping e estimativa da interrupção

O `tools/parse_ping.py` transforma o `ping_raw.log` em `ping.csv`, mais um
`ping_summary.json` com as métricas.

### Extração das respostas e do resumo

Três expressões regulares reconhecem as linhas de resposta (`[ts] N bytes from … icmp_seq=… time=… ms`),
a linha final `packets transmitted, … received, …% packet loss` e a
linha `rtt min/avg/max/mdev`. Um indicador `long_capture_started` garante que as linhas de resumo
e de rtt só sejam aceitas *depois* da primeira resposta real — uma segunda camada de
defesa contra a contaminação pela pré-verificação, além da separação de arquivos descrita acima.

O `packet_loss_percent` é derivado das contagens de pacotes transmitidos e recebidos; as estatísticas
de rtt são tiradas da linha final, se presente, ou calculadas a partir
das respostas processadas.

### Estimativa da interrupção do handover

Esta é a métrica principal. O parser cruza os carimbos de tempo das respostas de ping com o
`events.csv`:

- Localiza o instante do handover pelo evento `handover_trigger_start`
  (alternativa: `before_handover`).
- As respostas são divididas entre as **anteriores** e as **simultâneas ou posteriores** ao instante do handover.
- `estimated_interruption_ms = (primeira resposta depois) − (última resposta antes)`,
  em milissegundos.
- `first_ping_after_handover_ms = (primeira resposta depois) − (instante do handover)`.

> **Dependência do nome do evento.** A estimativa da interrupção depende de o
> evento `handover_trigger_start` estar presente no `events.csv`. O
> `trigger_handover.sh` unificado emite esse mesmo nome de evento para todas as topologias (F1 e
> as duas variantes N2). Se uma mudança futura o renomear para um evento específico de topologia,
> a estimativa da interrupção passará silenciosamente a `null`. Mantenha o nome do evento estável.

### Resolução e interpretação

A estimativa é limitada pelo intervalo do ping (0,2 s por padrão); portanto, é uma
**referência funcional, e não uma medição precisa da interrupção**. O conjunto de resultados
validados a trata dessa forma: uma única execução por topologia é uma verificação de sanidade,
e não uma referência estatisticamente significativa. Um estudo comparativo real exige tentativas
repetidas a partir de partida a frio, carga do host fixa, digests de imagem fixados e intervalos
de confiança.

### Verificação de validade

O `ping_metrics_valid` é definido como `parsed_reply_count > 0`. Após o processamento, o
controlador verifica novamente `ping_metrics_valid` e `packets_transmitted != 0`; se
qualquer um falhar, a execução é marcada como falha com um evento `ping_metrics_invalid`, mesmo
que o comando de handover tenha sido enviado. Métricas inválidas nunca se passam por aprovação.

### Captura da interrupção em alta resolução (`measure_interruption.sh`)

O intervalo padrão de 0,2 s do ping no teste rápido é grosseiro demais para resolver uma
interrupção do plano de usuário de dezenas de milissegundos: a estimativa tem como piso o intervalo,
de modo que um handover sem interrupção e uma interrupção de 150 ms podem ambos informar aproximadamente um intervalo.
O `scripts/measure_interruption.sh` existe para medir essa interrupção diretamente.

Trata-se de uma **captura limitada, em alta taxa, em torno de um único handover disparado**, que
reutiliza o mesmo pipeline do `parse_ping.py`. Diferentemente do teste rápido, ele **não**
sobe a pilha nem executa o iperf — pressupõe que a topologia já esteja ativa (a
mesma pré-condição do disparo rápido do painel). O fluxo:

1. `wait_ue_data_ready.sh` — a mesma verificação decisiva do plano de dados.
2. `start_ping_capture.sh` com `INTERRUPTION_PING_INTERVAL` (padrão **0,01 s = 10 ms**).
3. `sleep INTERRUPTION_PRE_SECONDS` (padrão 2 s) de referência.
4. `trigger_handover.sh <topologia>` — emite o mesmo evento `handover_trigger_start`
   em que o parser se ancora.
5. `sleep INTERRUPTION_POST_SECONDS` (padrão 4 s) de recuperação.
6. `stop_ping_capture` + `parse_ping.py`; em seguida, imprime o marcador `INTERRUPTION_RUN_DIR=`
   para que o painel consiga localizar a execução.

| Variável de ambiente | Padrão | Significado |
|---|---|---|
| `INTERRUPTION_PING_INTERVAL` | `0.01` | segundos entre sondas (10 ms) |
| `INTERRUPTION_PRE_SECONDS` | `2` | captura de referência antes do disparo |
| `INTERRUPTION_POST_SECONDS` | `4` | captura após o disparo |
| `UE_DATA_READY_TIMEOUT` | `60` | tempo limite de prontidão do plano de dados |
| `PING_TARGET` / `PING_INTERFACE` | da configuração | substituem os valores do experimento |

Intervalos abaixo de 200 ms exigem que o ping rode como root, o que o contêiner `oai-nr-ue`
já faz. O script aceita `f1`, `n2-monolithic` ou `n2-cu-du`.

#### Interpretação do resultado — sem interrupção vs. interrupção real

A estimativa continua tendo como piso o intervalo das sondas; assim, uma cadência de 10 ms resolve
interrupções de até cerca de 10 ms, não menos que isso. Leia o resultado junto com a perda de pacotes:

- **Estimativa ≈ um intervalo de sonda, 0% de perda, nenhum `icmp_seq` faltando** → o
  handover foi **sem interrupção**: nenhum pacote do plano de usuário foi de fato perdido, e a
  "interrupção" de poucos milissegundos informada é apenas o intervalo entre duas sondas
  bem-sucedidas adjacentes, e não uma interrupção. Não a cite como tempo de interrupção.
- **Valores de `icmp_seq` faltando (perda de pacotes > 0)** → este é o **sinal honesto de
  interrupção**. A extensão dos números de sequência faltantes, e não a diferença de tempo
  entre respostas, é o que caracteriza uma interrupção real.

Em outras palavras: a estimativa pelo intervalo de RTT é um número conveniente, mas **a perda de pacotes /
os números de sequência faltantes são a verdade de referência sobre se o tráfego foi de fato
interrompido**. O cartão de interrupção da Visão geral do painel reflete isso — ele plota
o fluxo de respostas por `icmp_seq` (interrompendo a linha nas sequências faltantes) e
rotula um resultado com 0% de perda e estimativa dentro de cerca de dois intervalos de sonda como
handover sem interrupção, e não como uma interrupção medida.

---

## 5. Medição opcional com iperf

Quando `IPERF_ENABLED=1` (ou `IPERF_REQUIRED=1`), o `run_iperf_test.sh` roda
simultaneamente com a captura de ping durante o handover. Ele se vincula ao endereço PDU
do UE com `iperf3 -B <ue_ip>` (o iperf3 da imagem da OAI não suporta
`--bind-dev`), de modo que o tráfego passa pela `oaitun_ue1`, e não pela `eth0`
Docker do contêiner.

O `tools/parse_iperf.py` lê o JSON do iperf3 e se ramifica conforme o protocolo:

- **UDP** → vazão (`mbps`), `jitter_ms`, `lost_packets`, `lost_percent`
  a partir de `end.sum`.
- **TCP** → vazão a partir de `sum_received` e `retransmits` a partir de `sum_sent`.

Por padrão, as falhas do iperf **não são fatais**: um resultado válido de ping/handover não é
invalidado por um problema no iperf, e a falha é registrada em
`iperf_status` / `iperf_error`. Defina `IPERF_REQUIRED=1` para que uma medição de iperf com falha ou
ausente faça a execução inteira falhar.

---

## 6. O resumo da execução

O `summary.json` é o único registro estruturado por execução. Ele é montado com
pequenos auxiliares `python3` embutidos (`json_metric`, `json_shell_string_or_null`) que
convertem em nulo qualquer submétrica ausente, de modo que o esquema é estável independentemente de quais
medições de fato rodaram. Ele registra:

- **Identidade e verificações**: `run_id`, `topology`, horário de início/fim, `status`,
  `containers_checked` e as verificações booleanas (`ue_data_ready`,
  `ping_capture_started`, `ping_precheck_passed`, `ping_parsed`,
  `ping_metrics_valid`, `handover_triggered`).
- **Métricas de ping**: contagens de transmitidos/recebidos, perda, rtt mín./méd./máx.,
  `estimated_interruption_ms`, `first_ping_after_handover_ms`.
- **Métricas de iperf**: status, protocolo, vazão, jitter, perda, retransmissões.
- **`notes`**: um relato legível de como a execução terminou.

Junto dele, o diretório da execução contém `ping_summary.json`, `iperf_summary.json`,
`ping.csv`, `events.csv` (a linha do tempo que alimenta a estimativa da interrupção)
e os logs e o estado do Docker coletados.

O `run_repeated_smoke_tests.sh` invoca esse ciclo de vida N vezes e agrega os
resumos de cada execução em `results/repeated/`.

---

## 7. Onde procurar quando uma métrica está ausente ou errada

| Sintoma | Causa provável | Onde verificar |
|---|---|---|
| `estimated_interruption_ms: null` | Não há evento `handover_trigger_start` ou não há respostas após o disparo | `events.csv`; confirme que o disparo teve sucesso |
| `packets_transmitted` implausivelmente pequeno | Pré-verificação contaminando o `ping_raw.log` (não deve ocorrer após a correção) | `ping_raw.log` vs. `ping_precheck_raw.log` |
| `ping_metrics_valid: false` | Zero respostas processadas | Prontidão do plano de dados do UE; `ping_raw.log` |
| Execução falhou antes do disparo | O plano de dados do UE nunca ficou alcançável | Eventos `ue_data_ready_*`; modelo de prontidão funcional |
| `iperf_status: failed` (a execução ainda passou) | Problema no iperf não obrigatório | `iperf_runner.log`, `iperf_error.txt` |
| `iperf_status: failed` (a execução falhou) | `IPERF_REQUIRED=1` e o iperf falhou | igual ao anterior |
