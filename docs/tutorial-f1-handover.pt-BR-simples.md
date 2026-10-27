# Tutorial: handover F1 em rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [tutorial-f1-handover.md](tutorial-f1-handover.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** tutorial
>
> **Leitura prévia:** [F00](foundation-f00-docker-network-ownership.pt-BR-simples.md), [F01](foundation-f01-functional-readiness-model.pt-BR-simples.md), [F02](foundation-f02-dn-reachability.pt-BR-simples.md), [F03](foundation-f03-rfsim-multicell-operations.pt-BR-simples.md), [F04](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md) e o [guia do pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md)

Com este tutorial, você executa um handover F1 (intra-gNB) da DU0 para a DU1. Ao mesmo tempo, você mede a continuidade do plano de usuário com ping e com iperf em UDP.

## Topologia

- CU: `oai-cu`, em `192.168.70.150`
- célula de origem: `oai-du0`, PCI 0
- célula de destino: `oai-du1`, PCI 1
- UE: `oai-nr-ue`, com endereço `10.0.0.2` na sessão PDU
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

A CU controla as duas DUs. Por isso, o comando de handover vai para a interface Telnet da CU: `ci trigger_f1_ho`.

## Pré-requisitos

Execute os comandos na pasta raiz do repositório. O computador precisa ter Docker, Docker Compose v2, SCTP, `/dev/net/tun`, `nc` e Python 3.

```bash
./scripts/preflight_check.sh f1
```

Os avisos sobre o Tailscale só informam. Eles só importam se afetarem a rota para `192.168.70.150`.

## Executar um experimento automático do zero

1. Derrube qualquer topologia ativa:

   ```bash
   ./scripts/down.sh f1
   ```

2. Execute o teste rápido com o iperf obrigatório:

   ```bash
   IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh f1
   ```

O script sobe o núcleo 5G, a CU, a DU de origem, o UE e a DU de destino, nessa ordem segura. Depois, ele inicia o ping e o iperf. Só então ele envia o comando de handover.

No final, uma execução bem-sucedida mostra a pasta de resultados. Exemplo:

```text
results/runs/20260619_145515_f1_handover_smoke
```

## Conferir o resultado

```bash
RUN_DIR=results/runs/<id-da-execução>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "HO acknowledged|handover .* complete" "$RUN_DIR/docker_logs/cu.log"
```

A execução deu certo quando:

- `status` é `pass`;
- `handover_triggered` é `true`;
- `ping_metrics_valid` é `true`;
- `iperf_status` é `pass`;
- o log da CU mostra que o handover terminou.

A execução de referência validada em 19/06/2026 teve estes resultados:

- 0% de perda de ping;
- cerca de 202 ms de interrupção estimada;
- cerca de 1,049 Mbit/s de vazão UDP;
- 0% de perda UDP.

## Modo manual

Para acompanhar cada etapa:

```bash
./scripts/up.sh f1
./scripts/status.sh f1
./scripts/trigger_handover.sh f1
./scripts/status.sh f1
```

Para investigar um problema, consulte a CU diretamente:

```bash
echo ue | nc -N 192.168.70.150 9090
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090
```

## Execuções repetidas

Para comparar execuções independentes com partida a frio, recrie a topologia entre elas:

```bash
RUNS=5 RESET_BETWEEN_RUNS=1 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh f1
```

O resumo fica em `results/repeated/`. Sem recriar a topologia, as execuções seguintes do F1 podem começar com o UE em outra DU.

## Limpeza

```bash
./scripts/down.sh f1
```

Só use `--volumes` se quiser apagar também os dados guardados do núcleo 5G.
