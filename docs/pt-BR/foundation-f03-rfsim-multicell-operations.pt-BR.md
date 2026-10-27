# Regras de operação do RFsim com múltiplas células

> Tradução para o português. O original em inglês é o [foundation-f03-rfsim-multicell-operations.md](../en/foundation-f03-rfsim-multicell-operations.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Fundamento (`F03`)
>
> **Leitura obrigatória:** [F00 — Propriedade das redes Docker](foundation-f00-docker-network-ownership.pt-BR.md)

## Regra de topologia

Nas topologias com múltiplas células usadas aqui, o UE é o servidor RFsim e cada DU/gNB é um cliente RFsim:

```text
DU/gNB 0 -----\
               >----- oai-nr-ue RFsim server :4043
DU/gNB 1 -----/
```

O endereço do servidor no UE é `192.168.70.181`.

## Endereçamento dos contêineres

`127.0.0.1` sempre se refere ao namespace do contêiner atual. Uma DU configurada com `--rfsimulator.serveraddr 127.0.0.1` tenta se conectar a si mesma, e não ao contêiner do UE.

Use o endereço do UE explicitamente:

```text
--rfsimulator.serveraddr 192.168.70.181
```

Este repositório usa as formas indexada e não indexada das opções da OAI, conforme a topologia e o comportamento da imagem. Valide a linha de comando efetiva após atualizar a imagem da OAI.

## Precedência da linha de comando

Na imagem develop da OAI testada, ativar `--rfsim` inicializava o endpoint do cliente em `127.0.0.1`, mesmo quando o arquivo de configuração continha outro endereço. Por isso, o endpoint é explícito na linha de comando da DU.

Inspecione:

```bash
docker logs <du-or-gnb> | grep -E "CMDLINE|Trying to connect"
```

## Endereçamento da F1

| Componente | Endereço |
|---|---|
| CU | `192.168.70.150` |
| DU0 | `192.168.70.171` |
| DU1 | `192.168.70.172` |

Uma DU com endereço F1 local `127.0.0.1` não consegue estabelecer SCTP com uma CU em outro contêiner.

## Inicialização começando pela célula de origem

Para a conexão inicial na F1:

1. Inicie o servidor RFsim do UE e a DU0 de origem.
2. Aguarde a prontidão da sessão PDU e do plano de dados do UE.
3. Inicie a DU1 de destino.
4. Verifique se o UE continua alcançável.

Iniciar os dois transmissores de RF antes da conexão inicial causou instabilidade na decodificação de PBCH e SIB1 no ambiente validado. Depois da conexão, as duas DUs permanecem conectadas e o handover F1 é bem-sucedido.

## Verificação

```bash
docker exec oai-nr-ue ss -ltnp
docker exec oai-du0 ss -tnp
docker exec oai-du1 ss -tnp
docker logs oai-cu | grep -E "F1 Setup Request|cell .* is in service"
```

Par esperado da DU: `192.168.70.181:4043`.

## Sensibilidade à versão

As opções do RFsim da OAI dependem da imagem. Uma opção presente em outra topologia pode não ser suportada pela imagem atual. Opções desconhecidas podem ser detectadas tarde e causar aborto depois que a atividade de rádio já começou.

Após trocar as imagens, valide novamente os papéis de servidor/cliente, os nomes de opção aceitos, as conexões TCP, a sincronização, o acesso aleatório, o estabelecimento da sessão PDU e a conectividade após o handover.
