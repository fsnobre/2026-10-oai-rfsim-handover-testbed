# Enumerações de configuração e temporização de rádio na OAI

> Tradução para o português. O original em inglês é o [foundation-f04-oai-config-enums-and-timing.md](foundation-f04-oai-config-enums-and-timing.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Fundamento (`F04`)
>
> **Leitura obrigatória:** nenhuma

## Valores de configuração podem ser índices de enumeração

Vários campos libconfig da OAI usam índices inteiros de enumeração em vez de valores literais do protocolo. Os comentários próximos ao campo geralmente descrevem o mapeamento.

Por exemplo:

```text
# 1,2,4,8,10,20,40,80
ra_ResponseWindow = 4;
```

Aqui, `4` é a seleção, com índice a partir de zero, correspondente a 10 slots. Não significa uma janela de resposta de quatro slots.

| Índice da enumeração | Janela de resposta de RA efetiva |
|---:|---:|
| `0` | 1 slot |
| `1` | 2 slots |
| `2` | 4 slots |
| `3` | 8 slots |
| `4` | 10 slots |
| `5` | 20 slots |
| `6` | 40 slots |
| `7` | 80 slots |

Informar o valor literal `8` fica fora da faixa válida da enumeração e fez o codificador de configuração de RACH da OAI falhar numa asserção.

## Diagnóstico da temporização de PRACH/Msg2

```text
Initiating RA procedure with preamble ...
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
cannot schedule Msg2
```

Interpretação:

1. A sincronização de RF e a decodificação do SIB1 foram bem-sucedidas.
2. O UE transmitiu o PRACH.
3. A DU detectou o preâmbulo.
4. A DU tentou agendar a resposta tarde demais.
5. O UE relatou falha no RAR e voltou ao estado ocioso.

Isso é diferente de ausência de conexão RFsim, falha de PBCH/SIB1, PRACH abaixo do limiar ou falha de autenticação NAS.

## Correção aplicada

O atraso observado foi de 11 slots. O índice `4` permitia 10 slots. A configuração passou para o índice `5`, que permite 20 slots:

```text
ra_ResponseWindow = 5;
```

## Regra geral

Antes de alterar um parâmetro inteiro de rádio:

1. Leia o comentário de mapeamento.
2. Determine se é uma enumeração ou um literal.
3. Compare os logs com o valor efetivo decodificado.
4. Escolha o menor valor válido que cubra a condição.
5. Teste novamente a sincronização, o acesso aleatório, o registro e o tráfego de dados.

Não deduza unidades apenas pelo nome do campo.
