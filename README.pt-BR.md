# Testbed de handover da OAI em RFsim

> Tradução para o português. O original em inglês é o [README.md](README.md). Em caso de divergência, prevalece o original. Há também uma versão em Linguagem Simples: [README.pt-BR-simples.md](README.pt-BR-simples.md).

Este repositório contém uma automação de nível de pesquisa para experimentos de handover com a OpenAirInterface. Ele suporta dois experimentos de handover no RFsimulator:

| Experimento | Topologia | Disparo | Versão da OAI |
|---|---|---|---|
| Handover F1 | 1 CU + 2 DUs (intra-gNB) | Telnet da CU `ci trigger_f1_ho` | v2.4.0 |
| Handover N2 | 2 gNBs monolíticas **ou** 2 pares CU+DU (inter-gNB) | Telnet da gNB de origem `ci trigger_n2_ho` | v2.4.0 |

Os experimentos de handover compartilham o mesmo 5GC da OAI (AMF, SMF, UPF, oai-ext-dn) e o mesmo UE RFsim.

Também há topologias com rádio real (USRP X310), usando um celular comercial (COTS) como UE:

| Experimento | Topologia | Rádios | UE |
|---|---|---|---|
| USRP célula única | 1 gNB monolítica (`usrp-cots`) | 1 × X310 | Celular COTS |
| Handover F1 com USRP | 1 CU + 2 DUs (distribuído) | 2 × X310 | Celular COTS |
| Handover N2 com USRP | 2 gNBs **ou** 2 pares CU+DU (distribuído) | 2 × X310 | Celular COTS |

As topologias de handover rodam **um rádio por host**. Veja o
[guia USRP X310 + UE COTS](docs/guide-usrp-x310-cots.pt-BR.md) (célula única) e o
[guia de handover com USRP (distribuído)](docs/guide-usrp-distributed-handover.pt-BR.md).

---

## Experimento de handover F1

### Topologia

- 1 5GC da OAI (AMF, SMF, UPF, oai-ext-dn)
- 1 UPF estática
- 1 CU (`192.168.70.150`)
- 2 DUs (`192.168.70.171`, `192.168.70.172`)
- 1 UE RFsim (`192.168.70.181`)
- Handover F1 manual disparado pela interface Telnet da CU

Nomes dos contêineres: `oai-amf`, `oai-smf`, `oai-upf`, `oai-cu`, `oai-du0`, `oai-du1`, `oai-nr-ue`

### Referência

Teste rápido repetido 5 vezes contra o `oai-ext-dn` local (`192.168.71.135`) pela `oaitun_ue1`. As 5 execuções passaram, com 0,0% de perda de pacotes e interrupção média estimada do handover de **207,07 ms**.

Veja [docs/report-baseline-results.pt-BR.md](docs/report-baseline-results.pt-BR.md) para os resultados completos e a interpretação.

### Uso

Inicie o testbed:

```bash
./scripts/up.sh f1
```

Verifique a prontidão:

```bash
./scripts/status.sh
```

Dispare o handover F1 manualmente:

```bash
./scripts/trigger_handover.sh
```

Execute o teste rápido (sobe a pilha, captura o ping durante o handover e grava os resultados):

```bash
./scripts/run_smoke_test.sh f1
```

Ative a medição simultânea com iperf durante o handover:

```bash
IPERF_ENABLED=1 IPERF_MODE=udp ./scripts/run_smoke_test.sh f1
```

Por padrão, o iperf usa como destino o endereço do lado público do oai-ext-dn, `192.168.70.135`, vincula-se ao endereço PDU do UE e registra falhas sem invalidar resultados válidos de ping e de handover. Torne-o obrigatório com `IPERF_REQUIRED=1`.

Execute 5 testes rápidos repetidos e agregue os resultados:

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh f1
```

Ative e agregue o iperf em todas as execuções repetidas:

```bash
RUNS=5 IPERF_ENABLED=1 ./scripts/run_repeated_smoke_tests.sh f1
```

Use um destino na internet como alternativa se o alcance da DN local estiver sob investigação:

```bash
PING_TARGET=8.8.8.8 PING_INTERFACE=oaitun_ue1 ./scripts/run_smoke_test.sh f1
```

Substitua o tempo limite de prontidão do plano de dados do UE:

```bash
UE_DATA_READY_TIMEOUT=180 ./scripts/run_smoke_test.sh f1
```

---

## Experimento de handover N2

**Guia completo: [docs/guide-n2-handover.pt-BR.md](docs/guide-n2-handover.pt-BR.md)**

O handover N2 (inter-gNB, mediado pelo AMF) está disponível na OAI v2.4.0 ou posterior. Há duas topologias:

- **`n2-monolithic` — duas gNBs independentes** (`oai-gnb0` em `192.168.70.160`, `oai-gnb1` em `192.168.70.161`)
- **`n2-cu-du` — dois pares CU+DU** (`oai-cu0`/`oai-du0` e `oai-cu1`/`oai-du1`)

O UE (`192.168.70.181`) atua como servidor RFsim nos dois casos.

### Início rápido

```bash
./scripts/up.sh n2-monolithic          # or n2-cu-du
./scripts/trigger_handover.sh          # auto-detects topology from running containers
```

### Teste rápido automatizado

```bash
./scripts/run_smoke_test.sh n2-monolithic
./scripts/run_smoke_test.sh n2-cu-du
```

### Experimentos repetidos

```bash
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-monolithic
RUNS=5 ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

Por padrão, as execuções N2 repetidas reinicializam a topologia antes de cada tentativa, para que todo handover no mesmo sentido comece na célula de origem. Só desative isso com `RESET_BETWEEN_RUNS=0`.

---

## Experimento com USRP X310 (rádio real)

**Guia completo: [docs/guide-usrp-x310-cots.pt-BR.md](docs/guide-usrp-x310-cots.pt-BR.md)**

Uma única gNB monolítica controla uma USRP X310 por 10GbE; um celular COTS com SIM programado se conecta pelo ar. Não há rfsim, nem modelo de canal, nem contêiner `oai-nr-ue`.

### Início rápido

```bash
./scripts/check_usrp.sh                 # probe the X310 (ping + uhd_usrp_probe)
./scripts/preflight_check.sh usrp-cots  # USRP-aware preflight
./scripts/up.sh usrp-cots               # CN + gNB, waits for NG association to the AMF
./scripts/status.sh                     # gNB NG association + UE registration (from AMF logs)
```

Em seguida, ligue o UE COTS (SIM programado a partir de `oai-cn5g/database/oai_db.sql`) para que ele se conecte. A medição do plano de dados a partir do aparelho é manual (navegador/teste de velocidade); os testes rápidos automatizados funcionam apenas com rfsim.

A X310 exige jumbo frames e buffers de socket grandes no host (`mtu 9000`, `net.core.rmem_max/wmem_max`) — veja o guia.

---

## Handover com USRP X310 (distribuído, rádio real)

**Guia completo: [docs/guide-usrp-distributed-handover.pt-BR.md](docs/guide-usrp-distributed-handover.pt-BR.md)**

As três topologias de handover (F1, N2 monolítica, N2 CU/DU) em rádios X310 reais, **um rádio por host**. Cada DU/gNB roda em seu próprio host com rede do host; as CUs não têm rádio; as configurações ficam em `experiments/usrp_handover/`. Os endereços entre os nós são injetados por host a partir de um `.env`.

```bash
# Core host: make the 5GC reachable from RAN hosts (no CN changes)
sudo ./scripts/usrp_core_routing.sh <core-host-lan-ip>

# Each RAN host: copy the topology .env.example to .env, set LAN IPs, then:
RUN_RADIO_CHECK=1 ./scripts/usrp_site_up.sh n2-monolithic gnb0    # e.g. on the gnb0 host

# Trigger from a control host pointing at the source node's LAN IP:
N2_SOURCE_GNB_TELNET_HOST=<gnb0-lan-ip> ./scripts/trigger_handover.sh n2-monolithic
```

---

## Operações comuns

### Sobrepor overlays do Compose à pilha da RAN

`RAN_COMPOSE_OVERLAY` adiciona arquivos Compose extras depois do arquivo Compose da RAN da topologia, para que um experimento externo possa substituir configurações de serviços sem editar os arquivos Compose deste repositório:

```bash
RAN_COMPOSE_OVERLAY=/path/to/overlay.yml ./scripts/up.sh f1
```

Use uma lista separada por dois-pontos para vários overlays; eles são aplicados da esquerda para a direita, de modo que os arquivos posteriores prevalecem:

```bash
RAN_COMPOSE_OVERLAY=/path/a.yml:/path/b.yml ./scripts/up.sh f1
```

A variável é respeitada por todos os scripts que carregam `scripts/lib.sh`, incluindo `up.sh`, `down.sh` e `preflight_check.sh`. **Passe ao `down.sh` o mesmo valor que você passou ao `up.sh`**, para que a pilha seja derrubada com a mesma configuração mesclada. Um caminho de overlay inexistente falha imediatamente com código de saída 2. O arquivo Compose base sempre fica em primeiro lugar, de modo que o diretório e o nome do projeto Compose não mudam e os caminhos relativos dentro do arquivo base continuam sendo resolvidos.

O uso típico é adicionar opções ao softmodem ou montar uma configuração alternativa. Observe que `USE_ADDITIONAL_OPTIONS` é substituída por inteiro, e não mesclada; por isso, um overlay precisa repetir as opções que deseja manter:

```yaml
services:
    du0:
        environment:
            USE_ADDITIONAL_OPTIONS: --rfsim
                                    --log_config.global_log_options level,nocolor,time
                                    --rfsimulator.[0].serveraddr 192.168.70.181
                                    --rfsimulator.[0].options chanmod
```

A ordem de subida continua importando, e é por isso que se deve usar o `up.sh` em vez de um simples `docker compose up -d`: o UE roda como servidor RFsim e não pode ser reiniciado no lugar enquanto as DUs continuam rodando, ou ele nunca restabelece o plano de dados.

### Parar o testbed

Detecta automaticamente a topologia em execução:

```bash
./scripts/down.sh
```

Ou especifique a topologia explicitamente:

```bash
./scripts/down.sh f1
./scripts/down.sh n2-monolithic
./scripts/down.sh n2-cu-du
./scripts/down.sh usrp-cots
```

Passe `--volumes` para apagar também os volumes gerenciados pelo Compose (destrutivo — remove o banco de dados de assinantes):

```bash
./scripts/down.sh --volumes
```

### Coletar logs

```bash
./scripts/collect_logs.sh
./scripts/collect_logs.sh --run-dir results/runs/<run_id>
```

### Diagnóstico de alcance da DN

```bash
./scripts/diagnose_dn_reachability.sh
```

Grava o estado das redes Docker, rotas, sondas de ping, regras de firewall e um resumo em `results/diagnostics/`. Não modifica nenhuma configuração.

Documentação:

- [Mapa da documentação e trilhas de leitura obrigatória](docs/README.pt-BR.md)
- [Tutorial de handover F1](docs/tutorial-f1-handover.pt-BR.md)
- [Tutorial de handover N2 monolítico](docs/tutorial-n2-monolithic-handover.pt-BR.md)
- [Tutorial de handover N2 CU/DU](docs/tutorial-n2-cu-du-handover.pt-BR.md)
- [Guia USRP X310 + UE COTS](docs/guide-usrp-x310-cots.pt-BR.md)
- [Guia de handover com USRP (distribuído)](docs/guide-usrp-distributed-handover.pt-BR.md)
- [Conjunto validado de experimentos nas três topologias](results/validated/2026-06-19/README.pt-BR.md)

### Medição opcional com iperf3 avulso

Verifique o suporte:

```bash
./scripts/check_iperf_support.sh
```

Execute um teste UDP do `oai-nr-ue` para o `oai-ext-dn`:

```bash
IPERF_MODE=udp IPERF_DURATION=10 ./scripts/run_iperf_test.sh
```

---

## Modos de falha conhecidos e intervenções

Execute `./scripts/preflight_check.sh` antes de iniciar — ele detecta automaticamente os problemas listados abaixo e informa `[PASS]`, `[WARN]` ou `[FAIL]` para cada um. Execute `./scripts/poststart_check.sh` depois de iniciar para verificar se o testbed está saudável.

Para pular o preflight em situações pontuais, quando você sabe que o ambiente está correto:

```bash
SKIP_PREFLIGHT=1 ./scripts/up.sh
```

### Referência de problemas

| Falha | Sintoma | Intervenção |
|---|---|---|
| **Exit node do Tailscale sem acesso à LAN**, *ou* **rota via tailscale0** | `nc/Telnet` para 192.168.70.x falha | `sudo tailscale set --exit-node-allow-lan-access=true`, desative o exit node ou `sudo tailscale down` |
| **WireGuard ativo** | Tráfego para 192.168.70.x desviado | Desconecte o WireGuard (`wg-quick down <iface>`) |
| **OpenVPN / outra VPN TUN** | Igual ao WireGuard | Desconecte a VPN |
| **Contêineres antigos** | Nome de contêiner já em uso ao iniciar | `docker rm -f <nomes>` |
| **Rede Docker do CN ausente** | O preflight informa que o Compose vai criá-la | Execute `./scripts/up.sh`; não crie redes compartilhadas manualmente |
| **Rede Docker do CN incompatível** | O preflight informa sub-rede ou propriedade incorretas | Pare os contêineres conectados, remova a rede incompatível e execute `./scripts/up.sh` novamente |
| **Conflito de sub-rede** | Tráfego desviado silenciosamente | Remova/reconfigure a interface ou rota conflitante |
| **/dev/net/tun ausente** | A `oaitun_ue1` nunca aparece; tempo limite do plano de dados | `sudo modprobe tun` |
| **SCTP não carregado** | O NG Setup do AMF nunca termina | `sudo modprobe sctp` |
| **Porta 9090 ou 4043 ocupada** | Telnet inalcançável / rfsim não conecta | Encerre o processo que ocupa a porta ou faça `docker rm -f` no contêiner zumbi |
| **iptables FORWARD DROP** | O UE não alcança o oai-ext-dn | Verifique a cadeia FORWARD; garanta que as regras do Docker não sejam sobrescritas |
| **AppArmor bloqueando NET_ADMIN** | `oaitun_ue1` ausente, sem erro visível | Verifique `dmesg \| grep apparmor`; ajuste o perfil |
| **Relógio fora de sincronia** | Falhas de autenticação NAS | `sudo systemctl restart systemd-timesyncd` |
| **Imagens não baixadas** | Início lento ou falha no download na primeira execução | `docker pull oaisoftwarealliance/oai-gnb:develop && docker pull oaisoftwarealliance/oai-nr-ue:develop` |
| **Pouco espaço em disco** | A coleta de logs ou a gravação de resultados falha silenciosamente | Limpe execuções antigas em `results/runs/` e `results/repeated/` |

---

## Estrutura do repositório

```
experiments/
  manual_f1_handover/        F1 handover experiment config
  n2_handover/               N2 handover experiment config
    config.yaml
    topology_a_monolithic/   Two monolithic gNBs
    topology_b_cu_du/        Two CU+DU pairs
  usrp_x310/                 USRP X310 real-radio gNB, single cell (COTS UE)
    config.yaml
    conf-gnb-usrp.conf
    gnb-docker-compose.yaml
  usrp_handover/             USRP X310 handover, distributed (one radio per host)
    f1/                      CU + 2 DUs (per-host compose, confs, .env.example)
    n2_monolithic/           2 gNBs
    n2_cu_du/                2 CU+DU pairs
scripts/
  up.sh / down.sh / restart.sh / status.sh  (accept topology: f1, n2-monolithic, n2-cu-du, usrp-cots)
  wait_ready.sh / wait_ue_data_ready.sh
  trigger_handover.sh        Handover trigger (all topologies; auto-detects if no arg)
  run_smoke_test.sh          Smoke test (all topologies)
  run_repeated_smoke_tests.sh
  preflight_check.sh / poststart_check.sh
  start_ping_capture.sh / collect_logs.sh
  run_iperf_test.sh / check_iperf_support.sh
  check_usrp.sh              USRP X310 device probe (ping + uhd_usrp_probe)
  usrp_core_routing.sh       Make the 5GC reachable from distributed RAN hosts
  usrp_site_up.sh / usrp_site_down.sh  Per-host launcher for distributed USRP roles
  diagnose_dn_reachability.sh
  lib.sh                     Shared helpers (apply_topology, detect_topology, ...)
conf-cu.conf                 F1 CU configuration
conf-du.conf                 F1 DU base configuration
conf-nr-ue.conf              UE configuration (shared by all experiments)
oai-cn5g/                   5GC Docker Compose and configuration
tools/
  parse_ping.py
  parse_iperf.py
docs/
  README.md                  Reading paths and documentation index
  foundation-fNN-*.md       Stable foundational concepts and rules
  guide-*.md                Broad operational guides
  tutorial-*.md             Goal-oriented procedures
  report-*.md               Results and validation reports
  record-*.md               Historical records
  handoff-*.md              Cross-effort context documents
results/
  runs/                      Per-run results
  repeated/                  Aggregated repeated-run results
  diagnostics/               DN reachability diagnostic runs
```

---

## Escopo

Este repositório abrange:

- Posicionamento estático da UPF
- Operação no RFsimulator (um único host, sem hardware de RF) para os experimentos de handover
- Operação com rádio real USRP X310 e UE COTS (célula única e handover F1/N2 distribuído — um rádio por host)
- Handover F1 intra-gNB (divisão CU/DU)
- Handover N2 inter-gNB (topologias monolítica e CU+DU)
- Verificações automatizadas de prontidão, medição com ping/iperf, coleta de logs e agregação de resultados

Medição automatizada a partir de um UE COTS, handover em rádio real, DRL, GNN e integração com xApp estão planejados para marcos futuros.
