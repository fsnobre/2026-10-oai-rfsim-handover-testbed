# Resultados de referência

> Tradução para o português. O original em inglês é o [report-baseline-results.md](report-baseline-results.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Relatório
>
> **Contexto:** [tutorial de handover F1 em RFsim](tutorial-f1-handover.pt-BR.md) e [guia do pipeline de medição](guide-measurement-pipeline.pt-BR.md)

Este documento registra a referência original validada, somente com ping, da automação de handover F1 no RFsimulator da OAI. Ela é anterior à medição integrada com iperf; seus números publicados permanecem inalterados para fins de comparação.

## Topologia do experimento

- 1 UE RFsim: `oai-nr-ue`
- 2 DUs: `oai-du0`, `oai-du1`
- 1 CU: `oai-cu`
- 1 plano de controle do 5GC da OAI
- 1 UPF estática: `oai-upf`
- 1 endpoint de rede de dados local: `oai-ext-dn`

O destino local do plano de dados é o `oai-ext-dn`, em `192.168.71.135`. O UE envia o tráfego de medição pela interface da sessão PDU, `oaitun_ue1`.

## Fluxo de inicialização e handover

O testbed é iniciado com a automação:

```bash
./scripts/up.sh
```

O fluxo de inicialização aguarda a prontidão do núcleo, da CU, da DU e do UE antes de os testes rápidos rodarem. Em seguida, o teste rápido aguarda que o plano de dados do UE alcance o destino de ping configurado.

O disparo de handover validado continua sendo o comando Telnet manual na CU:

```bash
echo ci trigger_f1_ho | nc -N 192.168.70.150 9090 && echo
```

O teste rápido envia esse comando por meio de:

```bash
./scripts/trigger_handover.sh
```

## Método de medição

A referência usa o ping ICMP como sonda de continuidade durante o handover. O iperf não foi ativado nestas cinco execuções históricas:

- destino: `192.168.71.135`
- contêiner de destino: `oai-ext-dn`
- interface do UE: `oaitun_ue1`
- número de repetições do experimento: `RUNS=5`
- método de handover: comando Telnet manual na CU, `ci trigger_f1_ho`

Em cada execução, o ping começa antes do handover, continua durante o handover e permanece ativo por um curto período depois dele. O parser estima a interrupção a partir da temporização das respostas de ping em torno do evento de disparo do handover.

## Resultados das execuções repetidas

| Execuções | Aprovadas | Perda de pacotes | Interrupção média | Desvio-padrão da interrupção | Interrupção mínima | Interrupção máxima | Média do primeiro ping após o handover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 5 | 0,0% | 207,0664 ms | 22,3375 ms | 170,576 ms | 238,949 ms | 93,309 ms |

## Resumo agregado

- Experimento repetido: `RUNS=5`
- Execuções bem-sucedidas: `5/5`
- Perda de pacotes: `0,0%`
- Interrupção estimada média: `207,0664 ms`
- Desvio-padrão da interrupção estimada: `22,3375 ms`
- Interrupção estimada mínima: `170,576 ms`
- Interrupção estimada máxima: `238,949 ms`
- Média do primeiro ping após o handover: `93,309 ms`

## Interpretação atual

A referência confirma que a automação consegue iniciar e validar repetidamente o testbed de handover F1 em RFsim, disparar o handover pela interface Telnet da CU e preservar a conectividade do plano de dados do UE com o destino local `oai-ext-dn`, sem perda de pacotes nas cinco execuções.

A interrupção medida está atualmente na ordem de centenas de milissegundos. Isso fornece uma referência prática para comparar mudanças futuras, especialmente ao adicionar lógica de controle de mobilidade mais elaborada ou caminhos de medição mais controlados.

## Capacidade atual de iperf

Novas execuções de teste rápido e repetidas podem adicionar iperf simultâneo com `IPERF_ENABLED=1`. Esses resultados incluem vazão, jitter, perda UDP ou retransmissões TCP, mas não fazem parte da tabela histórica acima. Uma nova referência com iperf e várias execuções deve ser registrada separadamente, em vez de alterar retroativamente este conjunto de dados.

## Limitação conhecida

As amostras de RTT ainda incluem efeitos de temporização do RFsim da OAI, escalonamento do Docker/contêineres, escalonamento do host e picos transitórios de processamento. A referência atual baseada em ping é útil para testes rápidos e comparações iniciais de pesquisa, mas ainda não deve ser tratada como uma medição limpa da latência do protocolo de rádio.
