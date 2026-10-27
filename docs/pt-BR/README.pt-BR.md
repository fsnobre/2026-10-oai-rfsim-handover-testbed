# Mapa da documentação

> Tradução para o português. O original em inglês é o [README.md](../en/README.md). Em caso de divergência, prevalece o original.
>
> As traduções ficam ao lado do original, com o sufixo `.pt-BR.md` (tradução padrão) ou `.pt-BR-simples.md` (Linguagem Simples). Este mapa aponta para as traduções padrão; a versão em Linguagem Simples dele é o [README.pt-BR-simples.md](../pt-BR-simples/README.pt-BR-simples.md).

Os documentos são nomeados pela finalidade. Os documentos de fundamentos também têm IDs estáveis (`F00`, `F01` e assim por diante), para que os pré-requisitos possam ser referenciados sem codificar o grafo de dependências no nome de cada arquivo.

Os IDs dos fundamentos são identificadores, e não níveis de dificuldade intercambiáveis. Não renumere os fundamentos existentes ao inserir um novo documento; atribua o próximo ID não utilizado.

## Fundamentos

| ID | Documento | Leitura obrigatória |
|---|---|---|
| F00 | [Propriedade das redes Docker](foundation-f00-docker-network-ownership.pt-BR.md) | Nenhuma |
| F01 | [Modelo de prontidão funcional](foundation-f01-functional-readiness-model.pt-BR.md) | Nenhuma |
| F02 | [Alcance do plano de usuário e da DN](foundation-f02-dn-reachability.pt-BR.md) | F00 |
| F03 | [Regras de operação do RFsim com múltiplas células](foundation-f03-rfsim-multicell-operations.pt-BR.md) | F00 |
| F04 | [Enumerações de configuração e temporização de rádio na OAI](foundation-f04-oai-config-enums-and-timing.pt-BR.md) | Nenhuma |

## Trilhas de leitura recomendadas

### Handover F1 em RFsim

`F00 → F01 → F02 → F03 → F04 →` [pipeline de medição](guide-measurement-pipeline.pt-BR.md) `→` [tutorial F1](tutorial-f1-handover.pt-BR.md)

### Handover N2 monolítico em RFsim

`F00 → F01 → F02 → F03 → F04 →` [guia N2](guide-n2-handover.pt-BR.md) `→` [pipeline de medição](guide-measurement-pipeline.pt-BR.md) `→` [tutorial monolítico](tutorial-n2-monolithic-handover.pt-BR.md)

### Handover N2 CU/DU em RFsim

`F00 → F01 → F02 → F03 → F04 →` [guia N2](guide-n2-handover.pt-BR.md) `→` [pipeline de medição](guide-measurement-pipeline.pt-BR.md) `→` [tutorial CU/DU](tutorial-n2-cu-du-handover.pt-BR.md)

### USRP X310 com um UE comercial (COTS)

`F00 → F01 → F04 →` [guia USRP de célula única](guide-usrp-x310-cots.pt-BR.md) `→` [guia de handover distribuído](guide-usrp-distributed-handover.pt-BR.md)

Quando uma execução OTA se comportar mal, consulte o catálogo de solução de problemas da OAI no repositório complementar `cerise_nobre` (`oai/docs/oai_troubleshooting_testbed.md`) e faça um grep pela string de log que você está vendo. Veja as [Referências externas](#referências-externas) abaixo.

## Guias e tutoriais

- [Pipeline de medição e ciclo de vida das execuções](guide-measurement-pipeline.pt-BR.md)
- [Guia do testbed de handover N2](guide-n2-handover.pt-BR.md)
- [Guia USRP X310 + UE COTS](guide-usrp-x310-cots.pt-BR.md)
- [Guia de handover distribuído com USRP](guide-usrp-distributed-handover.pt-BR.md)
- [Tutorial de handover F1 em RFsim](tutorial-f1-handover.pt-BR.md)
- [Tutorial de handover N2 monolítico em RFsim](tutorial-n2-monolithic-handover.pt-BR.md)
- [Tutorial de handover N2 CU/DU em RFsim](tutorial-n2-cu-du-handover.pt-BR.md)

## Relatórios, registros e handoffs

Estes documentos fornecem evidências ou contexto histórico. Eles não são pré-requisitos sequenciais, a menos que outro documento os liste explicitamente.

- [Resultados de referência](report-baseline-results.pt-BR.md)
- [Relatório da correção de inicialização e prontidão da F1 em RFsim](report-f1-rfsim-readiness-fix.pt-BR.md)
- [Avaliação do repositório: práticas, padrões e experiência de uso](report-repository-evaluation.pt-BR.md)
- [Relatório da correção do SMF para DNN com IPv4v6](report-smf-ipv4v6-dnn-fix.pt-BR.md)
- [Histórico de desenvolvimento](record-development-history.pt-BR.md)
- [Registro da visão geral do operador da Fase 6 do painel](record-dashboard-phase6-overview.pt-BR.md)
- [Handoff da integração com xApp](handoff-xapp-integration.pt-BR.md)
- [Handoff da implementação das correções da avaliação](handoff-evaluation-remediation.pt-BR.md)
- [Handoff da visão geral ao vivo do painel](handoff-dashboard-overview-live.pt-BR.md)
- [Handoff da falha de autenticação no teste rápido F1 (resolvido)](handoff-f1-smoke-auth-failure.pt-BR.md)

## Referências externas

O conhecimento sobre a OAI que vale para mais de um testbed fica deliberadamente fora deste repositório, no
repositório complementar `cerise_nobre`, em `oai/` (`github.com/fsnobre/cerise_nobre`,
clonado no Mini PC em `../cerise_nobre`; ele absorveu o antigo repositório `cerise_oai` em
26/10/2026). Os caminhos da tabela abaixo são relativos a `oai/`. Mantenha lá o material geral de OAI/ORANSlice e aqui o material
específico do testbed.

| Documento | Finalidade |
|---|---|
| `docs/oai_troubleshooting_testbed.md` | Falhas OTA recorrentes indexadas pela string de log da OAI, com causas confirmadas e hipóteses descartadas. **Comece por aqui quando uma execução se comportar mal.** Amplie-o em vez de refazer um diagnóstico. |
| `docs/oai_gnb_yaml_testbed.md` | Valores de referência dos parâmetros da gNB para este hardware |
| `docs/oai_gnb_yaml_general.md` | Referência de parâmetros da gNB independente de fabricante |
| `docs/nr_prb_frequency_reference.md` | Tabelas de PRB / largura de banda / ARFCN |
| `docs/oai_handover_{n2,xn,intra_gnb,ric}.md` | Variantes de handover, incluindo o mapeamento de IEs do E2SM-RC |
| `docs/oai_f1_split_*.md`, `docs/oai_oru_fronthaul_*.md` | Divisão F1 e fronthaul da ORU |
| `scripts/validate_gnb_yaml.py` | Validador estático da coerência dos parâmetros YAML/conf da gNB |
| `scripts/collect_*.sh` | Coletores de diagnóstico (gNB, CN, FlexRIC, estação de trabalho, FN990) |

## Especificações

- [Especificação do painel](spec-dashboard.pt-BR.md)

## Convenção de nomes

```text
foundation-fNN-<tema>.md   Conceito fundamental ou regra de operação estável
guide-<tema>.md            Guia operacional ou conceitual amplo
tutorial-<tema>.md         Procedimento executável orientado a um objetivo
spec-<tema>.md             Especificação de projeto
report-<tema>.md           Relatório de resultados, investigação ou validação
record-<tema>.md           Registro histórico
handoff-<tema>.md          Contexto preparado para repasse a outra frente de trabalho
```

Todo novo guia ou tutorial deve declarar sua leitura obrigatória perto do início e apontar diretamente para os documentos de pré-requisito.
