# Modelo de prontidão funcional para testbeds da OAI

> Tradução para o português em Linguagem Simples. O original em inglês é o [foundation-f01-functional-readiness-model.md](foundation-f01-functional-readiness-model.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** base (`F01`)
>
> **Leitura prévia:** nenhuma

## Problema

Um processo da OAI pode continuar rodando com a pilha de protocolos inutilizável. Por isso, três condições são necessárias, mas não bastam para dizer que o sistema está pronto:

- o contêiner existe;
- o processo está saudável;
- as portas de controle estão abertas.

O testbed usa um modelo de prontidão em camadas:

| Camada | Evidência | Falha comum quando a evidência falta |
|---|---|---|
| Computador | Docker, TUN, SCTP e ferramentas | Os contêineres não sobem ou não acessam os dispositivos. |
| Contêiner | O processo necessário está rodando. | O contêiner cai na hora ou reinicia sem parar. |
| Transporte | Conexões do rfsim, do F1, do NGAP e do PFCP | Os componentes rodam, mas não se comunicam. |
| Rádio | PBCH/SIB1 e PRACH/RAR | O UE não entra em RRC. |
| Plano de controle | Registro RRC e NAS | O AMF não tem UE registrado. |
| Sessão | Interface `oaitun_ue1` com o endereço do UE | Não há sessão PDU. |
| Plano de usuário | O destino responde pelo túnel do UE. | A sessão existe, mas o encaminhamento falha. |
| Handover | O comando é aceito e o handover termina. | Não há UE elegível, ou a célula de destino falha. |

Siglas da tabela:

- **UE:** equipamento de usuário;
- **PBCH, SIB1:** canal e mensagem de difusão que o UE lê para se sincronizar com a célula;
- **PRACH, RAR:** canal e resposta do acesso aleatório;
- **RRC:** controle dos recursos de rádio;
- **NAS:** sinalização entre o UE e o núcleo 5G;
- **AMF:** função do núcleo 5G que registra o UE.

## Regras de prontidão

Uma etapa não garante a seguinte. Não suponha nenhuma destas implicações:

```text
contêiner rodando           != rfsim conectado
rádio sincronizado          != acesso aleatório concluído
RRC conectado               != registrado no NAS
UE registrado               != sessão PDU criada
interface PDU presente      != destino alcançável pelo plano de usuário
comando de handover aceito  != handover concluído
```

## O que cada script faz

### `preflight_check.sh`

Confere, antes de subir, os pré-requisitos que não dependem do testbed estar rodando:

- Docker e Compose;
- ferramentas do computador;
- validade dos arquivos Compose;
- compatibilidade das redes;
- TUN e SCTP;
- rotas e VPNs;
- portas;
- imagens;
- espaço em disco.

A verificação prévia não deve exigir nada que o próprio `up.sh` vai criar.

### `up.sh`

No F1, o `up.sh` só avança quando cada etapa fica pronta:

1. Os serviços do núcleo 5G estão saudáveis.
2. A CU e o Telnet estão prontos.
3. A DU0 e o UE subiram.
4. A sessão PDU do UE está pronta, e a rede de dados responde.
5. A DU1 subiu.
6. O plano de usuário do UE responde de novo.

A segunda conferência do plano de usuário detecta efeitos da subida da célula de destino sobre o UE já registrado.

### `status.sh`

O `status.sh` só mostra `SUMMARY: PASS` quando:

- todos os contêineres críticos estão rodando;
- a interface de controle do handover responde;
- a interface `oaitun_ue1` tem endereço IPv4;
- o destino configurado na rede de dados responde pelo túnel.

### `poststart_check.sh`

Faz diagnósticos que não bloqueiam a subida. Ele também procura erros fatais nos logs. Quem decide se a subida deu certo continua sendo o `up.sh`.

### `trigger_handover.sh`

Se o plano de controle responder que não há UE em RRC, o script trata o comando como falho.

## Ordem recomendada de diagnóstico

1. Estado dos contêineres e códigos de saída.
2. Sockets e endereços do rfsim.
3. Conexões F1, NGAP e PFCP.
4. Sincronização do UE pelo PBCH/SIB1.
5. Processamento do PRACH e do RAR (Msg2).
6. Estado RRC do UE na CU ou na gNB.
7. Tabela de UEs registrados no AMF.
8. Endereço da interface `oaitun_ue1`.
9. Ping pela interface `oaitun_ue1`.
10. Logs da célula de origem e da célula de destino do handover.

Com essa ordem, você não perde tempo com o assinante ou com o SMF quando o UE ainda nem se sincronizou com o rádio.

## Como usar os health checks do Docker

Os health checks do Docker devem ser leves e locais. A prontidão entre contêineres e de ponta a ponta fica nos scripts de orquestração.

Uma DU pode estar saudável enquanto espera o UE. O UE pode ser um servidor rfsim saudável antes de uma DU se conectar. Se cada health check exigisse a prontidão completa, um contêiner ficaria esperando o outro para sempre.
