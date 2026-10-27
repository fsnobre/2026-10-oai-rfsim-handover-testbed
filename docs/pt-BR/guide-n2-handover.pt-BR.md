# Testbed de handover N2 — Guia do usuário

> Tradução para o português. O original em inglês é o [guide-n2-handover.md](../en/guide-n2-handover.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Guia
>
> **Leitura obrigatória:** [F00](foundation-f00-docker-network-ownership.pt-BR.md), [F01](foundation-f01-functional-readiness-model.pt-BR.md), [F02](foundation-f02-dn-reachability.pt-BR.md), [F03](foundation-f03-rfsim-multicell-operations.pt-BR.md) e [F04](foundation-f04-oai-config-enums-and-timing.pt-BR.md)

Este guia cobre tudo o que é necessário para executar experimentos de handover N2 inter-gNB no testbed com o RFsimulator da OAI. O handover N2 exige a OAI v2.4.0 ou posterior.

---

## Sumário

1. [Handover N2 e F1 — principais diferenças](#1-handover-n2-e-f1--principais-diferenças)
2. [Visão geral das topologias](#2-visão-geral-das-topologias)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Referência de configuração](#4-referência-de-configuração)
5. [Iniciar o 5GC](#5-iniciar-o-testbed)
6. [Topologia A — duas gNBs monolíticas](#6-topologia-a--duas-gnbs-monolíticas)
7. [Topologia B — dois pares CU+DU](#7-topologia-b--dois-pares-cudu)
8. [Disparar o handover N2 manualmente](#8-disparar-o-handover-n2-manualmente)
9. [Teste rápido automatizado](#9-teste-rápido-automatizado)
10. [Experimentos repetidos](#10-experimentos-repetidos)
11. [Leitura dos resultados](#11-leitura-dos-resultados)
12. [Parar a pilha](#12-parar-a-pilha)
13. [Solução de problemas](#13-solução-de-problemas)

---

## 1. Handover N2 e F1 — principais diferenças

| | Handover F1 | Handover N2 |
|---|---|---|
| Escopo | Intra-gNB (uma CU, duas DUs) | Inter-gNB (duas gNBs independentes) |
| Mediador | A CU move o UE entre suas próprias DUs | O AMF intermedeia a transferência entre gNBs |
| Interface usada | F1-C | N2 (NGAP) |
| Disparo | `ci trigger_f1_ho` no Telnet da CU | `ci trigger_n2_ho <pci>,<rrc_id>` no Telnet da gNB de origem |
| Versão mínima da OAI | v2.3.0 | v2.4.0 |
| Relatórios de medição | Não necessários (disparo manual) | Não necessários (disparo manual) |

Nos dois casos, o UE atua como **servidor rfsim**, para que várias gNBs possam se conectar à mesma instância do UE.

---

## 2. Visão geral das topologias

### Topologia A — duas gNBs monolíticas

```
                     AMF (192.168.70.132)
                    /                    \
           N2 (NGAP)                      N2 (NGAP)
                  /                          \
    oai-gnb0 (192.168.70.160)          oai-gnb1 (192.168.70.161)
    PCI=0  gNB_ID=0xe00            PCI=1  gNB_ID=0xe01
    Telnet :9090                   Telnet :9090
                  \                          /
                   rfsim client    rfsim client
                          \        /
                      oai-nr-ue (192.168.70.181)
                      rfsim server :4043
```

O handover é disparado pelo **Telnet da oai-gnb0**, tendo como destino a oai-gnb1 (PCI=1).

### Topologia B — dois pares CU+DU

```
                     AMF (192.168.70.132)
                    /                    \
           N2 (NGAP)                      N2 (NGAP)
                  /                          \
    oai-cu0 (192.168.70.150)           oai-cu1 (192.168.70.155)
    Telnet :9090                   gNB_ID=0xe01
    gNB_ID=0xe00                          |
           |                           F1-C/F1-U
        F1-C/F1-U                         |
           |                       oai-du1 (192.168.70.172)
    oai-du0 (192.168.70.171)           rfsim client
    rfsim client                          |
           \                             /
            -------- oai-nr-ue (192.168.70.181) --------
                     rfsim server :4043
```

O handover é disparado pelo **Telnet da oai-cu0**, tendo como destino a célula servida pela oai-cu1/oai-du1 (PCI=1).

---

## 3. Pré-requisitos

- Docker e Docker Compose v2 instalados. A pilha Compose do CN da OAI cria
  e é dona das redes `oai-cn5g-public-net` e `oai-ext-dn-traffic-net`; não as crie
  manualmente. Veja [Propriedade das redes Docker](foundation-f00-docker-network-ownership.pt-BR.md).
- `nc` (netcat) instalado no host (usado para enviar comandos Telnet)
- `python3` instalado no host (usado pelo parser de ping e pela agregação de resultados)
- Imagens da OAI baixadas:
  ```bash
  docker pull oaisoftwarealliance/oai-gnb:v2.4.0
  docker pull oaisoftwarealliance/oai-nr-ue:v2.4.0
  ```
- Imagens do 5GC já presentes (baixadas com `docker compose pull` em `oai-cn5g/`)

> **Aviso sobre o Tailscale:** se o Tailscale estiver ativo, o comando `nc` usado para disparar o handover pode falhar. Execute `sudo tailscale down` antes de disparar ou use o script, que avisa automaticamente.

---

## 4. Referência de configuração

Todos os padrões do experimento N2 ficam em `experiments/n2_handover/config.yaml`. Edite esse arquivo para alterar destinos de ping, parâmetros de handover ou padrões de topologia.

### Parâmetros principais

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `source_gnb_ip` | `192.168.70.160` | IP do Telnet da gNB de origem (oai-gnb0 / oai-cu0) |
| `source_gnb_port` | `9090` | Porta do Telnet |
| `target_pci` | `1` | PCI da célula da gNB de destino |
| `ue_rrc_id` | `1` | ID RRC do UE na gNB de origem |
| `ping.target` | `192.168.71.135` | Destino do ping (oai-ext-dn local) |
| `ping.interface` | `oaitun_ue1` | Interface da sessão PDU do UE |
| `ping.interval_seconds` | `0.2` | Intervalo do ping durante a captura |
| `ping.post_handover_seconds` | `10` | Por quanto tempo continuar capturando após o handover |
| `iperf.enabled` | `false` | Ativa a medição simultânea com iperf |
| `iperf.target` | `192.168.70.135` | Destino do iperf no lado público do oai-ext-dn |
| `iperf.mode` | `udp` | `udp` ou `tcp` |
| `iperf.duration_seconds` | `10` | Duração da medição com iperf |

### Substituição por variáveis de ambiente

Todos os scripts leem estas variáveis de ambiente, que têm precedência sobre o `config.yaml`:

| Variável | Usada por | Finalidade |
|---|---|---|
| `N2_SOURCE_GNB_TELNET_HOST` | script de disparo | Substitui o IP do Telnet da gNB de origem |
| `N2_SOURCE_GNB_TELNET_PORT` | script de disparo | Substitui a porta do Telnet da gNB de origem |
| `N2_TARGET_PCI` | script de disparo | Substitui a PCI de destino |
| `N2_UE_RRC_ID` | script de disparo | Substitui o ID RRC do UE |
| `PING_TARGET` | teste rápido | Substitui o destino do ping |
| `PING_INTERFACE` | teste rápido | Substitui a interface do ping |
| `PING_INTERVAL` | teste rápido | Substitui o intervalo do ping |
| `PING_POST_HANDOVER_SECONDS` | teste rápido | Substitui a duração da captura após o handover |
| `IPERF_ENABLED` | teste rápido/repetido | Ativa o iperf simultâneo (`1`, `true`, `yes` ou `on`) |
| `IPERF_REQUIRED` | teste rápido/repetido | Faz a execução falhar se o iperf não for concluído |
| `IPERF_TARGET` | teste rápido/repetido | Substitui o destino do iperf |
| `IPERF_MODE` | teste rápido/repetido | Seleciona `udp` ou `tcp` |
| `IPERF_DURATION` | teste rápido/repetido | Substitui a duração do iperf, em segundos |
| `IPERF_INTERFACE` | iperf avulso | Substitui a interface de origem do UE |
| `UE_DATA_READY_TIMEOUT` | teste rápido | Segundos de espera pelo plano de dados do UE (padrão 120) |
| `RUNS` | teste repetido | Número de execuções (padrão 5) |
| `RESET_BETWEEN_RUNS` | teste repetido | Reinicializa antes de cada execução; ativado por padrão na N2 |

---

## 5. Iniciar o testbed

O `up.sh` inicia o 5GC e a topologia de RAN selecionada com um único comando. Se o 5GC já estiver rodando, ele é reutilizado.

```bash
./scripts/up.sh n2-monolithic   # Topology A
./scripts/up.sh n2-cu-du        # Topology B
```

O `up.sh` executa o `preflight_check.sh` automaticamente e bloqueia até que o `oai-nr-ue` esteja rodando; depois, executa o `poststart_check.sh`.

---

## 6. Topologia A — duas gNBs monolíticas

### Iniciar

```bash
./scripts/up.sh n2-monolithic
```

A ordem de inicialização é garantida por `depends_on`: o `oai-nr-ue` sobe primeiro e, depois, a `oai-gnb0` e a `oai-gnb1` em paralelo.

### Verificar se os contêineres estão rodando

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-gnb0|oai-gnb1"
```

### Verificar se o Telnet da oai-gnb0 está alcançável

```bash
nc -z -w 3 192.168.70.160 9090 && echo "reachable" || echo "not reachable"
```

### Verificar se o Telnet da oai-gnb1 está alcançável

```bash
nc -z -w 3 192.168.70.161 9090 && echo "reachable" || echo "not reachable"
```

### Acompanhar os logs da oai-gnb0

```bash
docker logs -f oai-gnb0
```

Procure `Received NGAP INITIAL_CONTEXT_SETUP_REQUEST` para confirmar que o UE se conectou à oai-gnb0.

---

## 7. Topologia B — dois pares CU+DU

### Iniciar

```bash
./scripts/up.sh n2-cu-du
```

Ordem de inicialização: `oai-nr-ue` → `oai-cu0` → `oai-du0` → `oai-cu1` → `oai-du1`.

### Verificar se os contêineres estão rodando

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-cu0|oai-du0|oai-cu1|oai-du1"
```

### Verificar o Telnet da oai-cu0 (usado para disparar o handover)

```bash
nc -z -w 3 192.168.70.150 9090 && echo "reachable" || echo "not reachable"
```

### Acompanhar os logs da oai-cu0

```bash
docker logs -f oai-cu0
```

---

## 8. Disparar o handover N2 manualmente

### O que o comando faz

O comando de disparo envia `ci trigger_n2_ho <target_pci>,<ue_rrc_id>` para a interface Telnet da gNB de origem. A gNB de origem inicia o procedimento de handover N2 com o AMF, que coordena a transferência para a gNB de destino.

### Pelo script de disparo (recomendado)

O script lê os padrões do `config.yaml`, avisa sobre o Tailscale, verifica se a porta está alcançável e acrescenta eventos ao `RUN_DIR`, se definido. Sem argumento, ele detecta automaticamente a topologia em execução.

```bash
./scripts/trigger_handover.sh                     # auto-detect
./scripts/trigger_handover.sh n2-monolithic       # explicit
./scripts/trigger_handover.sh n2-cu-du            # topology B (source is cu0)
```

### Manualmente, com nc

Topologia A — disparar a partir da oai-gnb0, com destino oai-gnb1 (PCI=1, ID RRC do UE=1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090 && echo
```

Topologia B — disparar a partir da oai-cu0, com destino oai-cu1/oai-du1 (PCI=1, ID RRC do UE=1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.150 9090 && echo
```

### Saída esperada

O comando `nc` imprime a resposta do Telnet da gNB, que normalmente inclui uma linha como:

```
RRC N2 handover triggered for UE 1
```

Após o disparo, acompanhe os logs das gNBs de origem e de destino para ver a sequência NGAP Handover Required / Handover Request / Handover Command.

### Descobrir o ID RRC do UE

Se o ID RRC do UE não for 1 (por exemplo, após uma reconexão), consulte o Telnet da gNB de origem:

```bash
echo "ue" | nc -N 192.168.70.160 9090
```

A resposta lista os UEs conectados com seus IDs RRC.

---

## 9. Teste rápido automatizado

O teste rápido automatiza o fluxo completo: inicia o 5GC e a RAN (se ainda não estiverem rodando), aguarda a prontidão do plano de dados do UE, captura métricas de ping, opcionalmente roda o iperf simultaneamente, dispara o handover, processa os resultados e grava um resumo.

```bash
./scripts/run_smoke_test.sh n2-monolithic   # Topology A
./scripts/run_smoke_test.sh n2-cu-du        # Topology B
```

Ative o iperf UDP ou TCP opcional durante o handover:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh n2-monolithic
IPERF_ENABLED=1 IPERF_MODE=tcp ./scripts/run_smoke_test.sh n2-cu-du
```

As falhas do iperf são registradas sem invalidar resultados de ping que, fora isso, sejam válidos, a menos que `IPERF_REQUIRED=1` esteja definido.

### O que ele faz, passo a passo

1. Cria um diretório de execução com carimbo de tempo em `results/runs/` (por exemplo, `20260604_120000_n2_monolithic_smoke`)
2. Executa o `preflight_check.sh`
3. Verifica pelo `status.sh` se o testbed já está rodando; se não estiver, inicia-o pelo `up.sh`
4. Aguarda até 120 s para que o plano de dados do UE alcance `192.168.71.135` pela `oaitun_ue1`
5. Executa uma pré-verificação de ping com 2 pacotes para confirmar a conectividade
6. Inicia uma captura contínua de ping com carimbo de tempo em segundo plano
7. Se ativado, inicia o iperf vinculado ao endereço PDU do UE na `oaitun_ue1`
8. Aguarda 3 s e, então, chama o `trigger_handover.sh`
9. Mantém o ping rodando pela duração configurada após o handover
10. Aguarda o iperf, processa o ping e armazena os dois conjuntos de métricas
11. Coleta os logs dos contêineres com o `collect_logs.sh`
12. Grava o `summary.json`
13. Em caso de sucesso, imprime o caminho do diretório da execução

### Exemplo de substituição — captura mais longa após o handover

```bash
PING_POST_HANDOVER_SECONDS=30 ./scripts/run_smoke_test.sh n2-monolithic
```

---

## 10. Experimentos repetidos

Execute vários testes rápidos em sequência e obtenha estatísticas agregadas:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

Por padrão, as execuções N2 repetidas reinicializam a topologia antes de cada tentativa. Isso devolve o UE à célula de origem antes do próximo handover no mesmo sentido. Defina `RESET_BETWEEN_RUNS=0` somente quando o experimento oferecer outro mecanismo para voltar à célula de origem.

Ative o iperf em todas as execuções:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

### Saída

É criado um diretório com carimbo de tempo em `results/repeated/` (por exemplo, `20260604_120000_n2_monolithic_repeated`) contendo:

| Arquivo | Conteúdo |
|---|---|
| `runs.txt` | Caminhos de cada diretório de execução individual |
| `run_1.log` … `run_N.log` | stdout/stderr completos de cada teste rápido |
| `summary.csv` | Métricas de cada execução em forma de tabela |
| `summary.json` | Estatísticas agregadas de todas as execuções |

O `summary.json` inclui média, mínimo, máximo e desvio-padrão das métricas de ping e das métricas de iperf disponíveis (vazão, jitter, perda e retransmissões). Também inclui `iperf_status_counts`.

---

## 11. Leitura dos resultados

### Estrutura do diretório da execução

```
results/runs/20260604_120000_n2_monolithic_smoke/
  events.csv          — timestamped event log (precheck, handover trigger, etc.)
  ping_raw.log        — raw ping output from oai-nr-ue
  ping_precheck_raw.log — precheck ping output (separate from capture)
  ping.csv            — parsed per-packet RTT samples
  ping_summary.json   — parsed metrics
  summary.json        — overall smoke test result
  ping_target.txt     — which IP was pinged
  ping_interface.txt  — which interface was used
  iperf_raw.json      — iperf3 JSON output when enabled
  iperf_summary.json  — parsed throughput/jitter/loss metrics when enabled
  iperf_command.txt   — exact client command and UE source binding
  iperf_server.log    — oai-ext-dn iperf server output
  docker_ps.txt       — container state at collection time
  host_info.txt       — host metadata
```

### Métricas principais do `ping_summary.json`

```json
{
  "packets_transmitted": 64,
  "packets_received": 63,
  "packet_loss_percent": 1.56,
  "rtt_min_ms": 4.2,
  "rtt_avg_ms": 8.7,
  "rtt_max_ms": 312.4,
  "estimated_interruption_ms": 207.1,
  "first_ping_after_handover_ms": 93.3,
  "ping_metrics_valid": true
}
```

- **`estimated_interruption_ms`** — intervalo entre o último ping antes e o primeiro ping depois do handover, calculado a partir do carimbo de tempo do evento `handover_trigger_start`.
- **`first_ping_after_handover_ms`** — RTT da primeira resposta bem-sucedida recebida após o evento de disparo.

### Campos principais do `summary.json`

```json
{
  "status": "pass",
  "handover_triggered": true,
  "ue_data_ready": true,
  "ping_precheck_passed": true,
  "ping_metrics_valid": true,
  "estimated_interruption_ms": 207.1,
  "iperf_status": "pass",
  "iperf_protocol": "UDP",
  "iperf_mbps": 1.05,
  "iperf_jitter_ms": 7.08,
  "iperf_lost_percent": 0.0
}
```

O `status` só é `"pass"` se o plano de dados do UE estava pronto, o ping rodou com sucesso durante o handover e o parser encontrou amostras válidas. Uma falha do iperf opcional é representada por `iperf_status: "failed"`; ela só se torna fatal para a execução com `IPERF_REQUIRED=1`.

### Ver a linha do tempo dos eventos

```bash
cat results/runs/<run_id>/events.csv
```

Os eventos principais incluem a pré-verificação/captura de ping, os opcionais `iperf_server_start`, `iperf_client_start` e `iperf_client_end`, os eventos de disparo do handover e o `ping_capture_stop`.

---

## 12. Parar a pilha

### Parar somente a RAN N2

Topologia A:

```bash
docker compose \
  -f experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml \
  down
```

Topologia B:

```bash
docker compose \
  -f experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml \
  down
```

### Parar o 5GC

```bash
cd oai-cn5g && docker compose down && cd ..
```

> **Não** passe `--volumes`, a menos que queira apagar o banco de dados de assinantes. Apagar o banco exige inserir novamente o IMSI do UE antes da próxima execução.

### Parar tudo de uma vez

```bash
cd oai-cn5g && docker compose down && cd ..
docker compose \
  -f experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml \
  down 2>/dev/null || true
docker compose \
  -f experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml \
  down 2>/dev/null || true
```

---

## 13. Solução de problemas

### O UE não se conecta à oai-gnb0

Verifique se o AMF está saudável antes de a oai-gnb0 tentar se registrar:

```bash
docker logs oai-amf | grep "UE Context"
docker logs oai-gnb0 | grep -i "ngap\|ng setup\|error"
```

O AMF precisa concluir o NG Setup com as duas gNBs antes que o UE possa se conectar.

### O disparo do handover não retorna nada ou retorna um erro

1. Confirme que a porta Telnet da gNB de origem está alcançável:
   ```bash
   nc -z -w 3 192.168.70.160 9090 && echo ok
   ```
2. Verifique se o UE está conectado à gNB de origem com ID RRC 1:
   ```bash
   echo "ue" | nc -N 192.168.70.160 9090
   ```
3. Se o Tailscale estiver ativo, desative-o:
   ```bash
   sudo tailscale down
   ```

### O handover é disparado, mas o UE perde a conectividade de forma permanente

A gNB de destino pode não ter concluído o NG Setup com o AMF. Verifique:

```bash
docker logs oai-gnb1 | grep "NG Setup"   # topology A
docker logs oai-cu1  | grep "NG Setup"   # topology B
```

As duas gNBs precisam mostrar um NG Setup bem-sucedido antes do disparo do handover.

### A captura de ping mostra `packets_transmitted: 2`

Isso indica que a saída do ping da pré-verificação contaminou o `ping_raw.log`. Era um bug conhecido, que foi corrigido — a pré-verificação agora grava em `ping_precheck_raw.log`. Se você vir isso num diretório de execução antigo, trata-se de um artefato anterior à correção.

### O teste rápido falha na prontidão do plano de dados do UE

A sessão PDU do UE pode ainda não ter sido estabelecida. Aumente o tempo limite:

```bash
UE_DATA_READY_TIMEOUT=240 ./scripts/run_smoke_test.sh n2-monolithic
```

Verifique também se o UE tem um IP na `oaitun_ue1`:

```bash
docker exec oai-nr-ue ip addr show oaitun_ue1
```

Saída esperada: `inet 10.0.0.2/24`.

### Topologia B: a oai-du0 ou a oai-du1 não consegue se conectar à sua CU

Confirme que o endereço de escuta F1 da CU corresponde ao IP do Compose:

- a `oai-cu0` escuta em `192.168.70.150` — a oai-du0 se conecta a esse endereço
- a `oai-cu1` escuta em `192.168.70.155` — a oai-du1 se conecta a esse endereço

A opção `--gNBs.[0].remote_s_address 0.0.0.0` no `USE_ADDITIONAL_OPTIONS` de cada CU faz a CU aceitar conexões de qualquer endereço de DU.

### O contêiner encerra imediatamente

Verifique se há problemas no download da imagem ou de capabilities:

```bash
docker logs oai-gnb0
docker inspect oai-gnb0 --format '{{.State.ExitCode}}'
```

A ausência da capability `NET_ADMIN` no oai-nr-ue impede a criação da `oaitun_ue1`.
