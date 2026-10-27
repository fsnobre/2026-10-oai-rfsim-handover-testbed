# Modelo de prontidão funcional para testbeds da OAI

> Tradução para o português. O original em inglês é o [foundation-f01-functional-readiness-model.md](foundation-f01-functional-readiness-model.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Fundamento (`F01`)
>
> **Leitura obrigatória:** nenhuma

## Problema

Um processo da OAI pode continuar vivo enquanto a pilha de protocolos está inutilizável. Por isso, a existência do contêiner, a saúde do processo e as portas de controle abertas são condições de prontidão necessárias, mas não suficientes.

O testbed usa um modelo de prontidão em camadas:

| Camada | Evidência | Falha típica quando ausente |
|---|---|---|
| Host | Docker, TUN, SCTP, ferramentas | Os contêineres não sobem ou não conseguem anexar dispositivos |
| Contêiner | Processo obrigatório em execução | Falha imediata ou ciclo de reinicialização |
| Transporte | Associações RFsim, F1, NGAP/PFCP | Os componentes rodam, mas não se comunicam |
| Rádio | PBCH/SIB1, PRACH/RAR | O UE não consegue entrar em RRC |
| Plano de controle | RRC e registro NAS | O AMF não tem UE registrado |
| Sessão | `oaitun_ue1` com endereço do UE | Não há sessão PDU |
| Plano de usuário | Destino alcançável pelo túnel do UE | A sessão existe, mas o encaminhamento está quebrado |
| Handover | Disparo confirmado e concluído | Nenhum UE elegível ou falha na célula de destino |

## Invariantes de prontidão

As implicações abaixo não devem ser presumidas:

```text
contêiner em execução          != RFsim conectado
RF sincronizado                != acesso aleatório concluído
RRC conectado                  != NAS registrado
UE registrado                  != sessão PDU estabelecida
interface PDU presente         != destino do plano de usuário alcançável
comando de handover aceito     != handover concluído
```

## Responsabilidades dos scripts

### `preflight_check.sh`

Verifica os pré-requisitos que podem ser avaliados antes da inicialização: Docker e Compose, ferramentas do host, validade do Compose, compatibilidade das redes, TUN, SCTP, rotas, VPNs, portas, imagens e espaço em disco. O preflight não deve exigir estado de execução que cabe à inicialização criar.

### `up.sh`

Na F1, as etapas de verificação em tempo de execução são:

1. Serviços do CN saudáveis.
2. CU e Telnet prontos.
3. DU0 e UE iniciados.
4. Sessão PDU do UE e alcance da DN prontos.
5. DU1 iniciada.
6. Alcance do plano de dados do UE verificado novamente.

A segunda verificação do plano de dados detecta efeitos da inicialização da célula de destino sobre o UE registrado.

### `status.sh`

`SUMMARY: PASS` exige todos os contêineres críticos, o endpoint de controle de handover, `oaitun_ue1` com endereço IPv4 e o destino da DN configurado alcançável pelo túnel.

### `poststart_check.sh`

Fornece diagnósticos não bloqueantes e varredura de logs em busca de erros fatais. O veredito bloqueante da inicialização continua no `up.sh`.

### `trigger_handover.sh`

Trata como comando com falha uma resposta do plano de controle informando que não existe UE em RRC.

## Ordem de diagnóstico recomendada

1. Estado dos contêineres e códigos de saída.
2. Sockets do RFsim e endereços dos endpoints.
3. Associações F1, NGAP e PFCP.
4. Sincronização PBCH/SIB1 do UE.
5. Processamento de PRACH e RAR/Msg2.
6. Estado RRC do UE na CU/gNB.
7. Tabela de registro de UEs no AMF.
8. Endereço da `oaitun_ue1`.
9. Ping pela `oaitun_ue1`.
10. Logs de origem e destino do handover.

Isso evita depurar a configuração do assinante ou do SMF quando o UE ainda não concluiu a sincronização de rádio.

## Orientações sobre health checks

Os health checks do Docker devem continuar leves e locais. A prontidão entre contêineres e de ponta a ponta pertence aos scripts de orquestração. Uma DU pode ser um processo saudável enquanto espera um UE, e um UE pode ser um servidor RFsim saudável antes de uma DU se conectar; colocar a prontidão completa em health checks individuais criaria dependências circulares.
