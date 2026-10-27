# Conjunto validado de experimentos nas três topologias

> Tradução para o português. O original em inglês é o [README.md](README.md). Em caso de divergência, prevalece o original.

Data: 19 de junho de 2026

Estes são experimentos de referência de execução única, a partir de partida a frio, para as três topologias de handover em RFsim suportadas. Eles validam a automação e fornecem exemplos reproduzíveis; não constituem uma referência de desempenho estatisticamente representativa.

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

| Topologia | ID da execução | Perda de ping | Interrupção estimada | Primeiro ping após o disparo | Vazão UDP | Jitter UDP | Perda UDP |
|---|---|---:|---:|---:|---:|---:|---:|
| F1 CU + 2 DUs | `20260619_145515_f1_handover_smoke` | 0,000% | 202,072 ms | 20,664 ms | 1,049 Mbps | 5,932 ms | 0,000% |
| N2 monolítica | `20260619_152343_n2_monolithic_smoke` | 1,538% | 198,860 ms | 0,145 ms | 1,049 Mbps | 7,154 ms | 0,000% |
| N2 CU/DU | `20260619_152628_n2_cu_du_smoke` | 1,538% | 208,574 ms | 77,762 ms | 1,049 Mbps | 7,725 ms | 0,000% |

Todas as execuções passaram nas validações obrigatórias de ping e iperf. O cliente iperf estava vinculado ao endereço PDU do UE na `oaitun_ue1`.

## Evidências do handover

- F1: a CU relatou a confirmação do handover, a conclusão da reconfiguração RRC e `handover ... complete`.
- N2 monolítica: a `gnb0` enviou o Handover Required e recebeu o NG Handover Command; a `gnb1` confirmou a solicitação, concluiu o CFRA e transportou tráfego em sincronia.
- N2 CU/DU: a `cu0` enviou o Handover Required e recebeu o NG Handover Command; a `cu1` confirmou a alocação no destino; a `du1` concluiu o CFRA e transportou tráfego em sincronia.

## Artefatos preservados

Cada diretório de topologia contém:

- `summary.json`: resultado geral do teste rápido e das métricas
- `ping_summary.json`: métricas de ping processadas
- `iperf_summary.json`: métricas UDP processadas
- `events.csv`: linha do tempo do experimento

Os logs brutos completos permanecem nos diretórios locais `results/runs/<run-id>/`, ignorados pelo git. Os arquivos preservados omitem intencionalmente os logs volumosos específicos do host.

## Interpretação

Os valores de interrupção semelhantes são úteis como referência funcional, mas nenhuma classificação deve ser inferida a partir de uma única execução por topologia. Um estudo comparativo de desempenho deve usar tentativas repetidas a partir de partida a frio, carga do host fixa, digests das imagens e intervalos de confiança.
