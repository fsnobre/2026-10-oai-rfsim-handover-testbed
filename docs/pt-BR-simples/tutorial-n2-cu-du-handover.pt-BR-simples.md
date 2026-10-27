# Tutorial: handover N2 em rfsim com pares CU/DU

> Tradução para o português em Linguagem Simples. O original em inglês é o [tutorial-n2-cu-du-handover.md](../en/tutorial-n2-cu-du-handover.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** tutorial
>
> **Leitura prévia:** [guia do handover N2](guide-n2-handover.pt-BR-simples.md) e [guia do pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md)

Com este tutorial, você executa um handover N2 (inter-gNB) entre duas gNBs divididas em CU e DU. Ao mesmo tempo, você mede a continuidade do plano de usuário com ping e com iperf em UDP.

## Topologia

- CU de origem: `oai-cu0`, em `192.168.70.150`
- DU de origem: `oai-du0`, em `192.168.70.171`, PCI 0
- CU de destino: `oai-cu1`, em `192.168.70.155`
- DU de destino: `oai-du1`, em `192.168.70.172`, PCI 1
- UE: `oai-nr-ue`, com endereço `10.0.0.2` na sessão PDU
- comando de handover, coordenado pelo AMF: `ci trigger_n2_ho 1,1`
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

O comando vai para a `oai-cu0` de origem. O AMF coordena o handover para a `oai-cu1`. O UE faz o acesso aleatório sem disputa pela `oai-du1` de destino.

## Pré-requisitos

```bash
./scripts/preflight_check.sh n2-cu-du
```

Antes do handover, os dois pares CU/DU devem abrir a conexão F1. As DUs se conectam ao servidor rfsim no UE, em `192.168.70.181:4043`.

## Executar um experimento automático do zero

1. Derrube qualquer topologia ativa:

   ```bash
   ./scripts/down.sh n2-cu-du
   ```

2. Execute o teste rápido com o iperf obrigatório:

   ```bash
   IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-cu-du
   ```

No final, uma execução bem-sucedida mostra a pasta de resultados. Exemplo:

```text
results/runs/20260619_152628_n2_cu_du_smoke
```

## Conferir o resultado

```bash
RUN_DIR=results/runs/<id-da-execução>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-cu0.log"
rg "Handover Request Acknowledge|Handover triggered"   "$RUN_DIR/docker_logs/oai-cu1.log"
rg "CFRA procedure succeeded|in-sync|goodput"   "$RUN_DIR/docker_logs/oai-du1.log"
```

A CU de destino confirma a reserva de recursos do N2. A DU de destino confirma o acesso aleatório na célula de destino e o tráfego depois do handover.

A execução de referência validada em 19/06/2026 teve estes resultados:

- 1,538% de perda de ping;
- cerca de 209 ms de interrupção estimada;
- cerca de 1,049 Mbit/s de vazão UDP;
- 0% de perda UDP.

## Modo manual

```bash
./scripts/up.sh n2-cu-du
./scripts/status.sh n2-cu-du
echo ue | nc -N 192.168.70.150 9090
./scripts/trigger_handover.sh n2-cu-du
./scripts/status.sh n2-cu-du
```

Se a CU de origem mostrar outro PCI de destino ou outro identificador RRC do UE, informe-os:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-cu-du
```

## Execuções repetidas

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-cu-du
```

No N2, as execuções repetidas recriam a topologia inteira antes de cada execução, por padrão. Assim, toda execução começa com o UE na `oai-du0`. Só use `RESET_BETWEEN_RUNS=0` se o experimento fizer o handover de volta.

## Limpeza

```bash
./scripts/down.sh n2-cu-du
```
