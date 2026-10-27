# Tutorial de handover N2 CU/DU em RFsim

> Tradução para o português. O original em inglês é o [tutorial-n2-cu-du-handover.md](../en/tutorial-n2-cu-du-handover.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Tutorial
>
> **Leitura obrigatória:** [guia de handover N2](guide-n2-handover.pt-BR.md) e o [guia do pipeline de medição](guide-measurement-pipeline.pt-BR.md)

Este tutorial executa um handover N2 inter-gNB entre duas gNBs divididas em CU/DU, medindo a continuidade do plano de usuário com ping e iperf UDP.

## Topologia

- CU de origem: `oai-cu0` em `192.168.70.150`
- DU de origem: `oai-du0` em `192.168.70.171`, PCI 0
- CU de destino: `oai-cu1` em `192.168.70.155`
- DU de destino: `oai-du1` em `192.168.70.172`, PCI 1
- UE: `oai-nr-ue`, endereço PDU `10.0.0.2`
- comando de handover mediado pelo AMF: `ci trigger_n2_ho 1,1`
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

O comando é enviado à `oai-cu0` de origem. O AMF coordena o handover para a `oai-cu1`, e o UE realiza o acesso aleatório livre de contenção pela `oai-du1` de destino.

## Pré-requisitos

```bash
./scripts/preflight_check.sh n2-cu-du
```

Os dois pares CU/DU precisam estabelecer a F1 antes do handover. As DUs se conectam ao servidor RFsim do UE em `192.168.70.181:4043`.

## Executar um experimento automatizado limpo

```bash
./scripts/down.sh n2-cu-du
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-cu-du
```

Uma execução bem-sucedida imprime um diretório como:

```text
results/runs/20260619_152628_n2_cu_du_smoke
```

## Verificar o resultado

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-cu0.log"
rg "Handover Request Acknowledge|Handover triggered"   "$RUN_DIR/docker_logs/oai-cu1.log"
rg "CFRA procedure succeeded|in-sync|goodput"   "$RUN_DIR/docker_logs/oai-du1.log"
```

A CU de destino confirma a alocação de recursos N2, e a DU de destino confirma o acesso aleatório bem-sucedido na célula de destino e o tráfego após o handover.

A execução de referência validada em 19 de junho de 2026 registrou 1,538% de perda de ping, cerca de 209 ms de interrupção estimada, cerca de 1,049 Mbps de vazão UDP e 0% de perda UDP.

## Fluxo manual

```bash
./scripts/up.sh n2-cu-du
./scripts/status.sh n2-cu-du
echo ue | nc -N 192.168.70.150 9090
./scripts/trigger_handover.sh n2-cu-du
./scripts/status.sh n2-cu-du
```

Substitua a PCI de destino ou o ID RRC do UE quando a CU de origem informar valores diferentes:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-cu-du
```

## Experimentos repetidos

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

Por padrão, os testes N2 repetidos reinicializam a topologia completa antes de cada tentativa, para que toda execução comece com o UE na `oai-du0`. Use `RESET_BETWEEN_RUNS=0` somente se o experimento realizar explicitamente um handover reverso.

## Limpeza

```bash
./scripts/down.sh n2-cu-du
```
