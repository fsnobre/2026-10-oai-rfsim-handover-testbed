# Propriedade das redes Docker nas pilhas Compose da OAI

> Tradução para o português. O original em inglês é o [foundation-f00-docker-network-ownership.md](foundation-f00-docker-network-ownership.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Fundamento (`F00`)
>
> **Leitura obrigatória:** nenhuma

## Objetivo

Este documento define qual pilha Compose é dona das redes Docker compartilhadas e como as demais pilhas da OAI devem utilizá-las. A regra se aplica às topologias F1 e N2 deste repositório.

## Modelo de propriedade

O projeto Compose do núcleo (CN) da OAI é dono das seguintes redes e as cria:

| Rede Docker | Sub-rede | Chave de rede no Compose | Bridge Linux |
|---|---|---|---|
| `oai-cn5g-public-net` | `192.168.70.128/26` | `public_net` | `oai-cn5g` |
| `oai-ext-dn-traffic-net` | `192.168.71.128/26` | `traffic_net` | `oai-internet` |

As definições das redes ficam em `oai-cn5g/docker-compose.yaml`. Os arquivos Compose da RAN referenciam essas redes com `external: true`.

O ciclo de vida resultante é:

```text
O Compose do CN da OAI sobe
        |
        +-- cria public_net e traffic_net
        |
O Compose da RAN sobe
        |
        +-- conecta os contêineres às redes externas já existentes
```

## Por que as redes não devem ser criadas manualmente

Um comando como:

```bash
docker network create oai-cn5g-public-net
```

cria uma rede gerenciada de forma independente. Mesmo que o nome coincida, ela pode diferir em:

- sub-rede e configuração de IPAM;
- opções do driver e nome da bridge Linux;
- rótulos de propriedade do Compose; e
- comportamento do ciclo de vida durante `docker compose down`.

O comando manual usado historicamente empregava `192.168.70.0/24`, enquanto a definição do Compose do CN usa `192.168.70.128/26`. Os endereços estáticos dos contêineres podem parecer válidos nas duas faixas, o que torna a divergência fácil de passar despercebida, mas o Compose não consegue substituir uma rede incompatível já existente.

## Comportamento correto na inicialização

Execute:

```bash
./scripts/up.sh <topology>
```

O preflight trata a ausência da rede do CN como informativa, porque a pilha do CN ainda não foi iniciada. Depois que o CN sobe, o `up.sh` verifica que:

- a rede existe;
- o driver dela é `bridge`;
- a sub-rede esperada está presente;
- `com.docker.compose.project` identifica o projeto do CN; e
- `com.docker.compose.network` identifica a chave de rede esperada.

Só então a pilha da RAN é iniciada.

## Recuperação de uma rede incompatível

Primeiro, pare os contêineres conectados à rede:

```bash
./scripts/down.sh
```

Inspecione as conexões restantes:

```bash
docker network inspect oai-cn5g-public-net
docker network inspect oai-ext-dn-traffic-net
```

Se nenhum contêiner alheio ao testbed depender da rede incompatível, remova-a:

```bash
docker network rm oai-cn5g-public-net
docker network rm oai-ext-dn-traffic-net
```

Em seguida, execute `scripts/up.sh` e deixe o Compose do CN recriar as duas redes. Não remova uma rede em uso sem identificar os contêineres conectados a ela.

## Restrição do nome do projeto Compose

A validação de propriedade das redes espera que o nome do projeto Compose do CN corresponda ao padrão derivado do diretório, `oai-cn5g`, a menos que `COMPOSE_PROJECT_NAME` seja informado de forma consistente.

Se for necessário um nome de projeto personalizado:

```bash
COMPOSE_PROJECT_NAME=my-cn ./scripts/up.sh f1
```

O mesmo valor de ambiente deve ser usado nos comandos subsequentes do ciclo de vida do CN.

## Regra de projeto para novas topologias

Novas topologias de RAN não devem duplicar as definições de IPAM das redes do CN. Elas devem declarar:

```yaml
networks:
  public_net:
    external: true
    name: oai-cn5g-public-net
```

Adicione `traffic_net` somente quando um contêiner da RAN realmente precisar de acesso direto à rede Docker do lado do tráfego. Isso mantém uma única definição de rede de referência e evita divergência de configuração.
