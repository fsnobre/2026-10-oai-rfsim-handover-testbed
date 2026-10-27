# Valores enumerados da configuração da OAI e tempos de rádio

> Tradução para o português em Linguagem Simples. O original em inglês é o [foundation-f04-oai-config-enums-and-timing.md](../en/foundation-f04-oai-config-enums-and-timing.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** base (`F04`)
>
> **Leitura prévia:** nenhuma

## Um valor de configuração pode ser um índice

Vários campos de configuração da OAI (formato libconfig) usam um índice de uma lista de valores, e não o valor real do protocolo. Em geral, um comentário perto do campo mostra a lista.

Exemplo:

```text
# 1,2,4,8,10,20,40,80
ra_ResponseWindow = 4;
```

Aqui, `4` é a posição na lista, contada a partir de zero. Ela escolhe 10 slots. O valor não quer dizer uma janela de resposta de 4 slots.

| Índice | Janela de resposta do acesso aleatório |
|---:|---:|
| `0` | 1 slot |
| `1` | 2 slots |
| `2` | 4 slots |
| `3` | 8 slots |
| `4` | 10 slots |
| `5` | 20 slots |
| `6` | 40 slots |
| `7` | 80 slots |

O valor literal `8` fica fora da faixa de índices válidos. Com ele, o codificador da configuração do acesso aleatório (RACH) da OAI parou com erro (*assert*).

## Como diagnosticar o tempo do PRACH e da Msg2

```text
Initiating RA procedure with preamble ...
exceeded RA window: preamble at 503.19 now 504.10 (diff 11),
ra_ResponseWindow 4/10 slots
cannot schedule Msg2
```

O que essas linhas mostram:

1. A sincronização de rádio e a decodificação do SIB1 deram certo.
2. O UE transmitiu o PRACH.
3. A DU detectou o preâmbulo.
4. A DU tentou agendar a resposta tarde demais.
5. O UE registrou a falha do RAR e voltou para o estado ocioso.

Essa falha é diferente de:

- falta de conexão com o rfsim;
- falha no PBCH ou no SIB1;
- PRACH abaixo do limiar de detecção;
- falha na autenticação NAS.

## Correção aplicada

O atraso observado foi de 11 slots. O índice `4` permitia 10 slots. A configuração mudou para o índice `5`, que permite 20 slots:

```text
ra_ResponseWindow = 5;
```

## Regra geral

Antes de mudar um parâmetro de rádio com valor inteiro:

1. Leia o comentário que mostra a lista de valores.
2. Descubra se o valor é um índice ou um valor literal.
3. Compare os logs com o valor que a OAI decodificou de fato.
4. Escolha o menor valor válido que resolve o problema.
5. Teste de novo a sincronização, o acesso aleatório, o registro e o tráfego de dados.

Não deduza a unidade só pelo nome do campo.
