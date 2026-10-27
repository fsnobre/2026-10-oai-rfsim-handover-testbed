# Conjunto validado de experimentos nas três topologias

> Tradução para o português em Linguagem Simples. O original em inglês é o [README.md](README.md). Se houver diferença entre os dois, vale o original.

Data: 19/06/2026

Estes são experimentos de referência, com uma execução por topologia e partida a frio. Eles cobrem as três topologias de handover em rfsim do testbed. Eles validam a automação e servem de exemplos que podem ser reproduzidos. Eles não são um resultado de referência de desempenho com valor estatístico.

Todas as execuções usaram:

```text
IPERF_ENABLED=1
IPERF_REQUIRED=1
IPERF_MODE=udp
IPERF_DURATION=10
PING_INTERVAL=0.2
PING_POST_HANDOVER_SECONDS=10
```

## Resultados

| Topologia | ID da execução | Perda de ping | Interrupção estimada | Primeiro ping depois do comando | Vazão UDP | Jitter UDP | Perda UDP |
|---|---|---:|---:|---:|---:|---:|---:|
| F1, CU e 2 DUs | `20260619_145515_f1_handover_smoke` | 0,000% | 202,072 ms | 20,664 ms | 1,049 Mbit/s | 5,932 ms | 0,000% |
| N2 monolítica | `20260619_152343_n2_monolithic_smoke` | 1,538% | 198,860 ms | 0,145 ms | 1,049 Mbit/s | 7,154 ms | 0,000% |
| N2 CU/DU | `20260619_152628_n2_cu_du_smoke` | 1,538% | 208,574 ms | 77,762 ms | 1,049 Mbit/s | 7,725 ms | 0,000% |

Todas as execuções passaram nas validações obrigatórias de ping e de iperf. O cliente iperf usou como origem o endereço da sessão PDU do UE, na `oaitun_ue1`.

## Evidências do handover

- **F1:** a CU registrou a confirmação do handover, a conclusão da reconfiguração RRC e a mensagem `handover ... complete`.
- **N2 monolítica:** a `gnb0` enviou o Handover Required e recebeu o NG Handover Command. A `gnb1` confirmou o pedido, concluiu o acesso aleatório sem disputa (CFRA) e transportou tráfego sincronizado.
- **N2 CU/DU:** a `cu0` enviou o Handover Required e recebeu o NG Handover Command. A `cu1` confirmou a reserva no destino. A `du1` concluiu o CFRA e transportou tráfego sincronizado.

## Arquivos guardados

A pasta de cada topologia tem:

- `summary.json`: resultado geral do teste rápido e das métricas;
- `ping_summary.json`: métricas de ping;
- `iperf_summary.json`: métricas UDP;
- `events.csv`: linha do tempo do experimento.

Os logs completos ficam nas pastas locais `results/runs/<id-da-execução>/`, que o git ignora. Os arquivos guardados aqui deixam de fora, de propósito, os logs grandes e próprios de cada computador.

## Interpretação

Os valores de interrupção parecidos servem como referência de funcionamento. Mas uma execução por topologia não permite ordenar as topologias. Um estudo comparativo de desempenho deve usar:

- várias execuções com partida a frio;
- carga fixa no computador;
- imagens fixadas pelo identificador (*digest*);
- intervalos de confiança.
