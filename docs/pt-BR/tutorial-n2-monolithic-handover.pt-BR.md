# Tutorial de handover N2 monolítico em RFsim

> Tradução para o português. O original em inglês é o [tutorial-n2-monolithic-handover.md](../en/tutorial-n2-monolithic-handover.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Tutorial
>
> **Leitura obrigatória:** [guia de handover N2](guide-n2-handover.pt-BR.md) e o [guia do pipeline de medição](guide-measurement-pipeline.pt-BR.md)

Este tutorial executa um handover N2 inter-gNB entre duas gNBs monolíticas enquanto o ping e o iperf UDP atravessam o intervalo do handover.

## Topologia

- gNB de origem: `oai-gnb0` em `192.168.70.160`, PCI 0
- gNB de destino: `oai-gnb1` em `192.168.70.161`, PCI 1
- UE: `oai-nr-ue`, endereço PDU `10.0.0.2`
- comando de handover mediado pelo AMF: `ci trigger_n2_ho 1,1`
- destino do ping: `192.168.71.135`
- destino do iperf: `192.168.70.135`

Cada gNB contém suas funções de CU e DU. As duas gNBs se registram de forma independente no AMF.

## Pré-requisitos

Execute a partir da raiz do repositório:

```bash
./scripts/preflight_check.sh n2-monolithic
```

A topologia atual depende das configurações de compatibilidade com o RFsim deste repositório: o UE é o servidor RFsim, as duas gNBs se conectam a `192.168.70.181:4043` e a janela de resposta do acesso aleatório está configurada para a temporização do RFsim.

## Executar um experimento automatizado limpo

```bash
./scripts/down.sh n2-monolithic
IPERF_ENABLED=1 IPERF_REQUIRED=1 IPERF_MODE=udp   ./scripts/run_smoke_test.sh n2-monolithic
```

O script aguarda a sessão PDU do UE, inicia o ping e o iperf e, em seguida, envia o disparo N2 para a `oai-gnb0`.

Uma execução bem-sucedida imprime um diretório como:

```text
results/runs/20260619_152343_n2_monolithic_smoke
```

## Verificar o resultado

```bash
RUN_DIR=results/runs/<run-id>
python3 -m json.tool "$RUN_DIR/summary.json"
cat "$RUN_DIR/events.csv"
rg "Handover Required|Received NG Handover Command"   "$RUN_DIR/docker_logs/oai-gnb0.log"
rg "Handover Request Acknowledge|CFRA procedure succeeded|in-sync"   "$RUN_DIR/docker_logs/oai-gnb1.log"
```

O log da `oai-gnb1` de destino deve mostrar a alocação do contexto no destino, o acesso aleatório livre de contenção bem-sucedido e o tráfego em sincronia (*in-sync*) após o handover. Essa é uma evidência mais forte do que apenas o envio do comando.

A execução de referência validada em 19 de junho de 2026 registrou 1,538% de perda de ping, cerca de 199 ms de interrupção estimada, cerca de 1,049 Mbps de vazão UDP e 0% de perda UDP.

## Fluxo manual

```bash
./scripts/up.sh n2-monolithic
./scripts/status.sh n2-monolithic
echo ue | nc -N 192.168.70.160 9090
./scripts/trigger_handover.sh n2-monolithic
./scripts/status.sh n2-monolithic
```

O disparo padrão pressupõe PCI de destino 1 e ID RRC do UE na origem igual a 1. Substitua esses valores quando necessário:

```bash
N2_TARGET_PCI=1 N2_UE_RRC_ID=1   ./scripts/trigger_handover.sh n2-monolithic
```

## Experimentos repetidos

```bash
RUNS=5 IPERF_ENABLED=1 IPERF_REQUIRED=1   ./scripts/run_repeated_smoke_tests.sh n2-monolithic
```

Por padrão, os testes N2 repetidos reinicializam a topologia antes de cada execução. Isso é necessário porque cada disparo configurado move o UE da gNB de origem para a gNB de destino. Defina `RESET_BETWEEN_RUNS=0` somente quando outro mecanismo devolver o UE à célula de origem.

## Limpeza

```bash
./scripts/down.sh n2-monolithic
```
