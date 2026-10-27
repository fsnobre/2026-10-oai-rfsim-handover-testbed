# Testbed de handover da OAI em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [README.md](README.md). Se houver diferença entre os dois, vale o original.

Este repositório automatiza experimentos de handover com a OpenAirInterface (OAI). Ele foi feito para pesquisa. Ele tem dois experimentos de handover no simulador de rádio da OAI (rfsim):

| Experimento | Topologia | Comando de handover | Versão da OAI |
|---|---|---|---|
| Handover F1 | 1 CU e 2 DUs (intra-gNB) | Telnet na CU: `ci trigger_f1_ho` | v2.4.0 |
| Handover N2 | 2 gNBs monolíticas **ou** 2 pares CU+DU (inter-gNB) | Telnet na gNB de origem: `ci trigger_n2_ho` | v2.4.0 |

Os dois experimentos usam o mesmo núcleo 5G da OAI (AMF, SMF, UPF e `oai-ext-dn`). Eles também usam o mesmo OAI NR-UE em rfsim.

O repositório também tem topologias com rádio real (USRP X310). Nelas, o UE é um celular comercial (UE comercial, COTS):

| Experimento | Topologia | Rádios | UE |
|---|---|---|---|
| USRP com uma célula | 1 gNB monolítica (`usrp-cots`) | 1 X310 | Celular comercial |
| Handover F1 com USRP | 1 CU e 2 DUs (distribuída) | 2 X310 | Celular comercial |
| Handover N2 com USRP | 2 gNBs **ou** 2 pares CU+DU (distribuída) | 2 X310 | Celular comercial |

Nas topologias de handover, cada computador tem **um rádio**. Veja o [guia do USRP X310 com UE comercial](docs/guide-usrp-x310-cots.pt-BR-simples.md) (uma célula) e o [guia de handover distribuído com USRP](docs/guide-usrp-distributed-handover.pt-BR-simples.md).

Siglas usadas neste documento:

- **UE:** equipamento de usuário;
- **gNB:** estação rádio base 5G;
- **CU:** unidade centralizada da gNB;
- **DU:** unidade distribuída da gNB;
- **RAN:** rede de acesso por rádio;
- **DN:** rede de dados. No testbed, é o contêiner `oai-ext-dn`.

---

## Experimento de handover F1

### Topologia

- 1 núcleo 5G da OAI (AMF, SMF, UPF e `oai-ext-dn`)
- 1 UPF fixo
- 1 CU (`192.168.70.150`)
- 2 DUs (`192.168.70.171` e `192.168.70.172`)
- 1 OAI NR-UE em rfsim (`192.168.70.181`)
- Handover F1 manual, comandado pela interface Telnet da CU

Nomes dos contêineres: `oai-amf`, `oai-smf`, `oai-upf`, `oai-cu`, `oai-du0`, `oai-du1` e `oai-nr-ue`.

### Resultado de referência

O resultado de referência tem 5 execuções do teste rápido (*smoke test*). O UE envia ping para o `oai-ext-dn` local (`192.168.71.135`) pela interface `oaitun_ue1`. As 5 execuções passaram, com 0,0% de perda de pacotes. A média da interrupção estimada do handover foi de **207,07 ms**.

O [relatório do resultado de referência](docs/report-baseline-results.pt-BR-simples.md) tem os resultados completos e a interpretação.

### Uso

1. Suba o testbed:

   ```bash
   ./scripts/up.sh f1
   ```

2. Confira se está pronto:

   ```bash
   ./scripts/status.sh
   ```

3. Comande o handover F1 à mão:

   ```bash
   ./scripts/trigger_handover.sh
   ```

Para executar o teste rápido, use o comando abaixo. Ele sobe a pilha, captura o ping durante o handover e grava os resultados:

```bash
./scripts/run_smoke_test.sh f1
```

Para medir com iperf ao mesmo tempo que o handover, use:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh f1
```

O iperf envia tráfego para o endereço público do `oai-ext-dn` (`192.168.70.135`). Ele usa o endereço da sessão PDU do UE como origem. Se o iperf falhar, o testbed registra a falha, mas mantém os resultados válidos de ping e de handover. Para tornar o iperf obrigatório, use `IPERF_REQUIRED=1`.

Para executar 5 testes rápidos seguidos e juntar os resultados, use:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh f1
```

Para incluir o iperf em todas as execuções, use:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh f1
```

Se você estiver investigando o acesso à rede de dados local, use um destino na internet:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh f1
```

Para mudar o tempo máximo de espera pelo plano de usuário do UE, use:

```bash
UE_DATA_READY_TIMEOUT=180 ./scripts/run_smoke_test.sh f1
```

---

## Experimento de handover N2

**Guia completo: [docs/guide-n2-handover.pt-BR-simples.md](docs/guide-n2-handover.pt-BR-simples.md)**

O handover N2 acontece entre gNBs e é coordenado pelo AMF. Ele existe na OAI a partir da v2.4.0. O testbed tem duas topologias:

- **`n2-monolithic`: duas gNBs independentes** (`oai-gnb0` em `192.168.70.160` e `oai-gnb1` em `192.168.70.161`)
- **`n2-cu-du`: dois pares CU+DU** (`oai-cu0`/`oai-du0` e `oai-cu1`/`oai-du1`)

Nas duas topologias, o UE (`192.168.70.181`) é o servidor do rfsim.

### Início rápido

```bash
./scripts/up.sh n2-monolithic          # ou n2-cu-du
./scripts/trigger_handover.sh          # descobre a topologia pelos contêineres ativos
```

### Teste rápido automático

```bash
./scripts/run_smoke_test.sh n2-monolithic
./scripts/run_smoke_test.sh n2-cu-du
```

### Execuções repetidas

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

No N2, o testbed recria a topologia antes de cada execução. Assim, todo handover começa na célula de origem. Para mudar isso, use `RESET_BETWEEN_RUNS=0`. Só faça isso se tiver um motivo.

---

## Experimento com USRP X310 (rádio real)

**Guia completo: [docs/guide-usrp-x310-cots.pt-BR-simples.md](docs/guide-usrp-x310-cots.pt-BR-simples.md)**

Uma gNB monolítica controla um USRP X310 por Ethernet de 10 Gbit/s. Um celular comercial, com um chip SIM programado, se conecta pelo ar. Não há rfsim, modelo de canal nem contêiner `oai-nr-ue`.

### Início rápido

```bash
./scripts/check_usrp.sh                 # testa o X310 (ping e uhd_usrp_probe)
./scripts/preflight_check.sh usrp-cots  # verificação prévia própria para USRP
./scripts/up.sh usrp-cots               # sobe o núcleo 5G e a gNB; espera a associação NG com o AMF
./scripts/status.sh                     # associação NG da gNB e registro do UE (pelos logs do AMF)
```

Depois, ligue o celular. O chip SIM deve estar programado com os dados de `oai-cn5g/database/oai_db.sql`. Meça o plano de usuário à mão no celular, com o navegador ou um teste de velocidade. Os testes rápidos automáticos só funcionam com rfsim.

O computador do X310 precisa de quadros jumbo e de buffers de socket grandes (`mtu 9000`, `net.core.rmem_max/wmem_max`). Veja o guia.

---

## Handover com USRP X310 (distribuído, rádio real)

**Guia completo: [docs/guide-usrp-distributed-handover.pt-BR-simples.md](docs/guide-usrp-distributed-handover.pt-BR-simples.md)**

As três topologias de handover (F1, N2 monolítica e N2 CU/DU) também rodam com rádios X310 reais. Cada computador tem **um rádio**. Cada DU ou gNB roda em um computador próprio, com a rede do computador (*host networking*). As CUs não têm rádio. As configurações ficam em `experiments/usrp_handover/`. Cada computador recebe os endereços dos outros nós por um arquivo `.env`.

```bash
# Computador do núcleo 5G: torna o núcleo acessível aos computadores da RAN (sem mudar o núcleo)
sudo ./scripts/usrp_core_routing.sh <ip-do-núcleo-na-LAN>

# Em cada computador da RAN: copie o .env.example da topologia para .env, preencha os IPs da LAN e execute:
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0    # exemplo: no computador da gnb0

# Comande o handover de um computador de controle, apontando para o IP do nó de origem na LAN:
N2_SOURCE_GNB_TELNET_HOST=<ip-da-gnb0-na-LAN> ./scripts/trigger_handover.sh n2-monolithic
```

---

## Operações comuns

### Acrescentar arquivos Compose à RAN

A variável `RAN_COMPOSE_OVERLAY` acrescenta arquivos Compose depois do arquivo Compose da RAN da topologia. Assim, um experimento externo muda as configurações dos serviços sem editar os arquivos Compose deste repositório:

```bash
RAN_COMPOSE_OVERLAY=/caminho/para/overlay.yml ./scripts/up.sh f1
```

Para usar vários arquivos, separe-os com dois-pontos. O Compose aplica os arquivos da esquerda para a direita. Por isso, o último arquivo prevalece:

```bash
RAN_COMPOSE_OVERLAY=/caminho/a.yml:/caminho/b.yml ./scripts/up.sh f1
```

Todos os scripts que carregam `scripts/lib.sh` respeitam essa variável, inclusive `up.sh`, `down.sh` e `preflight_check.sh`. **Passe para o `down.sh` o mesmo valor que passou para o `up.sh`.** Assim, o `down.sh` derruba a pilha com a mesma configuração.

Se um arquivo da lista não existir, o script para na hora, com código de saída 2. O arquivo Compose base fica sempre em primeiro lugar. Por isso, a pasta e o nome do projeto Compose não mudam. Os caminhos relativos dentro do arquivo base também continuam válidos.

O uso mais comum é acrescentar opções ao softmodem ou montar outro arquivo de configuração. A variável `USE_ADDITIONAL_OPTIONS` é substituída inteira, e não mesclada. Por isso, o arquivo acrescentado deve repetir as opções que você quer manter:

```yaml
services:
    du0:
        environment:
            USE_ADDITIONAL_OPTIONS: --rfsim
                                    --log_config.global_log_options level,nocolor,time
                                    --rfsimulator.[0].serveraddr 192.168.70.181
                                    --rfsimulator.[0].options chanmod
```

A ordem de inicialização importa. Por isso, use o `up.sh`, e não apenas `docker compose up -d`. O UE é o servidor do rfsim. Se você reiniciar o UE com as DUs ativas, o plano de usuário não volta.

### Parar o testbed

O script descobre sozinho a topologia ativa:

```bash
./scripts/down.sh
```

Você também pode informar a topologia:

```bash
./scripts/down.sh f1
./scripts/down.sh n2-monolithic
./scripts/down.sh n2-cu-du
./scripts/down.sh usrp-cots
```

Para apagar também os volumes do Compose, acrescente `--volumes`. Isso apaga a base de assinantes:

```bash
./scripts/down.sh --volumes
```

### Coletar os logs

```bash
./scripts/collect_logs.sh
./scripts/collect_logs.sh --run-dir results/runs/<id_da_execução>
```

### Diagnosticar o acesso à rede de dados

```bash
./scripts/diagnose_dn_reachability.sh
```

O script grava em `results/diagnostics/` o estado das redes Docker, as rotas, testes de ping, as regras de firewall e um resumo. Ele não muda nenhuma configuração.

Documentação:

- [Mapa da documentação e ordem de leitura](docs/README.pt-BR-simples.md)
- [Tutorial de handover F1](docs/tutorial-f1-handover.pt-BR-simples.md)
- [Tutorial de handover N2 com gNBs monolíticas](docs/tutorial-n2-monolithic-handover.pt-BR-simples.md)
- [Tutorial de handover N2 com pares CU/DU](docs/tutorial-n2-cu-du-handover.pt-BR-simples.md)
- [Guia do USRP X310 com UE comercial](docs/guide-usrp-x310-cots.pt-BR-simples.md)
- [Guia de handover distribuído com USRP](docs/guide-usrp-distributed-handover.pt-BR-simples.md)
- [Conjunto validado de experimentos nas três topologias](results/validated/2026-06-19/README.pt-BR-simples.md)

### Medição avulsa com iperf3 (opcional)

1. Confira se o iperf3 está disponível:

   ```bash
   ./scripts/check_iperf_support.sh
   ```

2. Execute um teste UDP do `oai-nr-ue` para o `oai-ext-dn`:

   ```bash
   IPERF_MODE=udp IPERF_DURATION=10 ./scripts/run_iperf_test.sh
   ```

---

## Falhas conhecidas e soluções

Antes de subir o testbed, execute `./scripts/preflight_check.sh`. Ele detecta os problemas da tabela abaixo. Para cada um, ele mostra `[PASS]`, `[WARN]` ou `[FAIL]`. Depois de subir o testbed, execute `./scripts/poststart_check.sh` para conferir se tudo está funcionando.

Se você tiver certeza de que o ambiente está correto, pule a verificação prévia uma vez:

```bash
SKIP_PREFLIGHT=1 ./scripts/up.sh
```

### Tabela de problemas

| Falha | Sintoma | Solução |
|---|---|---|
| **Nó de saída do Tailscale sem acesso à LAN** *ou* **rota pela `tailscale0`** | `nc` ou Telnet para 192.168.70.x falha. | Execute `sudo tailscale set --exit-node-allow-lan-access=true`. Outra opção é desligar o nó de saída ou executar `sudo tailscale down`. |
| **WireGuard ativo** | O tráfego para 192.168.70.x vai para o lugar errado. | Desconecte o WireGuard com `wg-quick down <interface>`. |
| **OpenVPN ou outra VPN com TUN** | O mesmo do WireGuard. | Desconecte a VPN. |
| **Contêineres antigos** | Ao subir, o Docker diz que o nome do contêiner já está em uso. | Execute `docker rm -f <nomes>`. |
| **Falta a rede Docker do núcleo 5G** | A verificação prévia avisa que o Compose vai criar a rede. | Execute `./scripts/up.sh`. Não crie redes compartilhadas à mão. |
| **Rede Docker do núcleo 5G incompatível** | A verificação prévia mostra sub-rede ou dono errados. | Pare os contêineres ligados à rede. Apague a rede incompatível. Execute `./scripts/up.sh` de novo. |
| **Conflito de sub-rede** | O tráfego vai para o lugar errado, sem erro. | Apague ou reconfigure a interface ou a rota em conflito. |
| **Falta `/dev/net/tun`** | A interface `oaitun_ue1` não aparece. O plano de usuário não fica pronto no tempo. | Execute `sudo modprobe tun`. |
| **SCTP não carregado** | O NG Setup com o AMF não termina. | Execute `sudo modprobe sctp`. |
| **Porta 9090 ou 4043 ocupada** | O Telnet não responde, ou o rfsim não conecta. | Encerre o processo que ocupa a porta ou apague o contêiner travado com `docker rm -f`. |
| **iptables FORWARD com DROP** | O UE não alcança o `oai-ext-dn`. | Confira a cadeia FORWARD. Garanta que nada sobrescreve as regras do Docker. |
| **AppArmor bloqueia NET_ADMIN** | A interface `oaitun_ue1` não aparece, sem erro visível. | Confira com `dmesg \| grep apparmor`. Ajuste o perfil. |
| **Relógio fora de sincronia** | A autenticação NAS falha. | Execute `sudo systemctl restart systemd-timesyncd`. |
| **Imagens não baixadas** | A primeira execução demora ou falha ao baixar as imagens. | Execute `docker pull oaisoftwarealliance/oai-gnb:develop && docker pull oaisoftwarealliance/oai-nr-ue:develop`. |
| **Pouco espaço em disco** | A coleta de logs ou a gravação dos resultados falha sem aviso. | Apague execuções antigas em `results/runs/` e `results/repeated/`. |

---

## Organização do repositório

```
experiments/
  manual_f1_handover/        configuração do experimento de handover F1
  n2_handover/               configuração do experimento de handover N2
    config.yaml
    topology_a_monolithic/   duas gNBs monolíticas
    topology_b_cu_du/        dois pares CU+DU
  usrp_x310/                 gNB com USRP X310 e rádio real, uma célula (UE comercial)
    config.yaml
    conf-gnb-usrp.conf
    gnb-docker-compose.yaml
  usrp_handover/             handover com USRP X310, distribuído (um rádio por computador)
    f1/                      CU e 2 DUs (compose, confs e .env.example por computador)
    n2_monolithic/           2 gNBs
    n2_cu_du/                2 pares CU+DU
scripts/
  up.sh / down.sh / restart.sh / status.sh  (topologias: f1, n2-monolithic, n2-cu-du, usrp-cots)
  wait_ready.sh / wait_ue_data_ready.sh
  trigger_handover.sh        comando de handover (todas as topologias; descobre a topologia se faltar o argumento)
  run_smoke_test.sh          teste rápido (todas as topologias)
  run_repeated_smoke_tests.sh
  preflight_check.sh / poststart_check.sh
  start_ping_capture.sh / collect_logs.sh
  run_iperf_test.sh / check_iperf_support.sh
  check_usrp.sh              teste do USRP X310 (ping e uhd_usrp_probe)
  usrp_core_routing.sh       torna o núcleo 5G acessível aos computadores da RAN distribuída
  usrp_site_up.sh / usrp_site_down.sh  sobe e derruba cada papel USRP em cada computador
  diagnose_dn_reachability.sh
  lib.sh                     funções compartilhadas (apply_topology, detect_topology, ...)
conf-cu.conf                 configuração da CU do F1
conf-du.conf                 configuração base das DUs do F1
conf-nr-ue.conf              configuração do UE (usada por todos os experimentos)
oai-cn5g/                    Docker Compose e configuração do núcleo 5G
tools/
  parse_ping.py
  parse_iperf.py
docs/
  README.md                  ordem de leitura e índice da documentação
  foundation-fNN-*.md        conceitos e regras de base, estáveis
  guide-*.md                 guias amplos de operação
  tutorial-*.md              procedimentos com um objetivo
  report-*.md                relatórios de resultados e de validação
  record-*.md                registros históricos
  handoff-*.md               documentos de contexto entre frentes de trabalho
results/
  runs/                      resultados de cada execução
  repeated/                  resultados agregados das execuções repetidas
  diagnostics/               diagnósticos de acesso à rede de dados
```

---

## Escopo

Este repositório cobre:

- UPF em posição fixa
- rfsim em um único computador, sem rádio, para os experimentos de handover
- USRP X310 com rádio real e UE comercial (uma célula, e handover F1 e N2 distribuído, com um rádio por computador)
- handover F1 intra-gNB (divisão CU/DU)
- handover N2 inter-gNB (topologias monolítica e CU+DU)
- verificação automática de prontidão, medição com ping e iperf, coleta de logs e agregação de resultados

Os próximos marcos do projeto incluem:

- medição automática com UE comercial;
- handover com rádio real;
- aprendizado por reforço profundo (DRL);
- redes neurais em grafos (GNN);
- integração com xApps.
