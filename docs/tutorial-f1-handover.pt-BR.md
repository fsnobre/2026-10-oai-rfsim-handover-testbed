# Tutorial de handover F1 em RFsim

> Tradução para o português. O original em inglês é o [tutorial-f1-handover.md](tutorial-f1-handover.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Tutorial
>
> **Leitura obrigatória:** [F00](foundation-f00-docker-network-ownership.pt-BR.md), [F01](foundation-f01-functional-readiness-model.pt-BR.md), [F02](foundation-f02-dn-reachability.pt-BR.md), [F03](foundation-f03-rfsim-multicell-operations.pt-BR.md), [F04](foundation-f04-oai-config-enums-and-timing.pt-BR.md) e o [guia do pipeline de medição](guide-measurement-pipeline.pt-BR.md)

Este tutorial executa um handover F1 intra-gNB da DU0 para a DU1, medindo a continuidade do plano de usuário com ping e iperf UDP.

## Topologia

- CU: `oai-cu` em `192.168.70.150`
- célula de origem: `oai-du0`, PCI 0
- célula de destino: `oai-du1`, PCI 1
- UE: `oai-nr-ue`, endereço PDU `10.0.0.2`
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

A CU controla as duas DUs; por isso, o handover é disparado pela interface Telnet da CU com `ci trigger_f1_ho`.

## Pré-requisitos

Execute a partir da raiz do repositório. É preciso ter Docker, Docker Compose v2, suporte a SCTP, `/dev/net/tun`, `nc` e Python 3.

```bash
./scripts/preflight_check.sh f1
```

Avisos sobre o Tailscale são apenas informativos, a menos que a rota para `192.168.70.150` seja afetada.

## Executar um experimento automatizado limpo

Pare qualquer topologia existente e, em seguida, execute o experimento de teste rápido com iperf obrigatório:

```bash
./scripts/down.sh f1
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh f1
```

O script inicia o núcleo, a CU, a DU de origem, o UE e a DU de destino numa ordem que respeita a prontidão. Depois, inicia o ping e o iperf antes de enviar o comando de handover.

Uma execução bem-sucedida imprime seu diretório de resultados, por exemplo:

```text
results/runs/20260619_145515_f1_handover_smoke
```

## Verificar o resultado

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "HO acknowledged|handover .* complete" "$RUN_DIR/docker_logs/cu.log"
```

O sucesso exige:

- `status: pass`
- `handover_triggered: true`
- `ping_metrics_valid: true`
- `iperf_status: pass`
- evidência no log da CU de que o handover foi concluído

A execução de referência validada em 19 de junho de 2026 registrou 0% de perda de ping, cerca de 202 ms de interrupção estimada, cerca de 1,049 Mbps de vazão UDP e 0% de perda UDP.

## Fluxo manual

Para inspeção interativa:

```bash
./scripts/up.sh f1
./scripts/status.sh f1
./scripts/trigger_handover.sh f1
./scripts/status.sh f1
```

Consulte a CU diretamente ao investigar problemas:

```bash
echo ue | nc -N 192.168.70.150 9090
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090
```

## Experimentos repetidos

Use reinicializações da topologia ao comparar tentativas independentes a partir de partida a frio:

```bash
RUNS=5 RESET_BETWEEN_RUNS=1 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh f1
```

O agregado é gravado em `results/repeated/`. Sem reinicialização, as execuções F1 posteriores podem começar a partir de uma DU servidora diferente da usada na primeira execução.

## Limpeza

```bash
./scripts/down.sh f1
```

Use `--volumes` somente quando o estado persistido do núcleo também deve ser removido.
