# Tutorial: handover N2 em rfsim com gNBs monolíticas

> Tradução para o português em Linguagem Simples. O original em inglês é o [tutorial-n2-monolithic-handover.md](../en/tutorial-n2-monolithic-handover.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** tutorial
>
> **Leitura prévia:** [guia do handover N2](guide-n2-handover.pt-BR-simples.md) e [guia do pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md)

Com este tutorial, você executa um handover N2 (inter-gNB) entre duas gNBs monolíticas. Durante o handover, o UE envia ping e tráfego iperf em UDP.

## Topologia

- gNB de origem: `oai-gnb0`, em `192.168.70.160`, PCI 0
- gNB de destino: `oai-gnb1`, em `192.168.70.161`, PCI 1
- UE: `oai-nr-ue`, com endereço `10.0.0.2` na sessão PDU
- comando de handover, coordenado pelo AMF: `ci trigger_n2_ho 1,1`
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

Cada gNB tem as funções de CU e de DU no mesmo processo. As duas gNBs se registram no AMF de forma independente.

## Pré-requisitos

Execute na pasta raiz do repositório:

```bash
./scripts/preflight_check.sh n2-monolithic
```

A topologia depende das configurações de compatibilidade com o rfsim deste repositório:

- o UE é o servidor do rfsim;
- as duas gNBs se conectam a `192.168.70.181:4043`;
- a janela de resposta do acesso aleatório está ajustada para os tempos do rfsim.

## Executar um experimento automático do zero

1. Derrube qualquer topologia ativa:

   ```bash
   ./scripts/down.sh n2-monolithic
   ```

2. Execute o teste rápido com o iperf obrigatório:

   ```bash
   IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-monolithic
   ```

O script espera a sessão PDU do UE e inicia o ping e o iperf. Depois, ele envia o comando de handover N2 para a `oai-gnb0`.

No final, uma execução bem-sucedida mostra a pasta de resultados. Exemplo:

```text
results/runs/20260619_152343_n2_monolithic_smoke
```

## Conferir o resultado

```bash
RUN_DIR=results/runs/<id-da-execução>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-gnb0.log"
rg "Handover Request Acknowledge|CFRA procedure succeeded|in-sync"   "$RUN_DIR/docker_logs/oai-gnb1.log"
```

O log da `oai-gnb1` de destino deve mostrar três coisas:

- a criação do contexto do UE no destino;
- o acesso aleatório sem disputa (CFRA) concluído;
- tráfego sincronizado (`in-sync`) depois do handover.

Essa evidência é mais forte que o simples envio do comando.

A execução de referência validada em 19/06/2026 teve estes resultados:

- 1,538% de perda de ping;
- cerca de 199 ms de interrupção estimada;
- cerca de 1,049 Mbit/s de vazão UDP;
- 0% de perda UDP.

## Modo manual

```bash
./scripts/up.sh n2-monolithic
./scripts/status.sh n2-monolithic
echo ue | nc -N 192.168.70.160 9090
./scripts/trigger_handover.sh n2-monolithic
./scripts/status.sh n2-monolithic
```

Por padrão, o comando supõe o PCI de destino 1 e o identificador RRC 1 do UE na origem. Se precisar, informe outros valores:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-monolithic
```

## Execuções repetidas

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

No N2, as execuções repetidas recriam a topologia antes de cada execução, por padrão. Isso é necessário porque cada comando leva o UE da gNB de origem para a gNB de destino. Só use `RESET_BETWEEN_RUNS=0` se outro mecanismo devolver o UE à célula de origem.

## Limpeza

```bash
./scripts/down.sh n2-monolithic
```
