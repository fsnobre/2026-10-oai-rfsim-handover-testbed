# Quem cria as redes Docker nas pilhas Compose da OAI

> Tradução para o português em Linguagem Simples. O original em inglês é o [foundation-f00-docker-network-ownership.md](foundation-f00-docker-network-ownership.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** base (`F00`)
>
> **Leitura prévia:** nenhuma

## Finalidade

Este documento define qual pilha Compose cria as redes Docker compartilhadas. Ele também define como as outras pilhas da OAI usam essas redes. A regra vale para as topologias F1 e N2 deste repositório.

## Quem cria cada rede

O projeto Compose do núcleo 5G da OAI cria e controla estas redes:

| Rede Docker | Sub-rede | Chave da rede no Compose | Bridge do Linux |
|---|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` | `oai-cn5g` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` | `oai-internet` |

As redes estão definidas em `oai-cn5g/docker-compose.yaml`. Os arquivos Compose da rede de acesso por rádio (RAN) usam essas redes com `external: true`.

O ciclo de vida fica assim:

```text
O Compose do núcleo 5G sobe
        |
        +-- cria a public_net e a traffic_net
        |
O Compose da RAN sobe
        |
        +-- liga os contêineres às redes externas que já existem
```

## Por que não criar as redes à mão

Um comando como este cria uma rede independente:

```bash
docker network create oai-cn5g-public-net
```

Mesmo com o mesmo nome, essa rede pode ter diferenças em:

- sub-rede e configuração de endereços (IPAM);
- opções do driver e nome da bridge do Linux;
- etiquetas que indicam o projeto Compose dono da rede;
- comportamento durante o `docker compose down`.

O comando manual antigo usava `192.168.70.0/24`. O Compose do núcleo 5G usa `192.168.70.128/26`. Os endereços fixos dos contêineres cabem nas duas faixas. Por isso, é fácil não perceber a diferença. Mas o Compose não consegue substituir uma rede incompatível que já existe.

## Como subir do jeito certo

Execute:

```bash
./scripts/up.sh <topologia>
```

Antes de subir, a verificação prévia só informa a falta da rede do núcleo 5G. Isso não é erro, porque o núcleo ainda não subiu. Depois que o núcleo sobe, o `up.sh` confere se:

- a rede existe;
- o driver é `bridge`;
- a sub-rede esperada está presente;
- a etiqueta `com.docker.compose.project` indica o projeto do núcleo 5G;
- a etiqueta `com.docker.compose.network` indica a chave de rede esperada.

Só depois disso o `up.sh` sobe a RAN.

## Como corrigir uma rede incompatível

1. Pare os contêineres ligados à rede:

   ```bash
   ./scripts/down.sh
   ```

2. Veja se ainda há contêineres ligados às redes:

   ```bash
   docker network inspect oai-cn5g-public-net
   docker network inspect oai-ext-dn-traffic-net
   ```

3. Se nenhum outro contêiner depender da rede incompatível, apague-a:

   ```bash
   docker network rm oai-cn5g-public-net
   docker network rm oai-ext-dn-traffic-net
   ```

4. Execute `scripts/up.sh`. O Compose do núcleo 5G recria as duas redes.

> **CUIDADO:** Não apague uma rede em uso sem identificar os contêineres ligados a ela. Outros experimentos podem parar.

## Limite do nome do projeto Compose

A validação espera que o projeto Compose do núcleo 5G se chame `oai-cn5g`. Esse é o nome padrão, tirado do nome da pasta. Para usar outro nome, informe `COMPOSE_PROJECT_NAME` sempre com o mesmo valor.

Exemplo com outro nome de projeto:

```bash
COMPOSE_PROJECT_NAME=my-cn ./scripts/up.sh f1
```

Use o mesmo valor em todos os comandos seguintes do núcleo 5G.

## Regra para novas topologias

As novas topologias da RAN não devem repetir a definição de endereços das redes do núcleo 5G. Elas devem declarar:

```yaml
networks:
  public_net:
    external: true
    name: oai-cn5g-public-net
```

Só acrescente a `traffic_net` se um contêiner da RAN precisar mesmo de acesso direto à rede Docker de tráfego. Assim, cada rede tem uma única definição oficial, e as configurações não divergem com o tempo.
