# Avaliação do repositório: práticas, normas e experiência de uso

> Tradução para o português em Linguagem Simples. O original em inglês é o [report-repository-evaluation.md](report-repository-evaluation.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** relatório
>
> **Data:** 03/07/2026
>
> **Contexto:** revisão do repositório inteiro (automação, pipeline de medição, documentação e painel web). A revisão compara o repositório com as boas práticas de engenharia de software e com as normas da indústria. Ela também avalia a experiência de quem opera o testbed ou pesquisa com ele.

## 1. Escopo e método

Este relatório avalia tudo o que foi construído neste repositório até agora:

- a automação do handover em rfsim (`scripts/`, `tools/`, `experiments/`, `oai-cn5g/`);
- o pipeline de medição e os arquivos de resultado (`results/`);
- a documentação (`docs/`);
- o painel web (`dashboard/backend`, `dashboard/frontend`);
- a organização do repositório (histórico do git, regras de ignorar, licença, CI e ferramentas).

Cada área é avaliada por três critérios:

- **boas práticas:** um engenheiro experiente aprovaria isto?
- **normas da indústria:** o que fazem projetos abertos parecidos, de telecomunicações e de testbeds?
- **experiência de uso:** como é para um pesquisador ou um operador de demonstração que usa o testbed pela primeira vez?

No final, os achados viram recomendações ordenadas por prioridade.

**Conclusão geral:** este é um testbed de pesquisa com disciplina fora do comum. A metodologia de medição, o modelo de prontidão, a segurança das ações do painel web e a organização da documentação estão *acima* do normal para repositórios de testbeds acadêmicos. Várias práticas daqui merecem ser publicadas como metodologia: as etapas de validação, a telemetria marcada com nível de confiança e os resultados validados e selecionados.

As lacunas ficam em dois grupos:

- **infraestrutura do projeto:** sem CI, sem licença, histórico do git com ruído, ferramentas de teste fora do padrão, etiquetas de imagem que mudam e índice da documentação desatualizado;
- **cobertura igual entre topologias:** o painel de comando só atende o F1 em rfsim, mas a automação por baixo já aceita o N2 e, em parte, o rádio real com USRP (seção 7).

---

## 2. Automação (`scripts/`, `tools/`)

### O que está bem feito

- **Disciplina nos scripts de shell.** Todos os scripts usam `set -euo pipefail`, encontram os caminhos a partir de `BASH_SOURCE` e carregam um único `lib.sh` compartilhado (570 linhas). Esse arquivo cuida da escolha da topologia, das funções de prontidão e da validação das redes. A configuração tem camadas na ordem certa: argumento da linha de comando → variável de ambiente → valor padrão no `config.yaml` → valor fixo de reserva. Veja a sequência das variáveis `IPERF_*` no `run_smoke_test.sh`. É a configurabilidade de manual no estilo 12-factor para ferramentas de shell.
- **"Nunca espere e torça."** O princípio declarado (esperar por uma condição observável, em vez de pausas fixas) é seguido de fato. As únicas pausas fixas são as janelas de medição planejadas, e a documentação diz isso. A maioria dos repositórios de testbed erra aqui.
- **Registros de resultado que resistem a falhas.** O `run_smoke_test.sh` instala `trap finish_summary EXIT` logo depois de criar a pasta da execução. Assim, *qualquer* saída gera um `summary.json`, com as etapas marcadas como verdadeiro ou falso. Uma execução que cai no meio ainda deixa um registro estruturado de até onde chegou. É um padrão realmente forte.
- **Prontidão em camadas (F01).** O modelo de prontidão em oito camadas é a espinha dorsal da automação: computador → contêiner → transporte → rádio → plano de controle → sessão → plano de usuário → handover. Ele declara o que uma etapa não garante (por exemplo, `container running != RFsim connected`). Ele está codificado corretamente no `preflight_check.sh`, no `up.sh`, no `status.sh` e no `wait_ue_data_ready.sh`, com papéis bem separados.
- **Diagnóstico como ferramenta de primeira classe.** O `diagnose_dn_reachability.sh` só lê, sem mudar nada. Ele grava evidências estruturadas em `results/diagnostics/`. Ele separa `tool_missing` de uma falha real de acesso. Esse detalhe (o contêiner do UPF não tem `ping`) foi descoberto da forma difícil e depois virou regra.
- **Catálogo de falhas na verificação prévia.** Cada linha da tabela de falhas do README corresponde a uma verificação automática prévia: rotas do Tailscale ou do WireGuard, contêineres antigos, módulos TUN e SCTP faltando, AppArmor, relógio fora de sincronia. Transformar falhas de operação conhecidas em verificações executáveis é exatamente o que faz a automação de testes na indústria.

### Lacunas

- **Nenhum uso do `shellcheck`.** Ele não está instalado no computador de desenvolvimento, e nada o executa. Para cerca de 3.300 linhas de bash em 23 scripts, a análise estática é o filtro de defeitos mais barato que existe. (Prioridade: alta. Custo: mínimo.)
- **Nenhum teste dos scripts.** A camada bash só é conferida com o testbed real rodando. A maior parte do `lib.sh` é lógica pura: leitura da topologia, leitura da configuração e validação das redes. Ela poderia ser testada por um arquivo rápido de bats-core, ou mesmo de bash puro, sem Docker.
- **Os analisadores de `tools/` não têm testes de unidade.** O `parse_ping.py` calcula a principal métrica da pesquisa (`estimated_interruption_ms`). Ele já teve um erro real: a mistura com as estatísticas do teste inicial, corrigida e documentada. Ainda não há um teste de regressão que fixe essa correção com um `ping_raw.log` e um `events.csv` sintéticos. Para uma métrica que vai aparecer em publicações, o padrão é um teste com arquivo de referência (*golden file*).
- **Contrato frágil do nome do evento.** A estimativa da interrupção vira `null` sem aviso se o evento `handover_trigger_start` mudar de nome. O guia documenta isso ("não mude o nome do evento"), o que é bom. Mas duas soluções transformariam uma armadilha documentada em contrato garantido:
  - uma constante compartilhada, definida em um só lugar e usada pelo `trigger_handover.sh` e pelo `parse_ping.py`; ou
  - um aviso do analisador quando o `events.csv` tiver eventos parecidos com handover, mas sem nome reconhecido.

---

## 3. Metodologia de medição e rigor científico

### O que está bem feito

- **"Confiável ou marcada como inválida, nunca errada sem aviso."** As etapas de validação (`ping_metrics_valid` e `packets_transmitted != 0`) são conferidas de novo depois da análise. Uma execução que enviou o comando de handover, mas não tem amostras úteis, é marcada como *falha*, com o evento `ping_metrics_invalid`. Erro sem aviso é a falha mais comum dos pipelines de medição acadêmicos. Este repositório foi projetado contra isso, de forma explícita.
- **Honestidade sobre a resolução.** A documentação diz com clareza que:
  - o intervalo de 0,2 s entre pings limita a estimativa da interrupção;
  - o RTT inclui ruído do rfsim, do Docker e do escalonamento do computador;
  - uma execução por topologia serve para conferir o funcionamento, e não como resultado de referência.

  O `report-baseline-results.md` congela os números históricos, só com ping. Ele se recusa, de forma explícita, a misturar depois os dados do iperf ("registre um novo resultado de referência com iperf em separado"). Essa é a prática correta de procedência dos dados.
- **Resultados validados e selecionados.** O `results/validated/2026-06-19/` guarda no git um conjunto de referência escolhido. O `.gitignore` deixa de fora as saídas brutas das execuções. Separar "a evidência que defendemos" dos "arquivos de trabalho" é o que pedem as orientações de reprodutibilidade, como os selos de artefato da ACM.
- **Estatística tratada com honestidade no painel web.** Os valores nulos ficam fora das estatísticas das campanhas, em vez de serem convertidos. O p95 usa o método do posto mais próximo. Os resultados são determinísticos. Arquivos malformados geram avisos, e nunca valores inventados.

### Lacunas

- **Tamanho da amostra e incerteza.** O resultado de referência publicado tem n = 5, com média, desvio-padrão, mínimo e máximo. A documentação já reconhece que um estudo comparativo de verdade precisa de várias execuções com partida a frio e de intervalos de confiança. As ferramentas aceitam `RUNS=20`. Falta só executar e documentar um resultado de referência maior, com intervalos de confiança. Se o agregador de execuções repetidas calculasse o intervalo de confiança junto com a média e o desvio-padrão, isso ficaria automático.
- **Etiquetas de imagem que mudam prejudicam a reprodutibilidade.** Todas as imagens da OAI usam a etiqueta `:develop` (e `ims:latest`). O próprio guia de medição lista "imagens fixadas pelo identificador (*digest*)" como requisito de um estudo de verdade. A linha "OAI version v2.4.0" da tabela do README não bate com as etiquetas `develop` dos arquivos Compose. Recomendação:
  - fixar as imagens pelo identificador (`image: oaisoftwarealliance/oai-gnb@sha256:…`) ou, no mínimo, por uma etiqueta de versão fixa;
  - gravar os identificadores no `summary.json` de cada execução;
  - corrigir a afirmação do README.
- **O significado da resolução da interrupção merece um documento.** A nova medição da interrupção com ping frequente (pings a cada 10 ms, pelo `scripts/measure_interruption.sh` e pelo cartão da visão geral) resolve o problema da resolução. Mas a regra-chave de interpretação só existe no histórico das sessões: *uma estimativa perto de um intervalo, com 0% de perda, indica handover sem interrupção, e não uma interrupção real. Um `icmp_seq` faltando é o sinal confiável de interrupção.* Ela deve ir para o `guide-measurement-pipeline.md`, e de preferência também para a interface, antes que alguém cite esses números.

---

## 4. Documentação (`docs/`)

### O que está bem feito

- **Uma arquitetura de informação de verdade.** A classificação por finalidade usa os tipos `foundation-fNN`, `guide`, `tutorial`, `report`, `record` e `handoff`. Ela tem identificadores fixos para os documentos de base, cabeçalhos explícitos de "leitura prévia" e ordens de leitura por objetivo no `docs/README.md`. É um equivalente caseiro do método Diátaxis, mais organizado que a documentação da maioria dos projetos abertos já estabelecidos. A regra "os identificadores são identificadores, não níveis de dificuldade; nunca renumere" mostra cuidado real com a curadoria.
- **Os documentos de base registram o *porquê*, e não só o *como*.** O F00 explica por que criar redes à mão com `docker network create` é uma armadilha. O F01 registra as regras de prontidão. O F04 registra os valores de configuração que são índices, como `ra_ResponseWindow = 4` valendo 10 slots. Cada um registra um tipo de erro e a regra que o evita. É memória institucional bem feita.
- **As justificativas essenciais estão escritas.** A separação entre o arquivo do teste inicial e o da captura longa está documentada *junto com a disputa que ela evita*. A dependência do nome do evento está sinalizada. A limitação do UE como servidor do rfsim, e o teto de vários UEs que ela impõe, aparecem na passagem de contexto do xApp. Uma pessoa nova no projeto consegue entender por que o código tem esse formato.
- **As passagens de contexto (*handoffs*) como gênero.** O `handoff-xapp-integration.md` traz contexto para uma pesquisa futura, com um plano em fases de integração com E2 e FlexRIC e riscos nomeados. Ele e a passagem de contexto da falha do teste rápido são uma prática excelente para pesquisa com várias sessões e vários agentes.

### Lacunas

- **O índice estava desatualizado** (resolvido em 03/07/2026). Quatro documentos mais novos não seguiam a regra de nomes nem apareciam no `docs/README.md`. Eles foram renomeados para `spec-dashboard.md`, `record-dashboard-phase6-overview.md`, `handoff-dashboard-overview-live.md` e `handoff-f1-smoke-auth-failure.md`, e agora estão no índice. A categoria `spec-` foi acrescentada à regra de nomes.
- **Nomes com número de fase registram a história, e não o conteúdo.** "Fase 6" só faz sentido para quem viveu as fases 1 a 5. Nomes por finalidade, que a classificação já exige, envelhecem melhor. Mantenha os números de fase dentro do texto, como história.
- **Risco de passagens de contexto desatualizadas** (resolvido em 03/07/2026). A passagem de contexto do teste rápido do F1 descrevia um bloqueio que existia na época (`CONTEXT_NOT_FOUND` no AUSF) e que depois foi corrigido (PR #17). Agora ela tem um aviso de uma linha sobre a solução. Os outros documentos de passagem de contexto e de registro devem receber o mesmo tratamento quando o problema central deles for resolvido. Assim, ninguém depura de novo um problema já corrigido.
- **O `record-development-history.md` tem formato de conversa.** Ele é honesto e útil, mas está escrito como narração de sessão, com "você" e "nós". Isso é aceitável para um `record-`. Vale saber que ele serve como registro de procedência, e não como referência. O índice o classifica corretamente. É uma observação menor.

---

## 5. Backend do painel web

### O que está bem feito

- **O modelo de segurança das ações é o ponto alto.**
  - As ações vêm desligadas por padrão.
  - Exigem `confirm` explícito.
  - Só aceitam scripts de uma lista permitida, com argumentos fixos. Não há `shell=True` em lugar nenhum, e os validadores *conferem no código-fonte* que isso continua assim.
  - Só uma tarefa roda por vez (409 em caso de sobreposição).
  - O tempo limite encerra o grupo de processos com SIGTERM e depois SIGKILL.
  - A saída fica limitada às últimas 200 linhas.
  - O repositório é montado só para leitura, menos `results/`.
  - O endpoint de capacidades *informa as próprias garantias de segurança*.

  É uma postura de execução de comandos melhor que a de muitas ferramentas internas comerciais.
- **Projeto pensado primeiro para funcionar com partes fora do ar.** O backend precisa subir e continuar útil com o testbed desligado, o socket do Docker com problema, o Telnet indisponível ou arquivos malformados. Tudo isso aparece como aviso, e nunca derruba o backend. Os validadores testam de forma explícita os casos de arquivos vazios, malformados ou faltando.
- **Telemetria honesta sobre o que se sabe.** O painel tem três regras que quase nenhum painel cumpre:
  - a classificação de confiança `observed / parsed / inferred / unknown`;
  - a separação estrita entre "eventos de registro do AMF vistos nos logs" e "número de UEs conectados agora";
  - a regra de que uma DU atual não observada aparece como "DU not observed", e não como um caminho inventado `UE → Unknown → CU`.

  É um padrão de honestidade de nível de pesquisa. Ele deve continuar como regra fixa.
- **Lições de operação guardadas no código.** A consulta periódica pelo Telnet da CU vem desligada por padrão, porque consultas repetidas com `help` derrubaram a CU da OAI (`*** buffer overflow detected ***`). Quando ligada, ela tem limite de frequência e guarda as capacidades descobertas. Os caminhos de montagem visíveis no computador, usados pelas ações que mexem no Docker, estão documentados com um arquivo Compose de exemplo que funciona.

### Lacunas

- **Sem autenticação e com `allow_origins=["*"]`.** Isso está documentado com honestidade ("não exponha em redes não confiáveis com as ações ligadas") e é aceitável em um laboratório com um só computador. Mas, com as ações ligadas, o backend comanda o Docker do computador. O próximo passo padrão é barato:
  - um token fixo (variável de ambiente, conferido por um middleware em `/api/actions/*` e em `/ws`);
  - uma lista de origens CORS, com a origem do frontend como padrão.

  Isso transforma um aviso documentado em um controle garantido.
- **Validadores próprios em vez do pytest.** O `validate_phase2..6.py` e o `validate_registry.py` são testes reais, com boa cobertura. Mas o executor feito à mão já escondeu uma falha: um `AssertionError` que saiu com código 0 durante o próprio desenvolvimento deste projeto. Passar as funções para o pytest é quase mecânico, porque elas já parecem funções de teste. O pytest traz relatórios detalhados, seleção com `-k` e *fixtures*, e elimina essa classe de erros de código de saída. Mantenha a conferência de divergências do `validate_registry.py`: a ideia de comparar o registro de contêineres do painel com os arquivos Compose reais é excelente.
- **Arquivos de teste com número de fase.** É o mesmo acúmulo dos documentos: `validate_phase4.py` diz *quando* foi escrito, e não *o que* protege. Na passagem para o pytest, dê nomes por assunto (`test_actions.py`, `test_campaigns.py` etc.).
- **O estado das tarefas fica só na memória** e se perde quando o backend reinicia (isso está documentado). Por enquanto, tudo bem. Se as campanhas passarem a durar mais que o backend no ar, guarde registros mínimos das tarefas em `results/`.

---

## 6. Frontend do painel web e experiência do operador

### O que está bem feito

- **A visão geral como tela de comando foi a escolha certa.** A reformulação da fase 6 veio de pedidos reais do operador: tirar cartões repetidos, recolher grupos, tirar etiquetas desatualizadas e trocar uma "duração do handover ao vivo" enganosa por um gráfico ao vivo de entrega de pacotes. E, o mais importante, o *raciocínio* ficou registrado. Ajustar uma interface de monitoração conforme o uso real em demonstrações é o caminho padrão da indústria. Documentar cada ajuste é mais raro.
- **Gráficos que não mentem.**
  - O gráfico de latência ao vivo mostra os testes perdidos como falhas na linha ou marcas, em vez de ligar os pontos por cima deles.
  - O novo gráfico de interrupção interrompe a linha onde falta um `icmp_seq` (`connectNulls=false`).
  - Ele marca o comando com uma linha de referência e a falha com uma faixa sombreada.

  Não mentir por interpolação é a regra mais importante de integridade de gráficos, e ela é seguida.
- **Os estados vazios e indisponíveis foram projetados, e não deixados ao acaso.** Exemplos: "No live latency samples yet…" (ainda sem amostras de latência ao vivo), rótulos Unavailable e avisos sobre os indicadores sintéticos do rfsim. A lista de validação exige que a visão geral apareça com a pilha desligada e sem nenhuma execução histórica.
- **Conjunto de tecnologias sensato e enxuto.** React 18, Vite, Recharts e Tailwind, sem um framework de estado de que o aplicativo não precisa. O WebSocket envia as atualizações, a API REST entrega os arquivos, e os arquivos grandes ficam fora do socket, de propósito.

### Lacunas

- **Nenhum teste de frontend e nenhum lint.** Não há configuração de ESLint nem de Prettier, e não há executor de testes no `package.json`. Nesta semana, uma regressão de estado vazio foi encontrada à mão: o código usava `data.length` em vez de `visibleSamples.length`, depois do preenchimento da janela. É exatamente o tipo de erro que um teste de componente pegaria. Mínimo necessário: ESLint e alguns testes com Vitest e react-testing-library para as funções que preparam os dados (`buildInterruptionResult`, leitura da linha de marcação do ID da execução e preenchimento da janela). Elas são funções puras e muito fáceis de testar.
- **Ferramentas de compilação no bloco errado de dependências.** O `vite` e o `@vitejs/plugin-react` estão em `dependencies`, e não em `devDependencies`. É um detalhe numa compilação Docker, mas mostra de forma errada o que o sistema precisa para rodar.
- **Os componentes de página estão crescendo demais.** O `Overview.jsx` tem cerca de 490 linhas, e o `CampaignsPage.jsx`, cerca de 425. Cada um junta busca de dados, transformação e exibição. Mover as funções puras de preparação de dados para `src/utils/` diminuiria as páginas e as tornaria testáveis. A mesma mudança resolve as duas lacunas.
- **Oportunidades de acabamento** (pequenas, em ordem de impacto):
  1. Mostrar, no próprio cartão de interrupção, a interpretação "até um intervalo de teste e 0% de perda ⇒ nenhuma interrupção mensurável (sem interrupção)". Assim, o operador não lê 11 ms como uma interrupção real.
  2. Guardar os últimos resultados vistos (por exemplo, no `localStorage`, ou buscando a última execução ao abrir a página). Assim, recarregar a página não apaga o cartão de interrupção.
  3. Mostrar, no lugar de um simples botão desligado, um aviso de "ações desligadas" que diga *como* ligá-las (o comando exato com a variável de ambiente).

### Análise do visual e do design da interface

O repositório não tem requisitos de design declarados. Por isso, esta seção avalia a interface pelas boas práticas gerais de design e indica as técnicas que a melhorariam.

O visual atual já é coerente e adequado para um console de operação:

- fundo ardósia escuro (`#0f172a`/`slate-950`);
- cartões com efeito de vidro (`rounded-2xl border-white/10 bg-white/[0.06]`);
- uma única cor de destaque, ciano;
- tons de estado em verde-esmeralda, âmbar e rosa;
- fonte monoespaçada para valores técnicos;
- pequenas etiquetas em maiúsculas, com letras espaçadas.

A direção de design da especificação ("denso, mas organizado; uma ferramenta de monitoração para pesquisadores") está sendo seguida. Abaixo, está o caminho de "limpo" para "bem projetado":

1. **Criar tokens de design (a técnica de design de maior efeito aqui).** Hoje, as cores estão fixas em cada arquivo:
   - cores hexadecimais dos gráficos (`#22d3ee`, `#fb7185`, `#94a3b8`) dentro das propriedades do Recharts;
   - cores de estado repetidas entre `StatusDot`, `Pill` e as marcas dos gráficos;
   - só uma classe compartilhada (`.card`).

   Defina uma vez tokens com significado (`status-ok`, `status-warn`, `status-bad`, `accent`, `text-muted` e uma pequena paleta para gráficos), no tema do Tailwind e em um pequeno `chartTheme.js`. Use-os em todo lugar. Assim, toda página nova fica coerente por padrão, e não por disciplina. Um tema claro ou um estilo para impressão e exportação vira uma troca de tokens, e não uma reescrita.
2. **A acessibilidade é o maior defeito concreto.**
   - O `StatusDot` mostra a saúde do contêiner só pela cor (verde, laranja ou vermelho). Isso fere o critério 1.4.1 das WCAG (uso de cor) e não serve para quem não distingue vermelho de verde. Junte ao ponto um texto curto ou uma etiqueta. Na barra lateral, ele já fica ao lado do texto `health || status`. A correção é, sobretudo, garantir esse par em todo lugar e acrescentar uma diferença de ícone ou de forma.
   - As etiquetas pequenas, com cerca de 10 px, em `text-slate-500` (`#64748b`) sobre fundo quase preto, ficam no limite do contraste AA das WCAG para texto pequeno. Passe para `slate-400` e no mínimo 11 px.
   - Acrescente `aria-expanded` nos cartões recolhíveis da barra lateral e `aria-current` na aba de navegação ativa.
   - Deixe visíveis os contornos de foco (`focus-visible`). No tema escuro, os contornos padrão quase não aparecem.

   Técnica recomendada: usar os componentes básicos do Radix UI (ou do shadcn/ui) para abas, itens recolhíveis e avisos (*toasts*). Eles já trazem o comportamento correto de teclado e de ARIA, e mantêm o estilo atual do Tailwind.
3. **Acrescentar rotas por URL.** Hoje, a navegação usa `useState("Overview")`. Por isso:
   - recarregar a página leva o operador de volta à visão geral;
   - não dá para criar um link direto para uma página ou execução, nem compartilhá-lo;
   - o botão voltar do navegador não faz nada.

   Uma ferramenta de monitoração vive de URLs que podem ser compartilhadas (`/runs/<id>`, `/campaigns/<id>`). Com o `react-router`, uma rota por página e rotas com parâmetro para o detalhe das execuções e das campanhas, a mudança leva meio dia. É a maior melhoria de usabilidade disponível.
4. **Criar hierarquia visual em torno dos números que importam.** Na visão geral, a principal métrica da pesquisa (a interrupção em ms) aparece como uma pequena etiqueta. Já um parágrafo de apresentação quase sem mudanças ocupa o maior texto da página. Inverta isso:
   - troque o parágrafo de apresentação por uma faixa de cartões de indicadores: saúde da pilha, DU atual, última interrupção, estado da entrega ao vivo e perda de pacotes;
   - use números grandes com rótulos pequenos;
   - leve o texto explicativo para dicas (*tooltips*) e legendas.

   A boa prática dos consoles densos é: "a maior quantidade de tinta vai para o valor mais importante".
5. **Juntar o código dos gráficos.** O `LiveLatencyChart` e o gráfico de interrupção repetem eixos, dica, arredondamento do eixo y e estilo das linhas, com pequenas diferenças. Crie um componente `RttChart` compartilhado, que receba como propriedades os eixos, a formatação da dica e as anotações de falha e de comando. Isso traz coerência visual, reduz o código pela metade e dá um só lugar para corrigir problemas de todos os gráficos. Melhorias próprias dos gráficos:
   - no traço denso de 10 ms, tire os pontos de cada amostra (`dot={false}` com `activeDot`). Seiscentos pontos de raio 2 são ruído visual e custo de desenho;
   - dê ao gráfico ao vivo um eixo de tempo real. Hoje, ele mostra índices de posição, com rótulos quase sempre vazios;
   - quando um handover rápido acontecer, marque o momento do comando também no gráfico *ao vivo*. O backend sabe o horário de início da tarefa. Isso liga os dois cartões;
   - use uma forma de marca diferente (e não só uma cor diferente) para os testes perdidos.
6. **Levar os componentes locais para o conjunto compartilhado.** O `Pill` e o `Detail` estão definidos dentro do `Overview.jsx`. Outras páginas vão criar, ou já criam, as próprias versões. Mova-os para `components/`, ao lado do `StatusDot` e do `MetricCard`. Faça deles a única forma de mostrar etiquetas de estado e detalhes do tipo chave e valor.
7. **Tipografia.** A especificação pede Inter e JetBrains Mono, mas o aplicativo usa as fontes padrão do sistema. Hospede as duas no próprio projeto, com o `@fontsource`, sem depender de CDN, o que é bom para laboratórios sem internet. Os números monoespaçados, em especial, impedem que a etiqueta de RTT ao vivo mude de largura quando o valor muda.
8. **Detalhes de layout.** A barra lateral tem largura fixa (`w-80`) e não se recolhe. A grade de duas colunas só se divide a partir do ponto de quebra `xl`. Em um notebook comum, de 1366 px, tudo fica empilhado. Torne a barra lateral recolhível (ela já recolhe cada cartão; acrescente o recolhimento da barra inteira) e ajuste o ponto de quebra para `lg`. Mantenha a filosofia atual de densidade de informação. Não acrescente enfeites.

Nada disso é uma reformulação, porque a estética está boa. É uma sistematização: tokens, semântica de acessibilidade, rotas, hierarquia e componentes compartilhados.

---

## 7. Cobertura igual entre topologias e rádios (só F1 contra N2, rfsim contra USRP)

A camada do testbed aceita três topologias de handover em rfsim e a operação com rádio real no USRP X310. O painel web, e principalmente a tela de comando da visão geral, atende hoje **uma** dessas combinações: o F1 em rfsim. Essa assimetria é a maior lacuna *funcional* do projeto. Vale descrevê-la com precisão, porque uma parte é trivial de resolver, e outra parte é um problema real de projeto.

### 7.1 Suporte ao N2 na visão geral (barato de resolver)

Situação atual, conferida no código:

- O `actions.py` fixa `"f1"` nos argumentos do comando (`trigger_handover.sh f1`) e nos da captura da interrupção (`measure_interruption.sh f1`).
- A visão geral só liga o comando rápido e o cartão de interrupção quando `topology === "f1"`. O título principal é "F1 RFsim handover cockpit".
- O leitor de configuração do backend retorna `not_implemented_in_phase_1` para as topologias que não são F1. Assim, as pilhas N2 mostram o estado dos contêineres, mas não a configuração lida nem o detalhe do diagrama da topologia.

Enquanto isso, *a automação por baixo já aceita tudo isso*:

- O `trigger_handover.sh` trata as três topologias, com descoberta automática e as variáveis `N2_SOURCE_GNB_TELNET_HOST`, `N2_TARGET_PCI` e `N2_UE_RRC_ID`.
- O `measure_interruption.sh` recebe a topologia como argumento e calcula a etiqueta da execução para as três.
- As ações de teste rápido e de teste repetido já aceitam `n2-monolithic` e `n2-cu-du`.

A restrição ao F1 está quase toda na camada do painel. Para resolvê-la:

1. Faça o `build_trigger_handover_command` e o `build_measure_interruption_command` receberem a topologia *detectada* (o backend já calcula `active_topology()`), mantendo a validação pela lista permitida.
2. Faça a visão geral depender da topologia: título e texto do botão dinâmicos ("Trigger N2 handover → PCI 1"), e indicadores de suporte por topologia em `/api/actions/capabilities`, em vez da conferência `=== "f1"` no frontend.
3. Estenda o leitor de configuração e o diagrama da topologia aos dois formatos do N2 (2 gNBs; 2 pares CU+DU). As entradas do registro para descobrir os contêineres já existem.

O N2 traz um problema de uso realmente novo, que pede projeto, e não só ligações: o **sentido do handover**. Depois de um handover N2, o UE fica na gNB de destino. Um segundo comando no mesmo sentido não faz nada ou falha, sem aviso. A automação resolve isso com `RESET_BETWEEN_RUNS=1`. A visão geral deve:

- mostrar a célula atual, da forma honesta, com o nível de confiança, como já faz com a DU atual no F1;
- e, além disso, fazer uma destas duas coisas:
  - oferecer um comando que respeite o sentido, com escolha do PCI de origem e de destino. A escolha deve ser limitada e validada no servidor, como o parâmetro de número de repetições;
  - dizer com clareza ao operador que é preciso recriar a topologia antes de comandar de novo.

Qualquer coisa menos que isso vai gerar demonstrações confusas, do tipo "o comando não fez nada".

### 7.2 USRP e rádio real (um problema real de projeto; faça em fases)

O painel web não conhece o `usrp-cots` nem as topologias distribuídas do `usrp_handover`. Mais importante: as duas funções principais da visão geral partem de premissas do rfsim:

- O teste de latência ao vivo e a captura da interrupção medem *de dentro do contêiner `oai-nr-ue`* (`docker exec oai-nr-ue ping -I oaitun_ue1 …`). Com um celular comercial, não há contêiner do UE, nem `oaitun_ue1`, nem shell no UE. A documentação já reconhece isso ("a medição do plano de usuário no celular é manual; os testes rápidos automáticos só funcionam com rfsim"). O ponto aqui é que as funções principais do painel herdam essa limitação por inteiro.
- O monitor do Docker só observa o socket *local*. Na montagem distribuída, com um rádio por computador, cada nó da RAN fica em um computador diferente. O painel mostraria a RAN vazia ou em vermelho, mesmo com o testbed saudável.

Fases recomendadas, da mais barata para a mais cara:

1. **`usrp-cots` em um só computador (quase só ligações).** Registre a topologia. Mostre a saúde do contêiner da gNB, a associação NG e os eventos de registro nos logs do AMF (tudo isso já pode ser coletado no computador local). Esconda, de forma honesta, os cartões que dependem do contêiner do UE, com um aviso como "UE comercial: não há teste dentro do contêiner disponível". Não os mostre quebrados.
2. **Voltar a visão geral do rádio real para as métricas que passam a ser *reais*.** No rfsim, os indicadores de rádio (CQI, RSRP, BLER, MCS) são sintéticos, e o painel, com razão, dá pouco destaque a eles. Com rádio real, eles são os dados interessantes, e as estatísticas de MAC pelo Telnet da gNB passam a ter valor de verdade. A consulta pelo Telnet com limite de frequência, que já existe (e vem desligada por padrão, por causa da estabilidade da CU), é a fonte natural. As estatísticas de MAC por UE, do lado da gNB, funcionam com qualquer tipo de UE. Os sinais de saúde do rádio (contagens de falta e de excesso de amostras nos logs da gNB) também cabem nessa visão geral. Eles são a falha do USRP que o operador de fato acompanha.
3. **A medição do plano de usuário com UE comercial pede um novo projeto de medição, e não uma adaptação.** Opções realistas, do menor para o maior esforço:
   - testes de descida a partir do `oai-ext-dn` para o IP que o UPF deu ao celular (só funciona se o celular responder a ICMP, e muitos não respondem);
   - contadores de sessão do UPF ou do SMF como indicador indireto da entrega;
   - um pequeno aplicativo de medição no celular (servidor iperf3 ou eco UDP). É a única forma de obter um número de interrupção comparável ao resultado de referência do rfsim.

   Isso é trabalho de planejamento de longo prazo. O README já lista "medição automática com UE comercial" como marco futuro. Mas o ponto, para este relatório, é: não apresente os números de interrupção do rfsim e os futuros números com rádio real como a mesma métrica sem documentar a diferença no caminho de medição.
4. **A visibilidade distribuída é o maior esforço e deve ter escopo bem definido.** Opções:
   - uma instância do painel por computador (funciona hoje, sem código, mas com experiência de uso ruim);
   - consulta remota dos contêineres por SSH ou por `docker context`;
   - um pequeno agente de estado em cada computador.

   O caminho das *ações* já funciona em montagem distribuída: as variáveis do `trigger_handover.sh` alcançam o Telnet remoto pela LAN. Assim, existe um meio-termo: um único painel comanda e observa o handover numa montagem distribuída, enquanto a saúde dos contêineres continua sendo vista por computador.

### 7.3 O mesmo olhar fora do painel web

O viés de dar prioridade ao F1 em rfsim é mais fraco no resto do repositório, mas existe:

- o relatório do resultado de referência e os resultados validados giram em torno do F1. As topologias N2 só têm execuções validadas isoladas, e não há resultado de referência repetido do N2 publicado;
- a nova captura de alta resolução da interrupção só foi usada no F1, embora o script aceite as três topologias.

Um resultado de referência repetido do N2 (as duas variantes, recriando a topologia entre execuções) tornaria simétrica, na prática, a afirmação de que o repositório cobre três topologias. É só tempo de máquina com as ferramentas que já existem.

## 8. Organização do repositório, git e infraestrutura do projeto

É aqui que o repositório mais se afasta do padrão da indústria. Todos os itens são baratos de corrigir.

- **Sem CI.** O repositório tem um ótimo conjunto de validações, listado no `dashboard/README.md`: `compileall`, seis validadores, conferência de divergências do registro, compilação do frontend, `docker compose config` e validação da carga inicial de assinantes. *Nada o executa de forma automática.* Bastaria um único workflow do GitHub Actions com essa lista, mais `shellcheck scripts/*.sh` e `bash -n`. Ele pegaria as quebras que já aconteceram na prática, na passagem de parâmetros de construtores e no conjunto fixo de verificações. É a melhoria isolada de maior efeito disponível.
- **Sem LICENSE.** No GitHub, sem licença, todos os direitos ficam reservados. Ninguém pode reutilizar este testbed legalmente, nem citá-lo e construir sobre ele. Isso contradiz a finalidade de um artefato de pesquisa. Os componentes da OAI usam a OAI Public License, próxima da Apache. A automação pode usar Apache-2.0 ou MIT. Acrescente um arquivo.
- **Ruído no histórico do git.** Dos 57 commits no `main`, 14 são commits automáticos com a mensagem ".", misturados ao trabalho real feito por PRs. Isso impede o uso do `git bisect` e torna o `git log` ilegível. Aponte a ferramenta de commit automático para um branch de rascunho (ou desligue-a) e deixe o `main` só para PRs. Também crie etiquetas para os resultados de referência validados (`baseline-2026-06-19`). Assim, os números publicados ficam presos a um commit.
- **O `.gitignore` são dois modelos colados.** O modelo Python do GitHub e um bloco local estão juntos, repetindo `results/runs/*`, `__pycache__/`, `.venv/` etc. Mesmo com cerca de 300 linhas, **o `node_modules/` não é ignorado**. Ele aparece como não rastreado agora, a um commit automático errado de virar um commit de 200 MB. Reduza para cerca de 40 linhas planejadas e acrescente `node_modules/`.
- **Estrutura morta** (resolvido em 03/07/2026). A pasta `metrics/{ping,parsed,iperf}/` só tinha arquivos `.gitkeep`. A estrutura foi substituída por `results/runs/<id>/` e foi apagada. Nenhum código a citava.
- **Configurações espalhadas na raiz.** O `conf-cu.conf`, o `conf-du.conf`, o `conf-nr-ue.conf` e o `gnb-docker-compose.yaml` ficam na raiz do repositório, enquanto todas as outras topologias ficam em `experiments/<nome>/`. Mover os arquivos do F1 para `experiments/manual_f1_handover/`, atualizando os caminhos no `lib.sh` e no registro do painel, deixaria a organização uniforme. O validador de divergências pegaria o que faltasse. Esforço médio: faça quando houver oportunidade.
- **Sem `pyproject.toml` nem ruff para o código Python.** O `requirements.txt` fixa as versões corretamente, o que é bom. Mas não há configuração de formatação nem de lint para o backend e para `tools/`. Acrescentar o ruff (lint e formatação) ao workflow do CI padroniza o estilo de graça.
- **O AGENTS.md é uma prática boa e moderna.** Ele guarda fatos fixos (nomes dos contêineres, endpoint Telnet, "não invente um comando genérico `handover`"). Isso impede que várias sessões com assistentes de IA refaçam deduções ou violem regras. Continue a ampliá-lo à medida que surgem regras. O contrato do nome do evento `handover_trigger_start` também deve ir para lá.

---

## 9. Segurança

- **Pontos fortes:**
  - nenhuma execução de comando arbitrário;
  - nenhuma interpolação em shell (conferido nos testes);
  - travas e confirmação nas ações;
  - montagens só para leitura;
  - saídas limitadas;
  - as credenciais de SIM na documentação são os vetores de teste públicos da OAI, e não segredos;
  - os arquivos `.env` são ignorados pelo git, e o `.env.example` fica no repositório. É o padrão correto para as configurações de LAN do USRP.
- **Pontos fracos:**
  - sem autenticação e com CORS aberto a qualquer origem (seção 5);
  - o socket do Docker montado no contêiner do backend equivale a acesso de root no computador. Isso faz parte do projeto e é aceitável num laboratório. Mas quer dizer que o aviso "não exponha em redes não confiáveis" é essencial e deve ser garantido pelo token recomendado acima;
  - o nginx do frontend do painel não envia nenhum cabeçalho de proteção (detalhe menor para uso em laboratório).

---

## 10. Recomendações por prioridade

**P0: faça primeiro (cada uma leva menos de 1 hora):**

1. Criar um workflow de CI no GitHub Actions, com a lista de validações já documentada, `bash -n`, `shellcheck` e a compilação do frontend.
2. Acrescentar um arquivo LICENSE.
3. Corrigir o `.gitignore`: tirar as repetições e acrescentar `node_modules/`.
4. Parar os commits automáticos "." no `main` (branch de rascunho ou desligar) e criar a etiqueta `baseline-2026-06-19`.

**P1: a curto prazo (um ou dois dias no total):**

5. Estender ao N2 o comando rápido e a captura da interrupção da visão geral (seção 7.1): passar a topologia detectada pela lista permitida de ações, fazer a visão geral depender da topologia e projetar o uso com sentido do handover e recriação da topologia. A automação já aceita tudo isso.
6. Fixar as imagens da OAI pelo identificador (ou por etiqueta fixa), gravar os identificadores no `summary.json` e corrigir a afirmação "v2.4.0" do README.
7. Passar os `validate_phase*.py` para o pytest, com nomes por assunto. Acrescentar testes com arquivos de referência para o `parse_ping.py`. Incluir um caso de regressão do erro de mistura com o teste inicial e um caso sintético de interrupção com sequências faltando.
8. Acrescentar autenticação por token e uma lista explícita de origens CORS ao backend. Manter o aviso de "não exponha" na documentação, como defesa em profundidade.
9. Trazer os quatro documentos fora do padrão para a regra de nomes e incluí-los no `docs/README.md`. Acrescentar avisos de solução às passagens de contexto encerradas.
10. Documentar no `guide-measurement-pipeline.md` a medição de alta resolução da interrupção: pings a cada 10 ms, interpretação do limite de resolução e diferença entre "sem interrupção" e "interrupção real". Mostrar a mesma interpretação no cartão do painel.
11. Sistematizar a interface (seção 6):
    - tokens de design e componentes compartilhados de estado e de gráfico;
    - correções das WCAG: estado indicado sem depender só da cor, contraste, contornos de foco e ARIA nas abas e nos itens recolhíveis;
    - rotas por URL, com links diretos para execuções e campanhas.

**P2: quando houver oportunidade:**

12. ESLint e Vitest no frontend. Tirar dos componentes de página grandes as funções puras de preparação de dados e testá-las primeiro.
13. Passar o `vite` e o `@vitejs/plugin-react` para `devDependencies`.
14. Registrar um resultado de referência maior do F1 (n ≥ 20), com intervalos de confiança. Registrar também um primeiro resultado de referência repetido do N2, nas duas variantes, recriando a topologia entre execuções. Assim, a afirmação das três topologias fica simétrica na prática. Fazer o agregador calcular os intervalos de confiança.
15. Registrar o `usrp-cots` no painel, escondendo de forma honesta os cartões que dependem do contêiner do UE. Voltar uma visão geral de rádio real para as estatísticas de MAC pelo Telnet e para os sinais de saúde do rádio (seção 7.2). Tratar a medição do plano de usuário com UE comercial como um projeto à parte.
16. Apagar ou documentar a pasta vazia `metrics/`. Avaliar mover as configurações do F1, que estão na raiz, para `experiments/`.
17. Acrescentar a configuração do `ruff` ao backend e a `tools/`. Acrescentar o contrato do nome do evento (`handover_trigger_start`) ao AGENTS.md ou garanti-lo por uma constante compartilhada.

## 11. Avaliação final

O núcleo científico deste repositório é mais forte que o da grande maioria dos testbeds de pesquisa e não precisa ser refeito. Ele inclui:

- o modelo de prontidão;
- as etapas de validação da medição;
- a honestidade sobre a resolução;
- a telemetria marcada com nível de confiança;
- uma documentação com arquitetura de informação de verdade.

O modelo de segurança das ações do painel web tem pensamento de nível de produção. O que falta cai em três grupos:

- infraestrutura comum de projeto de software: CI, licença, organização do git, ferramentas padrão de teste e de lint, imagens fixadas. Nada disso é estrutural, e tudo é barato;
- uma sistematização da interface: tokens, acessibilidade e rotas. É um refinamento de um design sólido, e não uma reformulação;
- cobertura igual entre topologias. A metade do N2 é quase só ligação, porque a automação já fez a parte difícil. A metade do USRP é um problema real de projeto de medição e deve ser feita em fases, com cuidado, e não adaptada de forma ingênua.
