# Avaliação do repositório: práticas, padrões e experiência do usuário

> Tradução para o português. O original em inglês é o [report-repository-evaluation.md](../en/report-repository-evaluation.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Relatório
>
> **Data:** 03/07/2026
>
> **Contexto:** revisão do repositório inteiro — automação, pipeline de medição, conjunto de documentação e painel — comparado com as boas práticas de engenharia de software, os padrões do setor e a experiência de uso do operador/pesquisador.

## 1. Escopo e método

Este relatório avalia tudo o que foi construído neste repositório até agora:

- a automação de handover em RFsim (`scripts/`, `tools/`, `experiments/`, `oai-cn5g/`);
- o pipeline de medição e seus artefatos de resultado (`results/`);
- o conjunto de documentação (`docs/`);
- o painel web (`dashboard/backend`, `dashboard/frontend`);
- a higiene do repositório (histórico do git, regras de ignore, licenciamento, CI, ferramentas).

Cada área é avaliada sob três óticas: **boas práticas** (um engenheiro sênior aprovaria isto?), **padrões do setor** (o que fazem projetos open source comparáveis de telecom/testbed) e **experiência do usuário** (um pesquisador ou operador de demonstração usando-o pela primeira vez). Ao final, os achados são ordenados em recomendações priorizadas.

**Veredito geral:** este é um testbed de pesquisa excepcionalmente disciplinado. A metodologia de medição, a modelagem de prontidão, a postura de segurança das ações do painel e a arquitetura da documentação estão todas *acima* do padrão dos repositórios de testbeds acadêmicos — várias práticas daqui (verificações de validade, telemetria rotulada por confiança, resultados validados e curados) merecem ser publicadas como metodologia por si sós. As lacunas se dividem em duas famílias: **infraestrutura do projeto** (sem CI, sem licença, histórico do git ruidoso, ferramentas de teste fora do padrão, tags de imagem mutáveis, um índice de documentação desatualizado) e **paridade de cobertura** — o cockpit do painel atende apenas F1 em RFsim, enquanto a automação subjacente já suporta N2 e (parcialmente) rádio real com USRP (Seção 7).

---

## 2. Automação (`scripts/`, `tools/`)

### O que está bem feito

- **Disciplina em shell.** Todo script usa `set -euo pipefail`, resolve caminhos a partir de `BASH_SOURCE` e carrega um único `lib.sh` compartilhado (570 linhas) para seleção de topologia, auxiliares de prontidão e validação de rede. A configuração está corretamente em camadas: argumento de CLI → variável de ambiente → padrão do `config.yaml` → valor fixo de último recurso (veja a cascata `IPERF_*` em `run_smoke_test.sh`). Isso é configurabilidade no estilo 12-factor, de manual, para ferramentas em shell.
- **"Nunca usar sleep e torcer."** O princípio de projeto declarado — consultar uma condição observável em vez de usar atrasos fixos — é de fato seguido. Os únicos `sleep` fixos são janelas de medição deliberadas, e a documentação diz isso explicitamente. A maioria dos repositórios de testbed erra nisso.
- **Registros de resultado à prova de falhas.** O `run_smoke_test.sh` instala `trap finish_summary EXIT` logo após criar o diretório da execução, de modo que *todo* caminho de saída produz um `summary.json` com verificações booleanas de progresso. Uma execução que morre no meio ainda deixa um registro estruturado de até onde chegou. É um padrão realmente forte.
- **Prontidão em camadas (F01).** O modelo de prontidão em oito camadas (host → contêiner → transporte → rádio → plano de controle → sessão → plano de usuário → handover), com não implicações explícitas (`container running != RFsim connected` etc.), é a espinha dorsal intelectual da automação e está corretamente codificado em `preflight_check.sh` / `up.sh` / `status.sh` / `wait_ue_data_ready.sh`, com separação clara de responsabilidades.
- **Diagnóstico como ferramenta de primeira classe.** O `diagnose_dn_reachability.sh` é somente leitura, grava evidências estruturadas em `results/diagnostics/` e distingue `tool_missing` de uma falha real de alcance — um ponto sutil de correção (o contêiner da UPF não tem `ping`) que foi descoberto da maneira difícil e depois institucionalizado.
- **Catálogo de falhas do preflight.** A tabela de modos de falha do README (roteamento por Tailscale/WireGuard, contêineres antigos, módulos TUN/SCTP ausentes, AppArmor, relógio dessincronizado) corresponde um a um às verificações automatizadas do preflight. Codificar modos de falha operacional conhecidos como verificações executáveis é exatamente o que a automação de testes industrial faz.

### Lacunas

- **Nenhum `shellcheck` em lugar algum.** Ele não está instalado no host de desenvolvimento e nada o executa. Para ~3.300 linhas de bash em 23 scripts, a análise estática é o filtro de defeitos mais barato disponível. (Prioridade: alta, custo trivial.)
- **Nenhum teste no nível dos scripts.** A camada de bash só é verificada executando o testbed real. A maior parte do `lib.sh` (leitura de topologia, leitores de configuração, validação da especificação de rede) é lógica pura, que poderia ser exercitada por um arquivo de teste rápido em bats-core ou até em bash puro, sem Docker.
- **Os parsers de `tools/` não têm testes unitários.** O `parse_ping.py` calcula a métrica de pesquisa principal (`estimated_interruption_ms`) e já teve um bug real (contaminação pelas estatísticas da pré-verificação, corrigido e documentado). Ainda não há um teste de regressão que fixe essa correção com um fixture sintético de `ping_raw.log` + `events.csv`. Para uma métrica que vai aparecer em publicações, um teste com arquivo de referência (golden file) é o patamar padrão.
- **Contrato frágil do nome do evento.** A estimativa da interrupção vira `null` silenciosamente se `handover_trigger_start` for renomeado algum dia. O guia documenta isso ("mantenha o nome do evento estável"), o que é bom, mas uma constante compartilhada (definição única consumida por `trigger_handover.sh` e `parse_ping.py`) ou um aviso do parser quando o events.csv contiver eventos com cara de handover sem nome reconhecido transformaria uma armadilha documentada num contrato garantido.

---

## 3. Metodologia de medição e rigor científico

### O que está bem feito

- **"Confiável ou explicitamente inválido — nunca silenciosamente errado."** As verificações de validade (`ping_metrics_valid`, `packets_transmitted != 0`) são refeitas após o processamento, e uma execução com o comando de handover enviado, mas sem amostras utilizáveis, é *reprovada*, com um evento `ping_metrics_invalid`. O erro silencioso é a falha mais comum dos pipelines de medição acadêmicos; este repositório foi projetado explicitamente contra isso.
- **Contabilidade honesta da resolução.** A documentação afirma claramente que o intervalo de 0,2 s do ping limita a estimativa da interrupção, que o RTT inclui ruído do RFsim/Docker/escalonamento do host e que uma única execução por topologia é uma verificação de sanidade, e não uma referência. O `report-baseline-results.md` congela os números históricos somente com ping e se recusa explicitamente a misturar retroativamente dados de iperf ("uma nova referência com iperf e várias execuções deve ser registrada separadamente"). Essa é a prática correta de proveniência de dados.
- **Resultados validados e curados.** O `results/validated/2026-06-19/` versiona um conjunto de referência escolhido, enquanto o `.gitignore` exclui a saída bruta das execuções. Separar "evidências que defendemos" de "artefatos de trabalho" é o que as diretrizes de reprodutibilidade (por exemplo, os selos de artefato da ACM) pedem.
- **Estatística tratada com honestidade no painel.** Valores nulos são excluídos das estatísticas das campanhas, em vez de convertidos; p95 por posição mais próxima (nearest-rank); resultados determinísticos; artefatos malformados geram avisos, nunca valores fabricados.

### Lacunas

- **Tamanho das amostras e incerteza.** A referência publicada tem n=5, com média/desvio-padrão/mín./máx. A documentação já reconhece que um estudo comparativo real exige tentativas repetidas a partir de partida a frio e intervalos de confiança — as ferramentas suportam `RUNS=20`; o que falta é simplesmente executar e documentar uma referência maior, com ICs (e fazer o agregador de execuções repetidas emitir um intervalo de confiança junto com média/desvio-padrão tornaria isso automático).
- **Tags de imagem mutáveis prejudicam a reprodutibilidade.** Todas as imagens da OAI estão fixadas em `:develop` (e `ims:latest`). O próprio guia de medição lista "digests de imagem fixados" como requisito para um estudo real, e a linha "OAI version v2.4.0" da tabela do README não corresponde às tags `develop` realmente usadas nos arquivos Compose. Recomendação: fixar por digest (`image: oaisoftwarealliance/oai-gnb@sha256:…`) ou, no mínimo, por uma tag de versão fixa, registrar os digests no `summary.json` de cada execução e corrigir a afirmação do README.
- **A semântica da resolução da interrupção merece um documento.** A nova medição de interrupção em alta taxa (sondas a cada 10 ms via `scripts/measure_interruption.sh` e o cartão da Visão geral) resolve o problema de resolução, mas a regra de interpretação principal — *uma estimativa ≈ um intervalo de sonda com 0% de perda significa um handover sem interrupção, e não uma interrupção real; icmp_seq faltando é o sinal honesto de interrupção* — hoje só existe no histórico das sessões. Ela deve ser escrita no `guide-measurement-pipeline.md` (e, idealmente, exibida na interface) antes que alguém cite esses números.

---

## 4. Documentação (`docs/`)

### O que está bem feito

- **Uma arquitetura de informação de verdade.** A taxonomia baseada na finalidade (`foundation-fNN` / `guide` / `tutorial` / `report` / `record` / `handoff`), com IDs estáveis para os fundamentos, cabeçalhos explícitos de "leitura obrigatória" e trilhas de leitura por objetivo em `docs/en/README.md`, é um equivalente caseiro do framework Diátaxis e está mais bem organizada do que a documentação da maioria dos projetos open source consolidados. A regra "IDs são identificadores, não níveis de dificuldade; nunca renumere" mostra uma intenção real de curadoria.
- **Os fundamentos registram o *porquê*, e não só o *como*.** F00 (propriedade das redes: por que `docker network create` à mão é uma armadilha), F01 (invariantes de prontidão), F04 (valores de configuração que são índices de enumeração, como `ra_ResponseWindow = 4` significando 10 slots) — cada um registra uma classe de erro e a regra que o evita. Isso é memória institucional bem feita.
- **A justificativa essencial está escrita.** A separação entre os arquivos da pré-verificação e da captura longa está documentada *junto com a condição de corrida que ela evita*; a dependência do nome do evento está sinalizada; a restrição do UE como servidor RFsim e seu teto para múltiplos UEs são apontados no handoff da xApp. Um novo colaborador consegue entender por que o código tem a forma que tem.
- **Documentos de handoff como gênero.** O `handoff-xapp-integration.md` (contexto para uma frente de pesquisa futura, com um plano de integração E2/FlexRIC em fases e riscos nomeados) e o handoff da falha no teste rápido são excelentes práticas para trabalho de pesquisa com várias sessões e vários agentes.

### Lacunas

- **O índice tinha ficado desatualizado** (resolvido em 03/07/2026). Quatro documentos mais novos não seguiam a convenção de nomes nem apareciam em `docs/en/README.md`. Eles foram renomeados para `spec-dashboard.md`, `record-dashboard-phase6-overview.md`, `handoff-dashboard-overview-live.md` e `handoff-f1-smoke-auth-failure.md`, e todos estão agora indexados (uma categoria `spec-` foi adicionada à convenção de nomes).
- **Nomes numerados por fase codificam história, e não conteúdo.** "Phase 6" só tem significado para quem viveu as fases 1–5. Nomes baseados na finalidade (que a taxonomia já prescreve) envelhecem melhor; mantenha os números de fase no corpo do documento, como histórico.
- **Risco de estado desatualizado nos handoffs** (resolvido em 03/07/2026). O handoff do teste rápido F1 descrevia um bloqueio então vigente (AUSF `CONTEXT_NOT_FOUND`) que foi corrigido em seguida (PR #17); agora ele traz um aviso de resolução de uma linha. Os demais documentos de handoff/registro devem receber o mesmo tratamento quando seu problema central for resolvido, para que um leitor futuro não depure novamente um problema já corrigido.
- **O `record-development-history.md` tem formato de chat.** Ele é honesto e útil, mas escrito como narração de sessão em "você/nós". Tudo bem para um `record-`; vale saber que ele se lê como proveniência, e não como referência — o índice o classifica corretamente, então esta é uma observação menor.

---

## 5. Backend do painel

### O que está bem feito

- **O modelo de segurança das ações é o destaque.** Desabilitado por padrão; `confirm` explícito obrigatório; apenas scripts de uma lista de permissões, com argv fixo (nenhum `shell=True` em lugar algum — e os validadores *fazem asserções sobre o código-fonte* para garantir que isso continue assim); concorrência de um único job (409 em caso de sobreposição); tratamento de tempo limite por grupo de processos com SIGTERM→SIGKILL; finais de saída limitados a 200 linhas; montagem do repositório somente leitura, exceto `results/`; endpoint de capacidades que *informa suas próprias garantias de segurança*. Essa é uma postura de execução de comandos melhor do que a de muitas ferramentas internas comerciais.
- **Projeto voltado primeiro para o modo degradado.** O backend precisa iniciar e continuar útil com o testbed desligado, o socket do Docker quebrado, o telnet indisponível ou artefatos malformados — tudo exposto como aviso, nunca como falha. Os validadores testam explicitamente os casos de artefato vazio/malformado/ausente.
- **Telemetria epistemicamente honesta.** A taxonomia de confiança `observed / parsed / inferred / unknown`, a separação rigorosa entre "eventos de registro no AMF vistos nos logs" e "número de UEs conectados atualmente" e a regra de que uma DU servidora não observada aparece como "DU not observed", em vez de um caminho inventado `UE → Unknown → CU` — esse é um padrão de honestidade de nível de pesquisa que quase nenhum painel atinge. Deve ser mantido como invariante rígido.
- **Lições operacionais registradas no código.** A consulta passiva ao telnet da CU fica desativada por padrão porque sondagens `help` repetidas derrubavam a CU da OAI (`*** buffer overflow detected ***`); quando ativada, ela tem limite de taxa e descoberta de capacidades em cache. Os caminhos de bind mount visíveis no host para ações adjacentes a Docker-in-Docker estão documentados com um override de Compose funcional.

### Lacunas

- **Sem autenticação e com `allow_origins=["*"]`.** Isso está documentado com honestidade ("não exponha em redes não confiáveis quando as ações estiverem habilitadas") e é aceitável para um laboratório de um único host. Mas o modo com ações habilitadas comanda o daemon Docker do host; o próximo passo padrão é barato: um token bearer estático (variável de ambiente, verificado por middleware em `/api/actions/*` e `/ws`) e uma lista de origens CORS cujo padrão seja a origem do frontend. Isso converte um aviso documentado num controle efetivo.
- **Validadores próprios em vez de pytest.** `validate_phase2..6.py` + `validate_registry.py` são testes reais com boa cobertura, mas o executor sob medida já causou uma falha mascarada (um `AssertionError` que saiu com código 0 durante o próprio desenvolvimento deste projeto). Portar as funções para pytest é quase mecânico (elas já parecem funções de teste), traz relatórios granulares, seleção com `-k`, fixtures e elimina a classe de bugs de código de saída. Mantenha a verificação de divergência do `validate_registry.py` — essa ideia (comparar o registro de contêineres do painel com os arquivos Compose reais) é excelente.
- **Arquivos de teste numerados por fase.** O mesmo problema de acúmulo da documentação: `validate_phase4.py` diz *quando* foi escrito, e não *o que* protege. Renomeie por assunto (`test_actions.py`, `test_campaigns.py`, …) durante a migração para pytest.
- **O estado dos jobs fica só em memória** e é zerado ao reiniciar (documentado). Tudo bem por enquanto; se as campanhas passarem a durar mais do que o tempo de atividade do backend, persista registros mínimos dos jobs em `results/`.

---

## 6. Frontend do painel e experiência do operador

### O que está bem feito

- **A Visão geral como cockpit é a escolha certa.** O redesenho da Fase 6 foi guiado por feedback real do operador (eliminar cartões duplicados, agrupar recolhíveis, remover selos desatualizados, substituir uma enganosa "duração do handover ao vivo" por um gráfico de entrega de pacotes ao vivo) e, o que é crucial, o *raciocínio* foi registrado. Iterar uma interface de monitoramento a partir do uso real em demonstrações é o caminho padrão do setor; documentar cada iteração é mais raro.
- **Visualização fiel.** O gráfico de latência ao vivo renderiza as sondas perdidas como lacunas/marcadores, em vez de interpolar entre elas; o novo gráfico de interrupção interrompe a linha nos icmp_seq faltantes (`connectNulls=false`) e marca o disparo com uma linha de referência e a lacuna com uma faixa sombreada. Não mentir por interpolação é a regra mais importante de integridade de gráficos, e ela é seguida.
- **Estados vazios e indisponíveis são projetados, e não acidentais** ("No live latency samples yet…", rótulos Unavailable, ressalvas sobre KPIs sintéticos do RFsim). O checklist de validação exige explicitamente que a Visão geral seja renderizada com a pilha desligada e sem nenhuma execução histórica.
- **Pilha sensata e enxuta.** React 18 + Vite + Recharts + Tailwind, sem framework de gerenciamento de estado de que o aplicativo não precisa, WebSocket para push e REST para artefatos, artefatos grandes deliberadamente mantidos fora do socket.

### Lacunas

- **Zero testes de frontend e nenhum lint.** Não há configuração de ESLint/Prettier nem executor de testes no `package.json`. A regressão de estado vazio detectada manualmente nesta semana (`data.length` vs. `visibleSamples.length` após o preenchimento da janela) é exatamente o tipo de bug que um teste de componente fixaria. Patamar mínimo: ESLint + alguns testes com Vitest/react-testing-library para os auxiliares de transformação de dados (`buildInterruptionResult`, leitura do marcador de ID de execução, preenchimento da janela) — são funções puras e trivialmente testáveis.
- **Ferramentas de build no bloco de dependências errado.** `vite` e `@vitejs/plugin-react` estão em `dependencies`, em vez de `devDependencies`. É cosmético num build Docker, mas descreve mal o tamanho do ambiente de execução.
- **Os componentes de página estão crescendo demais.** O `Overview.jsx` tem ~490 linhas e o `CampaignsPage.jsx` ~425, reunindo busca de dados, transformação e apresentação. Extrair as funções puras de transformação de dados para `src/utils/` encolheria as páginas e as tornaria testáveis (a mesma refatoração atende às duas lacunas).
- **Oportunidades de polimento de UX** (pequenas, em ordem de impacto):
  1. Mostrar a interpretação "≤ um intervalo de sonda + 0% de perda ⇒ nenhuma interrupção mensurável (sem interrupção)" diretamente no cartão de interrupção, para que o operador não possa interpretar 11 ms como uma interrupção real.
  2. Persistir os últimos resultados vistos (por exemplo, `localStorage` ou buscar novamente a última execução ao montar) para que atualizar a página não esvazie o cartão de interrupção.
  3. Uma indicação visível de "ações desabilitadas" que diga *como* habilitá-las (o comando exato com a variável de ambiente), e não apenas um botão desabilitado.

### Revisão da interface e do design visual

O repositório não tem requisitos de design declarados; por isso, esta seção avalia a interface segundo as boas práticas gerais de design e nomeia as técnicas que a melhorariam. O visual atual — base em ardósia escura (`#0f172a`/`slate-950`), cartões com efeito de vidro (`rounded-2xl border-white/10 bg-white/[0.06]`), um único acento ciano, tons de status esmeralda/âmbar/rosa, fonte monoespaçada para valores técnicos, microrrótulos em maiúsculas espaçadas — já é coerente e adequado para um console de operações. A direção de design da especificação do painel ("denso, mas organizado, ferramenta de monitoramento para pesquisadores") está sendo seguida. O que segue é como passar de "limpo" para "bem projetado":

1. **Introduzir design tokens (a técnica de design de maior alavancagem aqui).** Hoje as cores estão fixas em cada arquivo: hexadecimais de gráfico (`#22d3ee`, `#fb7185`, `#94a3b8`) dentro das props do Recharts, cores de status duplicadas entre `StatusDot`, `Pill` e os marcadores dos gráficos, e apenas uma classe compartilhada (`.card`). Defina tokens semânticos uma única vez — `status-ok`, `status-warn`, `status-bad`, `accent`, `text-muted`, mais uma pequena paleta de gráficos — no tema do Tailwind e num pequeno `chartTheme.js`, e consuma-os em todo lugar. Isso torna toda página futura consistente por padrão, e não por disciplina, e faz de um tema claro ou de um estilo para impressão/exportação uma troca de tokens, e não uma reescrita.
2. **A acessibilidade é o maior defeito concreto.** O `StatusDot` codifica a saúde dos contêineres apenas pela cor (verde/laranja/vermelho), o que viola o critério 1.4.1 da WCAG (uso de cor) e é indistinguível para usuários com daltonismo vermelho-verde — associe o ponto a um texto/selo curto (ele já fica ao lado do texto `health || status` nas linhas da barra lateral, então a correção consiste principalmente em garantir essa associação em todo lugar e acrescentar uma diferença de ícone/forma). Microrrótulos de ~10px em `text-slate-500` (`#64748b`) sobre quase preto estão no limite do contraste AA da WCAG para texto pequeno — passe para `slate-400` e ≥11px. Adicione `aria-expanded` nos cartões recolhíveis da barra lateral, `aria-current` na aba de navegação ativa e anéis `focus-visible` visíveis (o tema escuro torna o contorno de foco padrão quase invisível). Técnica: adotar as primitivas do Radix UI (ou shadcn/ui) para abas/recolhíveis/toasts — elas trazem o comportamento correto de teclado e ARIA de graça, mantendo o estilo Tailwind existente.
3. **Adicionar roteamento por URL.** A navegação é `useState("Overview")` — atualizar a página devolve o operador à Visão geral, nenhuma página ou execução pode ter link direto ou ser compartilhada, e o botão voltar do navegador não faz nada. Uma ferramenta de monitoramento vive de URLs compartilháveis (`/runs/<id>`, `/campaigns/<id>`). O `react-router`, com uma rota por página mais rotas com parâmetro para o detalhe de execuções/campanhas, é uma mudança de meio dia e a maior melhoria de usabilidade disponível.
4. **Estabelecer hierarquia visual em torno dos números que importam.** A métrica de pesquisa principal da Visão geral — a interrupção em ms — aparece como uma pequena pílula, enquanto um parágrafo de destaque quase estático recebe o maior texto da página. Inverta isso: substitua o texto de destaque por uma faixa de KPIs com blocos de estatística (saúde da pilha, DU servidora, última interrupção, estado da entrega ao vivo, perda de pacotes) usando numerais grandes com rótulos pequenos, e deixe a prosa explicativa em tooltips/legendas. A boa prática em consoles densos é "a maior tinta = o valor mais importante".
5. **Consolidar o código dos gráficos.** O `LiveLatencyChart` e o gráfico de interrupção duplicam eixos, tooltip, arredondamento do y máximo e estilo das linhas, com pequenas divergências. Extraia um `RttChart` compartilhado (eixos, formatação do tooltip, props de anotação de lacuna/disparo) — isso traz consistência visual, reduz o código pela metade e oferece um único lugar para corrigir problemas comuns a todos os gráficos. Melhorias específicas dos gráficos: no traçado denso de 10 ms, retire os pontos individuais (`dot={false}` com `activeDot`) — 600 pontos com r=2 são ruído visual e custo de renderização; dê ao gráfico ao vivo um eixo de tempo real (hoje ele plota índices de posição, com rótulos de marcação quase vazios); quando um handover rápido for disparado, anote o instante do disparo também no gráfico *ao vivo* (o backend sabe o horário de início do job), ligando os dois cartões; e use uma forma de marcador distinta (e não só a cor) para as sondas perdidas.
6. **Promover as primitivas definidas localmente.** `Pill` e `Detail` são definidos dentro do `Overview.jsx`; outras páginas vão reimplementar (ou já reimplementam) variantes. Mova-os para `components/`, ao lado de `StatusDot`/`MetricCard`, e faça deles a única forma de renderizar chips de status e detalhes chave-valor.
7. **Tipografia.** A especificação pede Inter + JetBrains Mono; hoje o aplicativo usa os padrões do sistema. Hospede ambas localmente via `@fontsource` (sem dependência de CDN, adequado para laboratórios offline) — numerais tabulares monoespaçados, em particular, impedem que a pílula de RTT ao vivo oscile de largura conforme os valores mudam.
8. **Detalhes de layout.** A barra lateral fixa `w-80` não é recolhível e a grade de duas colunas só se divide em `xl` — num laptop típico de 1366px, tudo fica empilhado. Torne a barra lateral recolhível (ela já tem recolhimento por cartão; acrescente o recolhimento do trilho inteiro) e ajuste o ponto de quebra para `lg`. Mantenha a filosofia atual de densidade de informação; não acrescente decoração.

Nada disso é um redesenho — a estética está boa. É sistematização: tokens, semântica de acessibilidade, roteamento, hierarquia e primitivas compartilhadas.

---

## 7. Paridade de cobertura de topologias e rádio (só F1 vs. N2, RFsim vs. USRP)

A camada do testbed suporta três topologias de handover em RFsim, mais a operação com rádio real USRP X310. O painel — e especialmente o cockpit da Visão geral — atende hoje **uma** dessas combinações: F1 em RFsim. Essa assimetria é a maior lacuna *funcional* do projeto, e vale descrevê-la com precisão, porque parte dela é trivial de fechar e parte é um problema real de projeto.

### 7.1 Suporte à N2 na Visão geral (barato de fechar)

Estado atual, verificado no código:

- O `actions.py` fixa `"f1"` no argv do disparo (`trigger_handover.sh f1`) e no argv da captura da interrupção (`measure_interruption.sh f1`).
- A Visão geral condiciona tanto o disparo rápido quanto o cartão de interrupção a `topology === "f1"`, e o destaque se intitula "F1 RFsim handover cockpit".
- O parser de configuração do backend retorna `not_implemented_in_phase_1` para topologias que não são F1, de modo que as pilhas N2 recebem o status dos contêineres, mas nenhuma configuração processada nem detalhes no diagrama de topologia.

Enquanto isso, a *automação subjacente já suporta tudo isso*: o `trigger_handover.sh` trata as três topologias (com detecção automática e as substituições `N2_SOURCE_GNB_TELNET_HOST`/`N2_TARGET_PCI`/`N2_UE_RRC_ID`), o `measure_interruption.sh` recebe um argumento de topologia e calcula a tag da execução para as três, e as ações de teste rápido/teste rápido repetido já aceitam `n2-monolithic`/`n2-cu-du`. A restrição a F1 está quase toda na camada do painel. Para fechá-la:

1. Fazer `build_trigger_handover_command` e `build_measure_interruption_command` receberem a topologia *detectada* (o backend já calcula `active_topology()`), mantendo a validação existente pela lista de permissões.
2. Tornar a Visão geral sensível à topologia: título dinâmico, rótulo de botão dinâmico ("Trigger N2 handover → PCI 1") e indicadores de suporte por topologia em `/api/actions/capabilities`, em vez de uma verificação `=== "f1"` no frontend.
3. Estender o parser de configuração/diagrama de topologia aos dois formatos N2 (2 gNBs; 2 pares CU+DU) — as entradas do registro para descoberta de contêineres já existem.

Com a N2 vem um problema de UX genuinamente novo, que merece projeto, e não apenas ligação: o **sentido**. Após um handover N2, o UE fica na gNB de destino, de modo que um segundo disparo no mesmo sentido silenciosamente não faz nada ou falha; a automação resolve isso com `RESET_BETWEEN_RUNS=1`. A Visão geral deve mostrar a célula servidora atual (da forma honesta, rotulada por confiança, como já faz com a DU servidora na F1) e oferecer um disparo sensível ao sentido (seleção de PCI de origem/destino, limitada e validada no servidor, como o parâmetro de número de repetições) ou informar claramente ao operador que é preciso reinicializar antes de disparar de novo. Qualquer coisa a menos produzirá demonstrações confusas, em que "o disparo não fez nada".

### 7.2 USRP / rádio real (um problema real de projeto; fazer em fases)

O painel não tem noção do `usrp-cots` nem das topologias distribuídas `usrp_handover` e — mais fundamentalmente — seus dois recursos característicos da Visão geral se apoiam em premissas do RFsim:

- A sonda de latência ao vivo e a captura da interrupção medem ambas *de dentro do contêiner `oai-nr-ue`* (`docker exec oai-nr-ue ping -I oaitun_ue1 …`). Com um celular COTS não há contêiner de UE, nem `oaitun_ue1`, nem shell no UE. A documentação já reconhece isso ("a medição do plano de dados a partir do aparelho é manual; os testes rápidos automatizados funcionam apenas com rfsim") — o ponto aqui é que os recursos principais do painel herdam essa limitação por inteiro.
- O monitor do Docker observa apenas o socket *local*. Na implantação distribuída com um rádio por host, cada nó da RAN fica num host diferente, de modo que o painel mostraria uma RAN vazia/vermelha mesmo com o testbed saudável.

Fases recomendadas, da mais barata para a mais cara:

1. **`usrp-cots` em um único host (principalmente ligação).** Registrar a topologia, mostrar a saúde do contêiner da gNB, a associação NG e os eventos de registro nos logs do AMF (todos já coletáveis localmente). Suprimir com honestidade os cartões baseados no contêiner do UE ("COTS UE — no in-container probe available"), em vez de mostrá-los quebrados.
2. **Reorientar a Visão geral de rádio real para as métricas que se tornam *reais*.** No RFsim, os KPIs de RF (CQI, RSRP, BLER, MCS) são sintéticos e o painel corretamente os deixa em segundo plano; em rádio real, eles são os dados interessantes, e as estatísticas de MAC pelo telnet da gNB passam a ter valor real. O consultor de telnet existente, com limite de taxa (hoje desativado por padrão por motivos de estabilidade da CU), é a fonte natural; as estatísticas de MAC por UE do lado da gNB funcionam independentemente do tipo de UE. Sinais de saúde do rádio (contagens de underflow/overflow nos logs da gNB) também pertencem a essa Visão geral — são o modo de falha da USRP que o operador de fato acompanha.
3. **A medição do plano de usuário com um UE COTS exige um novo projeto de medição, e não uma adaptação.** Opções realistas, em ordem crescente de esforço: sondagem de downlink a partir do `oai-ext-dn` para o IP do celular atribuído pela UPF (só funciona se o aparelho responder ICMP — muitos não respondem); contadores de sessão da UPF/SMF como substituto da entrega; ou um pequeno aplicativo agente de medição no celular (servidor iperf3 / eco UDP), que é a única forma de obter um número de interrupção comparável à referência em RFsim. Isso é trabalho de roteiro — o README já lista "medição automatizada a partir de um UE COTS" como marco futuro —, mas o ponto *no nível deste relatório* é: não apresente os números de interrupção em RFsim e os futuros números em rádio real como a mesma métrica sem documentar a diferença no caminho de medição.
4. **A visibilidade distribuída é o maior esforço e deve ser delimitada deliberadamente.** Opções: uma instância do painel por host (funciona hoje, sem código, UX ruim); consulta remota de contêineres via SSH/`docker context`; ou um agente de status leve por host. Observe que o caminho das *ações* já está pronto para o modo distribuído — as substituições por variáveis de ambiente do `trigger_handover.sh` alcançam endpoints telnet remotos pela LAN —, então existe um meio-termo em que um único painel pode disparar e observar o handover numa implantação distribuída, enquanto a saúde dos contêineres continua sendo por host.

### 7.3 A mesma ótica aplicada fora do painel

O viés de F1/RFsim primeiro é mais brando no restante do repositório, mas existe: o relatório de referência e os resultados validados são centrados na F1 (há execuções validadas únicas para as topologias N2; nenhuma referência N2 repetida foi publicada), e a nova captura de interrupção em alta resolução só foi exercitada na F1, embora o script aceite as três topologias. Uma referência N2 repetida (as duas variantes, com reinicializações) tornaria empiricamente simétrica a afirmação do repositório sobre as três topologias, e é puro tempo de máquina com as ferramentas existentes.

## 8. Higiene do repositório, git e infraestrutura do projeto

É aqui que o repositório mais diverge do padrão do setor, e cada item é barato de corrigir.

- **Sem CI.** O repositório tem um excelente conjunto de validação (`compileall`, seis validadores, verificação de divergência do registro, build do frontend, `docker compose config`, validação do seed de assinantes — todos listados em `dashboard/README.md`) e *nada o executa automaticamente*. Um único workflow do GitHub Actions executando exatamente essa lista, mais `shellcheck scripts/*.sh` e `bash -n`, teria detectado as quebras de propagação de construtor e de conjunto de verificações fixado que já ocorreram na prática. Essa é a melhoria isolada de maior alavancagem disponível.
- **Sem LICENSE.** No GitHub, ausência de licença significa todos os direitos reservados: ninguém pode legalmente reutilizar este testbed nem citá-lo e construir sobre ele, o que anula o propósito de um artefato de pesquisa. Os componentes da OAI estão sob a OAI Public License / próxima da Apache; a automação em si pode ser Apache-2.0 ou MIT. Adicione um arquivo.
- **Ruído no histórico do git.** 14 dos 57 commits em `main` são commits automáticos com mensagem "." intercalados com o trabalho real baseado em PRs. Isso destrói a possibilidade de bisect e torna o `git log` ilegível. Aponte a ferramenta de commit automático para um branch de rascunho (ou desative-a) e mantenha a `main` apenas com PRs. Além disso: crie tags para as referências validadas (`baseline-2026-06-19`), para que os números publicados fiquem fixados num commit.
- **O `.gitignore` são dois modelos concatenados.** O modelo Python do GitHub e um bloco local foram colados juntos, duplicando `results/runs/*`, `__pycache__/`, `.venv/` etc. — e, apesar das ~300 linhas, **`node_modules/` não é ignorado** (ele aparece como não rastreado neste momento, a um commit automático equivocado de distância de um commit de 200 MB). Elimine a duplicação, chegando a ~40 linhas intencionais, e acrescente `node_modules/`.
- **Estrutura morta** (resolvido em 03/07/2026). `metrics/{ping,parsed,iperf}/` continha apenas `.gitkeep` — a estrutura foi substituída por `results/runs/<id>/` e foi removida. Nenhum código a referenciava.
- **Arquivos de configuração espalhados na raiz.** `conf-cu.conf`, `conf-du.conf`, `conf-nr-ue.conf` e `gnb-docker-compose.yaml` ficam na raiz do repositório, enquanto todas as outras topologias ficam em `experiments/<nome>/`. Mover os arquivos F1 para `experiments/manual_f1_handover/` (com atualização dos caminhos no `lib.sh` e no registro do painel — o validador de divergência pegará o que ficar para trás) tornaria a estrutura uniforme. Esforço médio; faça quando houver oportunidade.
- **Sem `pyproject.toml`/ruff para o código Python.** O `requirements.txt` está devidamente fixado (bom), mas não há configuração de formatador/linter para o backend nem para `tools/`. Adicionar o ruff (lint+formatação) ao workflow de CI padroniza o estilo sem custo.
- **O AGENTS.md é uma boa prática moderna** — fatos rígidos (nomes de contêineres, endpoint telnet, "não invente um comando `handover` genérico") que impedem que várias sessões assistidas por IA refaçam o raciocínio ou violem invariantes. Continue ampliando-o à medida que os invariantes se acumularem (o contrato do nome do evento `handover_trigger_start` também pertence a ele).

---

## 9. Postura de segurança

- **Pontos fortes:** nenhuma execução de comandos arbitrários; nenhuma interpolação de shell (verificado em testes); controle de ações + confirmação; montagens somente leitura; saídas limitadas; as credenciais de SIM na documentação são os vetores de teste públicos da OAI, e não segredos; os arquivos `.env` são ignorados pelo git, com `.env.example` versionado (o padrão correto para as configurações de LAN da USRP).
- **Pontos fracos:** sem autenticação + CORS curinga (Seção 5); o socket do Docker montado no contêiner do backend equivale a root no host — inerente ao projeto e aceitável para um laboratório, mas significa que o aviso "não exponha em redes não confiáveis" é essencial e deveria ser garantido pelo token recomendado acima; o nginx do frontend do painel serve sem nenhum cabeçalho de proteção (menor para uso em laboratório).

---

## 10. Recomendações priorizadas

**P0 — faça primeiro (cada uma < 1 hora):**

1. Adicionar um workflow de CI no GitHub Actions executando a lista de validação já documentada + `bash -n`/`shellcheck` + build do frontend.
2. Adicionar um arquivo LICENSE.
3. Corrigir o `.gitignore`: eliminar a duplicação e acrescentar `node_modules/`.
4. Parar os commits automáticos "." na `main` (branch de rascunho ou desativar); criar a tag `baseline-2026-06-19`.

**P1 — curto prazo (um ou dois dias no total):**

5. Estender à N2 o disparo rápido e a captura da interrupção da Visão geral (Seção 7.1): passar a topologia detectada pela lista de permissões de ações existente, tornar a Visão geral sensível à topologia e projetar a UX de sentido/reinicialização. A automação já suporta tudo isso.
6. Fixar as imagens da OAI por digest (ou tag fixa), registrar os digests no `summary.json` e conciliar a afirmação "v2.4.0" do README com a realidade.
7. Portar `validate_phase*.py` para pytest com nomes por assunto; adicionar testes com arquivos de referência para o `parse_ping.py` (incluindo um fixture de regressão para o bug de contaminação pela pré-verificação e uma interrupção sintética com sequências faltando).
8. Adicionar autenticação por token + origens CORS explícitas ao backend; manter o aviso de "não exposição" na documentação como defesa em profundidade.
9. Trazer os quatro documentos não convertidos para a convenção de nomes e indexá-los em `docs/en/README.md`; adicionar avisos de resolução aos handoffs encerrados.
10. Documentar a medição de interrupção em alta resolução (sondas a cada 10 ms, interpretação do piso de resolução, semântica de sem interrupção vs. interrupção) no `guide-measurement-pipeline.md` e exibir a mesma interpretação no cartão do painel.
11. Etapa de sistematização da interface (Seção 6): design tokens + primitivas compartilhadas de status/gráfico, correções de WCAG (indicações de status sem depender da cor, contraste, anéis de foco, ARIA em abas/recolhíveis) e roteamento por URL com links diretos para execuções/campanhas.

**P2 — quando houver oportunidade:**

12. ESLint + Vitest para o frontend; extrair os auxiliares puros de transformação de dados dos componentes de página grandes e testá-los primeiro.
13. Mover `vite`/`@vitejs/plugin-react` para `devDependencies`.
14. Registrar uma referência F1 maior (n≥20) com intervalos de confiança e uma primeira referência N2 repetida (as duas variantes, com reinicializações), para que a afirmação sobre as três topologias seja empiricamente simétrica; fazer o agregador emitir ICs.
15. Registrar o `usrp-cots` no painel, com supressão honesta dos cartões baseados no contêiner do UE; reorientar uma Visão geral de rádio real para as estatísticas de MAC via telnet e os sinais de saúde do rádio (Seção 7.2) e tratar a medição do plano de usuário com UE COTS como um esforço de projeto próprio.
16. Remover ou documentar a árvore vazia `metrics/`; considerar realocar os arquivos de configuração F1 da raiz para `experiments/`.
17. Adicionar configuração do `ruff` para o backend + tools; acrescentar o contrato do nome do evento (`handover_trigger_start`) ao AGENTS.md ou garanti-lo por meio de uma constante compartilhada.

## 11. Avaliação final

O núcleo científico deste repositório — modelagem de prontidão, verificações de validade da medição, contabilidade honesta da resolução, telemetria rotulada por confiança e um sistema de documentação com arquitetura de informação real — é mais sólido do que o da grande maioria dos testbeds de pesquisa e não precisa ser refeito. O modelo de segurança das ações no painel é pensamento de nível de produção. O que resta se divide em três grupos: infraestrutura comum de projeto de software (CI, licença, higiene do git, ferramentas padrão de teste/lint, imagens fixadas — nada arquitetural, tudo barato); uma etapa de sistematização da interface (tokens, acessibilidade, roteamento — um refinamento de um design sólido, e não um redesenho); e a paridade de cobertura, em que a metade N2 é principalmente ligação, porque a automação já fez o trabalho difícil, e a metade USRP é um problema real de projeto de medição, que deve ser feito em fases, de forma deliberada, e não adaptado ingenuamente.
