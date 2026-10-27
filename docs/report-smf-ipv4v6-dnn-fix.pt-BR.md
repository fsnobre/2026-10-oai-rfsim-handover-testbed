# Relatório da correção do SMF para DNN com IPv4v6

> Tradução para o português. O original em inglês é o [report-smf-ipv4v6-dnn-fix.md](report-smf-ipv4v6-dnn-fix.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Relatório
>
> **Contexto:** [Guia USRP X310 + UE COTS](guide-usrp-x310-cots.pt-BR.md) e [F02 — Alcance do plano de usuário e da DN](foundation-f02-dn-reachability.pt-BR.md)

**Data:** 5 de maio de 2026 (registrado em 27 de outubro de 2026)
**Escopo:** SMF do 5G Core da OAI com UE comercial (Telit FN990)
**Status:** corrigido em uma imagem do SMF construída localmente; não faz parte da pilha padrão deste repositório

## Resumo executivo

Um Telit FN990 se registrava no AMF, mas o SMF rejeitava toda sessão PDU como "unknown requested DNN" (causa 5GSM `0x1b`), logo depois de registrar `DNN matched!`. O UE pede uma sessão IPv4v6 e o DNN estava configurado como IPv4. A validação de DNN do SMF só aceitava tipos exatamente iguais. Uma alteração local nessa validação permite que o SMF aceite o pedido e escolha IPv4. Depois da alteração, o FN990 recebeu `PDU Session Establishment Accept` e um endereço IPv4.

## Sintoma

```text
Requested DNN: internet
DNN matched!
unknown requested DNN internet
PDU Session Establishment Reject (5GSM Cause: 0x1b)
```

`0x1b` significa "DNN ausente ou desconhecido". O nome do DNN coincidia, o que tornava o log enganoso.

## Causa raiz

A validação de DNN do SMF (`src/smf_app/smf_config.cpp`, código da `develop` obtido em 21 de abril de 2026) só retornava correspondência quando o tipo de sessão PDU pedido era igual ao configurado. O FN990 pede **IPv4v6**; o DNN era **IPv4**. A função retornava "não encontrado" depois de a comparação do nome ter dado certo, e o SMF rejeitava a sessão antes que a lógica de escolha de endereço pudesse escolher IPv4.

O problema foi reproduzido em RFsim, com o tipo de sessão PDU do OAI NR-UE definido como `IPv4v6`, o que descartou o lado do rádio.

## Correção

Foram acrescentados dois casos depois da comparação de igualdade existente:

| Tipo pedido | Tipo do DNN configurado | Antes | Depois |
|---|---|---|---|
| IPv4v6 | IPv4 | rejeitado (`0x1b`) | aceito; o SMF escolhe IPv4 |
| IPv4v6 | IPv6 | rejeitado (`0x1b`) | aceito; o SMF escolhe IPv6 |
| qualquer | mesmo tipo | aceito | aceito (sem mudança) |

Cada caso novo registra um aviso no log. A escolha de endereço em si não foi alterada. O arquivo-fonte modificado não é publicado por causa da licença do SMF da OAI (`LicenseRef-CSSL-1.0`).

## Relevância para este testbed

O núcleo deste repositório (`oai-cn5g/docker-compose.yaml`) usa a imagem padrão `oaisoftwarealliance/oai-smf:develop`, e o DNN padrão `oai` em `oai-cn5g/conf/config.yaml` é `IPV4`. As topologias RFsim não são afetadas, porque a configuração do OAI NR-UE (`conf-nr-ue.conf`) pede IPv4.

Um UE COTS que peça IPv4v6 no DNN `oai` pode sofrer essa rejeição com a imagem padrão. Procure no log do SMF a sequência acima antes de investigar o lado do rádio.

## Onde a correção foi usada

O SMF corrigido foi construído como `oai-smf:ipv4v6-dnn-fallback` e `oai-smf:ipv4v6-dnn-fallback-smf_context-fix` e usado nos cenários de slicing do repositório companheiro `cerise_nobre`. O registro completo está lá, em `oai/docs/oai_smf_ipv4v6_dnn_fix.md`.
