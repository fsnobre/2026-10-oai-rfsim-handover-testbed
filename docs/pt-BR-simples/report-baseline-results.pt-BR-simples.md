# Resultado de referência

> Tradução para o português em Linguagem Simples. O original em inglês é o [report-baseline-results.md](../en/report-baseline-results.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** relatório
>
> **Contexto:** [tutorial de handover F1 em rfsim](tutorial-f1-handover.pt-BR-simples.md) e [guia do pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md)

Este documento registra o primeiro resultado de referência validado do testbed de handover F1 em rfsim. Esse resultado usou só ping. Ele é anterior à medição com iperf. Os números publicados não mudaram, para permitir comparações.

## Topologia do experimento

- 1 OAI NR-UE em rfsim: `oai-nr-ue`
- 2 DUs: `oai-du0` e `oai-du1`
- 1 CU: `oai-cu`
- 1 plano de controle do núcleo 5G da OAI
- 1 UPF fixo: `oai-upf`
- 1 ponto local da rede de dados: `oai-ext-dn`

O destino local do plano de usuário é o `oai-ext-dn`, em `192.168.71.135`. O UE envia o tráfego de medição pela interface da sessão PDU, `oaitun_ue1`.

## Como o testbed sobe e faz o handover

O testbed sobe com o script de automação:

```bash
./scripts/up.sh
```

O script espera o núcleo 5G, a CU, a DU e o UE ficarem prontos. Só então os testes rápidos começam. O teste rápido espera o plano de usuário do UE alcançar o destino do ping.

O comando de handover validado continua sendo o comando Telnet na CU:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

O teste rápido envia esse comando por meio deste script:

```bash
./scripts/trigger_handover.sh
```

## Método de medição

Este resultado de referência usa o ping (ICMP) para medir a continuidade durante o handover. As cinco execuções históricas não usaram iperf.

- destino: `192.168.71.135`
- contêiner de destino: `oai-ext-dn`
- interface do UE: `oaitun_ue1`
- número de execuções: `RUNS=5`
- comando de handover: Telnet na CU, `ci trigger_f1_ho`

Em cada execução, o ping começa antes do handover, continua durante o handover e segue por pouco tempo depois dele. O analisador estima a interrupção pelos horários das respostas de ping em torno do comando de handover.

## Resultados das execuções repetidas

| Execuções | Aprovadas | Perda de pacotes | Interrupção média | Desvio-padrão | Interrupção mínima | Interrupção máxima | Média do primeiro ping depois do handover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 5 | 0,0% | 207,0664 ms | 22,3375 ms | 170,576 ms | 238,949 ms | 93,309 ms |

## Resumo

- Execuções repetidas: `RUNS=5`
- Execuções aprovadas: `5/5`
- Perda de pacotes: `0,0%`
- Interrupção estimada média: `207,0664 ms`
- Desvio-padrão da interrupção estimada: `22,3375 ms`
- Interrupção estimada mínima: `170,576 ms`
- Interrupção estimada máxima: `238,949 ms`
- Média do primeiro ping depois do handover: `93,309 ms`

## Interpretação

O resultado de referência confirma que a automação consegue, de forma repetida:

- subir e validar o testbed de handover F1 em rfsim;
- comandar o handover pela interface Telnet da CU;
- manter o plano de usuário do UE até o `oai-ext-dn` local, sem perda de pacotes nas cinco execuções.

A interrupção medida está na casa das centenas de milissegundos. Esse valor serve de base de comparação para mudanças futuras. Isso vale principalmente para uma lógica de mobilidade mais elaborada ou para caminhos de medição mais controlados.

## Medição atual com iperf

As novas execuções, simples ou repetidas, podem medir com iperf ao mesmo tempo, com `IPERF_ENABLED=1`. Esses resultados trazem vazão, jitter, perda UDP ou retransmissões TCP. Eles não fazem parte da tabela histórica acima. Registre um novo resultado de referência com iperf em separado. Não altere este conjunto de dados.

## Limitação conhecida

As medidas de tempo de ida e volta (RTT) ainda incluem efeitos do rfsim, do escalonamento dos contêineres e do computador, e picos passageiros de processamento. Este resultado de referência, baseado em ping, serve para testes rápidos e para as primeiras comparações da pesquisa. Ele ainda não é uma medida limpa da latência do protocolo de rádio.
