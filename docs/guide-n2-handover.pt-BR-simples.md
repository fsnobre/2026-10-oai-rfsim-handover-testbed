# Testbed de handover N2: guia de uso

> Tradução para o português em Linguagem Simples. O original em inglês é o [guide-n2-handover.md](guide-n2-handover.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** guia
>
> **Leitura prévia:** [F00](foundation-f00-docker-network-ownership.pt-BR-simples.md), [F01](foundation-f01-functional-readiness-model.pt-BR-simples.md), [F02](foundation-f02-dn-reachability.pt-BR-simples.md), [F03](foundation-f03-rfsim-multicell-operations.pt-BR-simples.md) e [F04](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md)

Este guia mostra tudo o que você precisa para executar experimentos de handover N2 (inter-gNB) no testbed com o simulador de rádio da OAI (rfsim). O handover N2 exige a OAI v2.4.0 ou mais nova.

---

## Sumário

1. [Diferenças entre o handover N2 e o F1](#1-diferenças-entre-o-handover-n2-e-o-f1)
2. [Visão geral das topologias](#2-visão-geral-das-topologias)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Referência da configuração](#4-referência-da-configuração)
5. [Subir o testbed](#5-subir-o-testbed)
6. [Topologia A: duas gNBs monolíticas](#6-topologia-a-duas-gnbs-monolíticas)
7. [Topologia B: dois pares CU+DU](#7-topologia-b-dois-pares-cudu)
8. [Comandar o handover N2 à mão](#8-comandar-o-handover-n2-à-mão)
9. [Teste rápido automático](#9-teste-rápido-automático)
10. [Execuções repetidas](#10-execuções-repetidas)
11. [Ler os resultados](#11-ler-os-resultados)
12. [Parar a pilha](#12-parar-a-pilha)
13. [Solução de problemas](#13-solução-de-problemas)

---

## 1. Diferenças entre o handover N2 e o F1

| | Handover F1 | Handover N2 |
|---|---|---|
| Alcance | Intra-gNB (uma CU, duas DUs) | Inter-gNB (duas gNBs independentes) |
| Quem coordena | A CU move o UE entre as próprias DUs. | O AMF coordena a troca entre as gNBs. |
| Interface usada | F1-C | N2 (NGAP) |
| Comando | `ci trigger_f1_ho` no Telnet da CU | `ci trigger_n2_ho <pci>,<rrc_id>` no Telnet da gNB de origem |
| Versão mínima da OAI | v2.3.0 | v2.4.0 |
| Relatórios de medição do UE | Não são necessários (comando manual) | Não são necessários (comando manual) |

Nos dois casos, o UE é o **servidor do rfsim**. Assim, várias gNBs se conectam ao mesmo UE.

---

## 2. Visão geral das topologias

### Topologia A: duas gNBs monolíticas

```
                     AMF (192.168.70.132)
                    /                    \
           N2 (NGAP)                      N2 (NGAP)
                  /                          \
    oai-gnb0 (192.168.70.160)          oai-gnb1 (192.168.70.161)
    PCI=0  gNB_ID=0xe00            PCI=1  gNB_ID=0xe01
    Telnet :9090                   Telnet :9090
                  \                          /
                   cliente rfsim   cliente rfsim
                          \        /
                      oai-nr-ue (192.168.70.181)
                      servidor rfsim :4043
```

O comando de handover vai para o **Telnet da oai-gnb0**. O destino é a oai-gnb1 (PCI 1).

### Topologia B: dois pares CU+DU

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
    oai-du0 (192.168.70.171)           cliente rfsim
    cliente rfsim                         |
           \                             /
            -------- oai-nr-ue (192.168.70.181) --------
                     servidor rfsim :4043
```

O comando de handover vai para o **Telnet da oai-cu0**. O destino é a célula da oai-cu1/oai-du1 (PCI 1).

---

## 3. Pré-requisitos

- Docker e Docker Compose v2 instalados. A pilha Compose do núcleo 5G da OAI cria e controla as redes `oai-cn5g-public-net` e `oai-ext-dn-traffic-net`. Não crie essas redes à mão. Veja [Quem cria as redes Docker](foundation-f00-docker-network-ownership.pt-BR-simples.md).
- `nc` (netcat) instalado no computador. Ele envia os comandos Telnet.
- `python3` instalado no computador. Ele analisa o ping e junta os resultados.
- Imagens da OAI baixadas:
  ```bash
  docker pull oaisoftwarealliance/oai-gnb:v2.4.0
  docker pull oaisoftwarealliance/oai-nr-ue:v2.4.0
  ```
- Imagens do núcleo 5G já presentes. Baixe-as com `docker compose pull`, na pasta `oai-cn5g/`.

> **ATENÇÃO:** Se o Tailscale estiver ativo, o comando `nc` do handover pode falhar. Execute `sudo tailscale down` antes do comando, ou use o script, que avisa sozinho.

---

## 4. Referência da configuração

Os valores padrão dos experimentos N2 ficam em `experiments/n2_handover/config.yaml`. Edite esse arquivo para mudar o destino do ping, os parâmetros do handover ou a topologia padrão.

### Parâmetros principais

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `source_gnb_ip` | `192.168.70.160` | IP do Telnet da gNB de origem (oai-gnb0 ou oai-cu0) |
| `source_gnb_port` | `9090` | Porta do Telnet |
| `target_pci` | `1` | PCI da célula da gNB de destino |
| `ue_rrc_id` | `1` | Identificador RRC do UE na gNB de origem |
| `ping.target` | `192.168.71.135` | Destino do ping (o `oai-ext-dn` local) |
| `ping.interface` | `oaitun_ue1` | Interface da sessão PDU do UE |
| `ping.interval_seconds` | `0.2` | Intervalo entre pings durante a captura |
| `ping.post_handover_seconds` | `10` | Tempo de captura depois do handover |
| `iperf.enabled` | `false` | Liga a medição com iperf ao mesmo tempo |
| `iperf.target` | `192.168.70.135` | Destino do iperf, no lado público do `oai-ext-dn` |
| `iperf.mode` | `udp` | `udp` ou `tcp` |
| `iperf.duration_seconds` | `10` | Duração da medição com iperf |

### Variáveis de ambiente

Todos os scripts leem estas variáveis de ambiente. Elas prevalecem sobre o `config.yaml`:

| Variável | Usada por | Finalidade |
|---|---|---|
| `N2_SOURCE_GNB_TELNET_HOST` | script de handover | Troca o IP do Telnet da gNB de origem |
| `N2_SOURCE_GNB_TELNET_PORT` | script de handover | Troca a porta do Telnet da gNB de origem |
| `N2_TARGET_PCI` | script de handover | Troca o PCI de destino |
| `N2_UE_RRC_ID` | script de handover | Troca o identificador RRC do UE |
| `PING_TARGET` | teste rápido | Troca o destino do ping |
| `PING_INTERFACE` | teste rápido | Troca a interface do ping |
| `PING_INTERVAL` | teste rápido | Troca o intervalo entre pings |
| `PING_POST_HANDOVER_SECONDS` | teste rápido | Troca o tempo de captura depois do handover |
| `IPERF_ENABLED` | testes rápidos e repetidos | Liga o iperf ao mesmo tempo (`1`, `true`, `yes` ou `on`) |
| `IPERF_REQUIRED` | testes rápidos e repetidos | Faz a execução falhar se o iperf não terminar |
| `IPERF_TARGET` | testes rápidos e repetidos | Troca o destino do iperf |
| `IPERF_MODE` | testes rápidos e repetidos | Escolhe `udp` ou `tcp` |
| `IPERF_DURATION` | testes rápidos e repetidos | Troca a duração do iperf, em segundos |
| `IPERF_INTERFACE` | iperf avulso | Troca a interface de origem no UE |
| `UE_DATA_READY_TIMEOUT` | teste rápido | Segundos de espera pelo plano de usuário do UE (padrão: 120) |
| `RUNS` | teste repetido | Número de execuções (padrão: 5) |
| `RESET_BETWEEN_RUNS` | teste repetido | Recria a topologia antes de cada execução. No N2, vem ligado. |

---

## 5. Subir o testbed

O `up.sh` sobe o núcleo 5G e a topologia da RAN escolhida com um único comando. Se o núcleo 5G já estiver rodando, o script o reaproveita.

```bash
./scripts/up.sh n2-monolithic   # topologia A
./scripts/up.sh n2-cu-du        # topologia B
```

O `up.sh` executa o `preflight_check.sh` sozinho. Ele espera o `oai-nr-ue` estar rodando e, em seguida, executa o `poststart_check.sh`.

---

## 6. Topologia A: duas gNBs monolíticas

### Subir

```bash
./scripts/up.sh n2-monolithic
```

O `depends_on` garante a ordem de subida: primeiro o `oai-nr-ue`, depois a `oai-gnb0` e a `oai-gnb1`, ao mesmo tempo.

### Conferir se os contêineres estão rodando

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-gnb0|oai-gnb1"
```

### Conferir se o Telnet da oai-gnb0 responde

```bash
nc -z -w 3 192.168.70.160 9090 && echo "reachable" || echo "not reachable"
```

### Conferir se o Telnet da oai-gnb1 responde

```bash
nc -z -w 3 192.168.70.161 9090 && echo "reachable" || echo "not reachable"
```

### Acompanhar os logs da oai-gnb0

```bash
docker logs -f oai-gnb0
```

Procure a linha `Received NGAP INITIAL_CONTEXT_SETUP_REQUEST`. Ela confirma que o UE se conectou à oai-gnb0.

---

## 7. Topologia B: dois pares CU+DU

### Subir

```bash
./scripts/up.sh n2-cu-du
```

Ordem de subida: `oai-nr-ue` → `oai-cu0` → `oai-du0` → `oai-cu1` → `oai-du1`.

### Conferir se os contêineres estão rodando

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "oai-nr-ue|oai-cu0|oai-du0|oai-cu1|oai-du1"
```

### Conferir o Telnet da oai-cu0 (usado no comando de handover)

```bash
nc -z -w 3 192.168.70.150 9090 && echo "reachable" || echo "not reachable"
```

### Acompanhar os logs da oai-cu0

```bash
docker logs -f oai-cu0
```

---

## 8. Comandar o handover N2 à mão

### O que o comando faz

O comando envia `ci trigger_n2_ho <pci_de_destino>,<id_rrc_do_ue>` para a interface Telnet da gNB de origem. A gNB de origem inicia o procedimento de handover N2 com o AMF. O AMF coordena a troca para a gNB de destino.

### Pelo script (recomendado)

O script:

- lê os valores padrão do `config.yaml`;
- avisa sobre o Tailscale;
- confere se a porta responde;
- acrescenta os eventos em `RUN_DIR`, se essa variável existir.

Sem argumento, ele descobre a topologia ativa sozinho.

```bash
./scripts/trigger_handover.sh                     # descobre a topologia
./scripts/trigger_handover.sh n2-monolithic       # topologia informada
./scripts/trigger_handover.sh n2-cu-du            # topologia B (a origem é a cu0)
```

### À mão, com o nc

Topologia A: comando na oai-gnb0, destino oai-gnb1 (PCI 1, identificador RRC do UE 1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.160 9090 && echo
```

Topologia B: comando na oai-cu0, destino oai-cu1/oai-du1 (PCI 1, identificador RRC do UE 1):

```bash
echo ci trigger_n2_ho 1,1 | nc -N 192.168.70.150 9090 && echo
```

### Saída esperada

O `nc` mostra a resposta do Telnet da gNB. Em geral, ela tem uma linha como esta:

```
RRC N2 handover triggered for UE 1
```

Depois do comando, acompanhe os logs das gNBs de origem e de destino. Eles mostram a sequência NGAP: Handover Required, Handover Request e Handover Command.

### Descobrir o identificador RRC do UE

O identificador RRC do UE pode não ser 1, por exemplo, depois de uma nova conexão. Nesse caso, consulte o Telnet da gNB de origem:

```bash
echo "ue" | nc -N 192.168.70.160 9090
```

A resposta lista os UEs conectados e os identificadores RRC deles.

---

## 9. Teste rápido automático

O teste rápido automatiza todo o processo:

- sobe o núcleo 5G e a RAN, se ainda não estiverem rodando;
- espera o plano de usuário do UE ficar pronto;
- captura as métricas de ping;
- roda o iperf ao mesmo tempo, se estiver ligado;
- comanda o handover;
- analisa os resultados e grava um resumo.

```bash
./scripts/run_smoke_test.sh n2-monolithic   # topologia A
./scripts/run_smoke_test.sh n2-cu-du        # topologia B
```

Para medir com iperf em UDP ou TCP durante o handover, use:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh n2-monolithic
IPERF_ENABLED=1 IPERF_MODE=tcp ./scripts/run_smoke_test.sh n2-cu-du
```

O testbed registra as falhas do iperf, mas não anula os resultados válidos de ping. A exceção é quando `IPERF_REQUIRED=1` está definido.

### O que o teste faz, passo a passo

1. Cria uma pasta de execução com data e hora em `results/runs/`. Exemplo: `20260604_120000_n2_monolithic_smoke`.
2. Executa o `preflight_check.sh`.
3. Confere, pelo `status.sh`, se o testbed já está rodando. Se não estiver, sobe-o com o `up.sh`.
4. Espera até 120 s o plano de usuário do UE alcançar `192.168.71.135` pela `oaitun_ue1`.
5. Executa um teste de ping com 2 pacotes para confirmar a conexão.
6. Inicia uma captura contínua de ping, com horário, em segundo plano.
7. Se estiver ligado, inicia o iperf com o endereço da sessão PDU do UE, na `oaitun_ue1`, como origem.
8. Espera 3 s e chama o `trigger_handover.sh`.
9. Mantém o ping pelo tempo configurado depois do handover.
10. Espera o iperf, analisa o ping e guarda os dois conjuntos de métricas.
11. Coleta os logs dos contêineres com o `collect_logs.sh`.
12. Grava o `summary.json`.
13. Se der certo, mostra o caminho da pasta da execução.

### Exemplo de troca de valor: captura mais longa depois do handover

```bash
PING_POST_HANDOVER_SECONDS=30 ./scripts/run_smoke_test.sh n2-monolithic
```

---

## 10. Execuções repetidas

Para executar vários testes rápidos seguidos e obter estatísticas agregadas, use:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

No N2, as execuções repetidas recriam a topologia antes de cada execução, por padrão. Assim, o UE volta à célula de origem antes do próximo handover no mesmo sentido. Só use `RESET_BETWEEN_RUNS=0` se o experimento tiver outro mecanismo para voltar o UE à célula de origem.

Para ligar o iperf em todas as execuções, use:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

### Saída

O script cria uma pasta com data e hora em `results/repeated/`. Exemplo: `20260604_120000_n2_monolithic_repeated`. A pasta tem:

| Arquivo | Conteúdo |
|---|---|
| `runs.txt` | Caminhos das pastas de cada execução |
| `run_1.log` … `run_N.log` | Saída completa (stdout e stderr) de cada teste rápido |
| `summary.csv` | Métricas de cada execução, em tabela |
| `summary.json` | Estatísticas agregadas de todas as execuções |

O `summary.json` traz média, mínimo, máximo e desvio-padrão das métricas de ping. Ele também traz as métricas de iperf disponíveis: vazão, jitter, perda e retransmissões. Ele inclui ainda o campo `iperf_status_counts`.

---

## 11. Ler os resultados

### Organização da pasta de uma execução

```
results/runs/20260604_120000_n2_monolithic_smoke/
  events.csv          — registro de eventos com horário (teste inicial, comando de handover etc.)
  ping_raw.log        — saída bruta do ping no oai-nr-ue
  ping_precheck_raw.log — saída do teste inicial de ping (separada da captura)
  ping.csv            — RTT de cada pacote
  ping_summary.json   — métricas calculadas
  summary.json        — resultado geral do teste rápido
  ping_target.txt     — IP usado no ping
  ping_interface.txt  — interface usada
  iperf_raw.json      — saída JSON do iperf3, quando ligado
  iperf_summary.json  — vazão, jitter e perda, quando ligado
  iperf_command.txt   — comando exato do cliente e endereço de origem no UE
  iperf_server.log    — saída do servidor iperf no oai-ext-dn
  docker_ps.txt       — estado dos contêineres no momento da coleta
  host_info.txt       — dados do computador
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

- **`estimated_interruption_ms`:** intervalo entre o último ping antes do handover e o primeiro depois dele. Ele usa o horário do evento `handover_trigger_start`.
- **`first_ping_after_handover_ms`:** RTT da primeira resposta recebida depois do evento do comando.

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

O `status` só é `"pass"` quando:

- o plano de usuário do UE ficou pronto;
- o ping funcionou durante o handover;
- o analisador encontrou amostras válidas.

Uma falha do iperf opcional aparece como `iperf_status: "failed"`. Ela só derruba a execução com `IPERF_REQUIRED=1`.

### Ver a linha do tempo dos eventos

```bash
cat results/runs/<run_id>/events.csv
```

Os eventos principais são:

- o teste inicial e a captura do ping;
- `iperf_server_start`, `iperf_client_start` e `iperf_client_end`, quando o iperf está ligado;
- os eventos do comando de handover;
- `ping_capture_stop`.

---

## 12. Parar a pilha

### Parar só a RAN do N2

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

### Parar o núcleo 5G

```bash
cd oai-cn5g && docker compose down && cd ..
```

> **CUIDADO:** Não use `--volumes`, a menos que queira apagar a base de assinantes. Depois de apagar a base, você precisa cadastrar de novo o IMSI do UE antes da próxima execução.

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

Confira se o AMF está saudável antes de a oai-gnb0 tentar se registrar:

```bash
docker logs oai-amf | grep "UE Context"
docker logs oai-gnb0 | grep -i "ngap\|ng setup\|error"
```

O AMF precisa concluir o NG Setup com as duas gNBs antes de o UE se conectar.

### O comando de handover não responde ou retorna erro

1. Confirme que a porta Telnet da gNB de origem responde:
   ```bash
   nc -z -w 3 192.168.70.160 9090 && echo ok
   ```
2. Confira se o UE está conectado à gNB de origem com o identificador RRC 1:
   ```bash
   echo "ue" | nc -N 192.168.70.160 9090
   ```
3. Se o Tailscale estiver ativo, desligue-o:
   ```bash
   sudo tailscale down
   ```

### O handover acontece, mas o UE perde a conexão de vez

A gNB de destino pode não ter concluído o NG Setup com o AMF. Confira:

```bash
docker logs oai-gnb1 | grep "NG Setup"   # topologia A
docker logs oai-cu1  | grep "NG Setup"   # topologia B
```

As duas gNBs precisam mostrar um NG Setup bem-sucedido antes do comando de handover.

### A captura de ping mostra `packets_transmitted: 2`

Isso indica que a saída do teste inicial de ping se misturou ao `ping_raw.log`. Esse erro já foi corrigido: o teste inicial agora grava em `ping_precheck_raw.log`. Se você vir isso em uma pasta de execução antiga, o resultado é anterior à correção.

### O teste rápido falha na espera pelo plano de usuário do UE

A sessão PDU do UE pode ainda não estar pronta. Aumente o tempo de espera:

```bash
UE_DATA_READY_TIMEOUT=240 ./scripts/run_smoke_test.sh n2-monolithic
```

Confira também se o UE tem endereço IP na `oaitun_ue1`:

```bash
docker exec oai-nr-ue ip addr show oaitun_ue1
```

Saída esperada: `inet 10.0.0.2/24`.

### Topologia B: a oai-du0 ou a oai-du1 não se conecta à sua CU

Confirme que o endereço F1 em que a CU escuta é o mesmo IP do Compose:

- a `oai-cu0` escuta em `192.168.70.150`. A oai-du0 se conecta a esse endereço.
- a `oai-cu1` escuta em `192.168.70.155`. A oai-du1 se conecta a esse endereço.

A opção `--gNBs.[0].remote_s_address 0.0.0.0`, no `USE_ADDITIONAL_OPTIONS` de cada CU, faz a CU aceitar conexões de qualquer endereço de DU.

### O contêiner para logo depois de subir

Procure problemas no download da imagem ou nas permissões (*capabilities*):

```bash
docker logs oai-gnb0
docker inspect oai-gnb0 --format '{{.State.ExitCode}}'
```

Sem a permissão `NET_ADMIN`, o oai-nr-ue não consegue criar a `oaitun_ue1`.
