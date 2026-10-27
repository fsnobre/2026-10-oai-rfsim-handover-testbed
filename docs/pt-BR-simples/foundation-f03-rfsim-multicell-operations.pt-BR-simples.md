# Regras para várias células no rfsim

> Tradução para o português em Linguagem Simples. O original em inglês é o [foundation-f03-rfsim-multicell-operations.md](../en/foundation-f03-rfsim-multicell-operations.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** base (`F03`)
>
> **Leitura prévia:** [F00 — Quem cria as redes Docker](foundation-f00-docker-network-ownership.pt-BR-simples.md)

## Regra da topologia

Nas topologias com várias células deste repositório, o UE é o servidor do simulador de rádio da OAI (rfsim). Cada DU ou gNB é um cliente do rfsim:

```text
DU/gNB 0 -----\
               >----- oai-nr-ue, servidor rfsim na porta 4043
DU/gNB 1 -----/
```

O endereço do servidor no UE é `192.168.70.181`.

## Endereços dentro dos contêineres

O endereço `127.0.0.1` sempre aponta para o próprio contêiner. Uma DU configurada com `--rfsimulator.serveraddr 127.0.0.1` tenta se conectar a si mesma, e não ao contêiner do UE.

Informe o endereço do UE de forma explícita:

```text
--rfsimulator.serveraddr 192.168.70.181
```

Este repositório usa a forma da opção com índice (`[0]`) e a forma sem índice. A escolha depende da topologia e da imagem. Depois de atualizar a imagem da OAI, confira a linha de comando que a imagem usa de fato.

## Qual valor prevalece

Na imagem `develop` da OAI testada, a opção `--rfsim` definia o endereço do cliente como `127.0.0.1`. Isso acontecia mesmo com outro endereço no arquivo de configuração. Por isso, o endereço fica explícito na linha de comando da DU.

Para conferir:

```bash
docker logs <du-ou-gnb> | grep -E "CMDLINE|Trying to connect"
```

## Endereços do F1

| Componente | Endereço |
|---|---|
| CU | `192.168.70.150` |
| DU0 | `192.168.70.171` |
| DU1 | `192.168.70.172` |

Se o endereço F1 local da DU for `127.0.0.1`, a DU não consegue abrir a conexão SCTP com uma CU em outro contêiner.

## Subir primeiro a célula de origem

Na primeira conexão do UE no F1:

1. Suba o servidor rfsim no UE e a DU0 de origem.
2. Espere a sessão PDU e o plano de usuário do UE ficarem prontos.
3. Suba a DU1 de destino.
4. Confira se o UE continua respondendo.

No ambiente validado, ligar os dois transmissores antes da primeira conexão deixou instável a decodificação do PBCH e do SIB1. Depois que o UE se conecta, as duas DUs ficam conectadas, e o handover F1 funciona.

## Verificação

```bash
docker exec oai-nr-ue ss -ltnp
docker exec oai-du0 ss -tnp
docker exec oai-du1 ss -tnp
docker logs oai-cu | grep -E "F1 Setup Request|cell .* is in service"
```

Cada DU deve estar conectada a `192.168.70.181:4043`.

## Dependência da versão

As opções do rfsim mudam de uma imagem da OAI para outra. Uma opção que funciona em outra topologia pode não existir na imagem atual. A imagem pode detectar uma opção desconhecida só mais tarde, e o processo pode parar depois que o rádio já começou a funcionar.

Depois de trocar a imagem, confira de novo:

- os papéis de servidor e de cliente;
- os nomes de opção aceitos;
- as conexões TCP;
- a sincronização;
- o acesso aleatório;
- a criação da sessão PDU;
- a conectividade depois do handover.
