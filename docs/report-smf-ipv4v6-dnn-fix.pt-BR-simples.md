# Relatório da correção do SMF para sessões IPv4v6

> Tradução para o português em Linguagem Simples. O original em inglês é o [report-smf-ipv4v6-dnn-fix.md](report-smf-ipv4v6-dnn-fix.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** relatório
>
> **Contexto:** [Guia do USRP X310 com UE comercial](guide-usrp-x310-cots.pt-BR-simples.md) e [F02 — Plano de usuário e acesso à rede de dados](foundation-f02-dn-reachability.pt-BR-simples.md)

**Data:** 05/05/2026 (registrado em 27/10/2026)
**Escopo:** SMF do núcleo 5G da OAI com UE comercial (Telit FN990)
**Situação:** corrigido numa imagem do SMF feita localmente. Essa imagem não faz parte da rede padrão deste repositório.

## Resumo executivo

O Telit FN990 se registrava no AMF, mas o SMF recusava toda sessão de dados (sessão PDU). O motivo informado era "unknown requested DNN" (causa `0x1b`), logo depois da mensagem `DNN matched!`.

O FN990 pede uma sessão do tipo IPv4v6, e a rede de dados (DNN) estava configurada como IPv4. O SMF só aceitava o pedido se os dois tipos fossem iguais. Uma mudança nessa verificação fez o SMF aceitar o pedido e escolher IPv4. Depois da mudança, o FN990 recebeu `PDU Session Establishment Accept` e um endereço IPv4.

## Sintoma

```text
Requested DNN: internet
DNN matched!
unknown requested DNN internet
PDU Session Establishment Reject (5GSM Cause: 0x1b)
```

`0x1b` quer dizer "DNN ausente ou desconhecido". Mas o nome do DNN estava certo, por isso o log confundia.

## Causa

A verificação do DNN fica no arquivo `src/smf_app/smf_config.cpp` do SMF (código da `develop` baixado em 21/04/2026). Ela só aceitava o DNN se o tipo de sessão pedido fosse igual ao configurado.

O FN990 pede **IPv4v6**, e o DNN era **IPv4**. Por isso, a verificação dizia "não encontrado" mesmo com o nome certo. O SMF recusava a sessão antes de chegar à parte que escolhe o tipo de endereço.

Para separar o problema do rádio, ele foi reproduzido no rfsim, com o OAI NR-UE pedindo sessão `IPv4v6`.

## Correção

Foram acrescentados dois casos depois da comparação que já existia:

| Tipo pedido | Tipo do DNN | Antes | Depois |
|---|---|---|---|
| IPv4v6 | IPv4 | recusado (`0x1b`) | aceito; o SMF escolhe IPv4 |
| IPv4v6 | IPv6 | recusado (`0x1b`) | aceito; o SMF escolhe IPv6 |
| qualquer | o mesmo | aceito | aceito (igual a antes) |

Cada caso novo escreve um aviso no log. A escolha do endereço não mudou. O arquivo alterado não está publicado por causa da licença do SMF da OAI (`LicenseRef-CSSL-1.0`).

## O que isso tem a ver com este testbed

O núcleo 5G deste repositório (`oai-cn5g/docker-compose.yaml`) usa a imagem padrão `oaisoftwarealliance/oai-smf:develop`. O DNN padrão `oai`, em `oai-cn5g/conf/config.yaml`, é `IPV4`.

As topologias do rfsim não têm esse problema, porque o OAI NR-UE (`conf-nr-ue.conf`) pede IPv4.

Um UE comercial que peça IPv4v6 no DNN `oai` pode ser recusado com a imagem padrão. Antes de investigar o rádio, procure no log do SMF as mensagens acima.

## Onde a correção foi usada

O SMF corrigido foi gerado com os nomes `oai-smf:ipv4v6-dnn-fallback` e `oai-smf:ipv4v6-dnn-fallback-smf_context-fix`. Ele foi usado nos cenários de slicing do repositório `cerise_nobre`. O registro completo está lá, em `oai/docs/oai_smf_ipv4v6_dnn_fix.md`.
