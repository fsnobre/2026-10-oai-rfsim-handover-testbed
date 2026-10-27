# Mapa da documentação

> Tradução para o português em Linguagem Simples. O original em inglês é o [README.md](../en/README.md). Se houver diferença entre os dois, vale o original.

O nome de cada documento indica a finalidade dele. Os documentos de base (*foundations*) também têm identificadores fixos: `F00`, `F01` e assim por diante. Com esses identificadores, um documento indica os pré-requisitos sem precisar de nomes de arquivo longos.

Os identificadores não indicam nível de dificuldade. Ao criar um documento de base, não renumere os existentes. Use o próximo identificador livre.

As traduções ficam ao lado do original, com o sufixo `.pt-BR-simples.md` (Linguagem Simples) ou `.pt-BR.md` (tradução padrão).

## Documentos de base

| ID | Documento | Leitura prévia |
|---|---|---|
| F00 | [Quem cria as redes Docker](foundation-f00-docker-network-ownership.pt-BR-simples.md) | Nenhuma |
| F01 | [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR-simples.md) | Nenhuma |
| F02 | [Plano de usuário e acesso à rede de dados](foundation-f02-dn-reachability.pt-BR-simples.md) | F00 |
| F03 | [Regras para várias células no rfsim](foundation-f03-rfsim-multicell-operations.pt-BR-simples.md) | F00 |
| F04 | [Valores enumerados da configuração da OAI e tempos de rádio](foundation-f04-oai-config-enums-and-timing.pt-BR-simples.md) | Nenhuma |

## Ordem de leitura recomendada

### Handover F1 em rfsim

`F00 → F01 → F02 → F03 → F04 →` [pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md) `→` [tutorial F1](tutorial-f1-handover.pt-BR-simples.md)

### Handover N2 em rfsim, com gNBs monolíticas

`F00 → F01 → F02 → F03 → F04 →` [guia N2](guide-n2-handover.pt-BR-simples.md) `→` [pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md) `→` [tutorial monolítico](tutorial-n2-monolithic-handover.pt-BR-simples.md)

### Handover N2 em rfsim, com pares CU/DU

`F00 → F01 → F02 → F03 → F04 →` [guia N2](guide-n2-handover.pt-BR-simples.md) `→` [pipeline de medição](guide-measurement-pipeline.pt-BR-simples.md) `→` [tutorial CU/DU](tutorial-n2-cu-du-handover.pt-BR-simples.md)

### USRP X310 com UE comercial

`F00 → F01 → F04 →` [guia do USRP com uma célula](guide-usrp-x310-cots.pt-BR-simples.md) `→` [guia de handover distribuído](guide-usrp-distributed-handover.pt-BR-simples.md)

Se uma execução com rádio real falhar, consulte o catálogo de problemas da OAI no repositório `cerise_nobre` (`oai/docs/oai_troubleshooting_testbed.md`). Procure nele, com `grep`, a mensagem de log que você está vendo. Veja [Referências externas](#referências-externas), abaixo.

## Guias e tutoriais

- [Pipeline de medição e ciclo de vida de uma execução](guide-measurement-pipeline.pt-BR-simples.md)
- [Guia do testbed de handover N2](guide-n2-handover.pt-BR-simples.md)
- [Guia do USRP X310 com UE comercial](guide-usrp-x310-cots.pt-BR-simples.md)
- [Guia de handover distribuído com USRP](guide-usrp-distributed-handover.pt-BR-simples.md)
- [Tutorial de handover F1 em rfsim](tutorial-f1-handover.pt-BR-simples.md)
- [Tutorial de handover N2 em rfsim, com gNBs monolíticas](tutorial-n2-monolithic-handover.pt-BR-simples.md)
- [Tutorial de handover N2 em rfsim, com pares CU/DU](tutorial-n2-cu-du-handover.pt-BR-simples.md)

## Relatórios, registros e passagens de contexto

Estes documentos trazem evidências ou contexto histórico. Eles não são pré-requisitos, a menos que outro documento os indique.

- [Resultado de referência](report-baseline-results.pt-BR-simples.md)
- [Relatório da correção da partida e da prontidão do F1 em rfsim](report-f1-rfsim-readiness-fix.pt-BR-simples.md)
- [Avaliação do repositório: práticas, normas e experiência de uso](report-repository-evaluation.pt-BR-simples.md)
- [Relatório da correção do SMF para sessões IPv4v6](report-smf-ipv4v6-dnn-fix.pt-BR-simples.md)
- [Histórico do desenvolvimento](record-development-history.pt-BR-simples.md)
- [Registro da fase 6 do painel web: visão geral para o operador](record-dashboard-phase6-overview.pt-BR-simples.md)
- [Passagem de contexto: integração com xApps](handoff-xapp-integration.pt-BR-simples.md)
- [Passagem de contexto: correções da avaliação](handoff-evaluation-remediation.pt-BR-simples.md)
- [Passagem de contexto: visão geral ao vivo do painel web](handoff-dashboard-overview-live.pt-BR-simples.md)
- [Passagem de contexto: falha de autenticação no teste rápido F1 (resolvida)](handoff-f1-smoke-auth-failure.pt-BR-simples.md)

## Referências externas

O conhecimento sobre a OAI que vale para mais de um testbed fica fora deste repositório, de propósito. Ele está no repositório `cerise_nobre`, na pasta `oai/` (`github.com/fsnobre/cerise_nobre`). No Mini PC, esse repositório fica em `../cerise_nobre`. Em 26/10/2026, ele absorveu o antigo repositório `cerise_oai`.

Os caminhos da tabela abaixo partem de `oai/`. Guarde lá o material geral sobre OAI e ORANSlice. Guarde aqui o material próprio deste testbed.

| Documento | Finalidade |
|---|---|
| `docs/oai_troubleshooting_testbed.md` | Falhas frequentes com rádio real, organizadas pela mensagem de log da OAI, com as causas confirmadas e as hipóteses descartadas. **Comece por aqui quando uma execução falhar.** Acrescente casos novos a ele, em vez de refazer o diagnóstico. |
| `docs/oai_gnb_yaml_testbed.md` | Valores oficiais dos parâmetros da gNB para este hardware |
| `docs/oai_gnb_yaml_general.md` | Referência geral dos parâmetros da gNB, sem depender de fabricante |
| `docs/nr_prb_frequency_reference.md` | Tabelas de PRB, largura de banda e ARFCN |
| `docs/oai_handover_{n2,xn,intra_gnb,ric}.md` | Tipos de handover, inclusive o mapeamento dos IEs do E2SM-RC |
| `docs/oai_f1_split_*.md`, `docs/oai_oru_fronthaul_*.md` | Divisão F1 e fronthaul da RU |
| `scripts/validate_gnb_yaml.py` | Validador da coerência dos parâmetros nos arquivos YAML e conf da gNB |
| `scripts/collect_*.sh` | Coletores de diagnóstico (gNB, núcleo 5G, FlexRIC, estação de trabalho e FN990) |

## Especificações

- [Especificação do painel web](spec-dashboard.pt-BR-simples.md)

## Regra para nomes de arquivo

```text
foundation-fNN-<tema>.md  conceito ou regra de operação de base, estável
guide-<tema>.md           guia amplo, de operação ou de conceitos
tutorial-<tema>.md        procedimento executável com um objetivo
spec-<tema>.md            especificação de projeto
report-<tema>.md          relatório de resultados, investigação ou validação
record-<tema>.md          registro histórico
handoff-<tema>.md         contexto preparado para outra frente de trabalho
```

Todo guia ou tutorial novo deve indicar a leitura prévia logo no início, com links diretos para os documentos.
