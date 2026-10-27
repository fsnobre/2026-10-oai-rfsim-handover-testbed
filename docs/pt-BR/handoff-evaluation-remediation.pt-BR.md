# Handoff: implementação das correções da avaliação

> Tradução para o português. O original em inglês é o [handoff-evaluation-remediation.md](../en/handoff-evaluation-remediation.md). Em caso de divergência, prevalece o original.

> **Tipo de documento:** Handoff
>
> **Data:** 03/07/2026
>
> **Leitura obrigatória:** [relatório de avaliação do repositório](report-repository-evaluation.pt-BR.md) (o *porquê* de cada tarefa deste documento), `CLAUDE.md` na raiz do repositório (invariantes rígidos e conjunto de validação).

Este documento transforma as recomendações do relatório de avaliação em pacotes de trabalho
ordenados e delimitados para um agente de implementação que roda sem supervisão. O relatório explica e
justifica; este documento dá instruções. Quando os dois parecerem divergir quanto ao escopo, prevalece este
documento.

## Regras básicas para o agente de implementação

1. Obedeça a todos os invariantes do `CLAUDE.md`. Em particular: apenas staging explícito (nunca
   `git add -A`), nada de push, nada de enfraquecer o modelo de segurança das ações do painel, nada de
   valores de telemetria fabricados.
2. Execute os pacotes **em ordem**. Faça um commit por pacote de trabalho concluído, com uma
   mensagem descritiva. Se um pacote falhar no critério de aceitação, corrija-o ou reverta-o antes de
   seguir adiante — não deixe a árvore quebrada entre pacotes.
3. O testbed da OAI ao vivo **não está rodando**. A aceitação de cada pacote é o conjunto de
   validação estática do `CLAUDE.md` (mais as verificações específicas de cada pacote, abaixo). Tudo o que
   exigir uma pilha ao vivo está marcado explicitamente como *acompanhamento manual* — implemente, verifique
   estaticamente e liste no seu resumo final como "precisa de verificação ao vivo".
4. Decisões já tomadas pelo responsável — não as rediscuta:
   - **Licença: adiada.** NÃO adicione um arquivo LICENSE. Onde o relatório disser "adicionar uma
     licença", pule e registre como bloqueado aguardando o responsável.
   - **Escopo: tudo o que está abaixo** (de P0 a P2), exceto os itens marcados para pular.
5. Se algo for ambíguo, escolha a menor mudança coerente com o relatório e
   registre a escolha no seu resumo final. Não amplie o escopo além destes pacotes.

## Pacotes de trabalho

### WP1 — Higiene do repositório (relatório §8; itens P0 1 e 3)

- Reescreva o `.gitignore`: elimine a duplicação dos modelos concatenados, produzindo um único arquivo
  intencional (~40 linhas) que preserve todas as regras atualmente em vigor (artefatos de execução em results/logs
  com as exceções `.gitkeep`, caches do Python, venvs, `.env` com `!.env.example`,
  `dist/`) e **acrescente `node_modules/`**. Verifique com `git status --short` que nenhum
  arquivo atualmente rastreado passa a ser ignorado e que nada novo aparece em staging.
- Adicione um workflow do GitHub Actions em `.github/workflows/ci.yml`, executado em push/PR:
  (a) o conjunto completo de validação do `CLAUDE.md` (validadores do backend, compose config,
  seed de assinantes, `npm ci && npm run build` no frontend); (b) `bash -n` em todos os
  `scripts/*.sh`; (c) `shellcheck` (pela action padrão do shellcheck; inicialmente, trate os avisos
  como não fatais — `SHELLCHECK_OPTS=-S error` — para que a primeira execução de CI fique verde).
  Use apenas `docker compose config` (sem subir a pilha). Fixe as versões das actions.
- NÃO mexa na ferramenta de commit automático (externa ao repositório). NÃO adicione um LICENSE
  (adiado). Criar a tag `baseline-2026-06-19` é decisão do responsável — pule.
- **Aceitação:** o conjunto de validação passa localmente; o YAML do workflow é válido
  (`docker run --rm rhysd/actionlint`, se disponível; caso contrário, revisão cuidadosa);
  `node_modules/` não aparece mais no `git status`.

### WP2 — Corrigir os defeitos apontados pelo shellcheck (relatório §2)

- Execute o shellcheck (instale localmente, se possível: `sudo apt-get install -y shellcheck`,
  ou use um contêiner) em `scripts/*.sh`. Corrija os achados de severidade `error`; corrija
  os de severidade `warning` somente quando a correção for obviamente segura (aspas, variáveis
  não usadas). Não reestruture os scripts.
- **Aceitação:** `bash -n` limpo; shellcheck sem erros; os validadores continuam passando
  (vários fazem asserções sobre caminhos/comportamento dos scripts).

### WP3 — Portar os validadores do backend para pytest (relatório §5; item P1 7)

- Converta `validate_phase2..6.py` e `validate_registry.py` em testes pytest em
  `dashboard/backend/tests/`, nomeados por assunto (`test_state.py`, `test_runs.py`,
  `test_handover.py`, `test_actions.py`, `test_campaigns.py`, `test_overview.py`,
  `test_registry.py` — ajuste ao conteúdo real ao dividir). Preserve todas as
  asserções existentes, incluindo as asserções sobre o código-fonte (ausência de `shell=True` etc.).
- Mantenha os arquivos `validate_*.py` originais como invólucros finos que invocam o pytest (para que
  os comandos documentados continuem funcionando) ou atualize todas as referências documentadas
  (`dashboard/README.md`, `docs/en/record-dashboard-phase6-overview.md`, o CI do WP1,
  `CLAUDE.md`) — escolha uma abordagem e aplique-a de forma consistente.
- Adicione `pytest` a um novo `dashboard/backend/requirements-dev.txt` (não o adicione ao
  `requirements.txt` de execução).
- Adicione testes com arquivos de referência (golden files) para `tools/parse_ping.py`: um fixture sintético de `ping_raw.log` +
  `events.csv` com uma lacuna conhecida (`estimated_interruption_ms` esperado), um
  fixture de contaminação pela pré-verificação (regressão do bug histórico do parser) e um
  caso sem interrupção com 0% de perda. Coloque-os em `tools/tests/`.
- **Aceitação:** `pytest dashboard/backend tools` verde; CI atualizado para executá-lo.

### WP4 — Autenticação e CORS no backend (relatório §5, §9; item P1 8)

- Adicione autenticação opcional por token bearer estático: variável de ambiente `DASHBOARD_API_TOKEN`; quando definida,
  exija `Authorization: Bearer <token>` em todos os endpoints `/api/actions/*` e no
  handshake do `/ws` (parâmetro de consulta ou cabeçalho para o WS). Quando não definida, o comportamento não muda
  (padrão de laboratório). Rejeite com 401, nunca falhe.
- Substitua `allow_origins=["*"]` por `DASHBOARD_CORS_ORIGINS` (separado por vírgulas, padrão
  `*` para preservar o comportamento atual de laboratório; documente que um uso próximo de produção deve defini-lo).
- Frontend: leia o token a partir de um recurso simples de configuração (por exemplo, uma chave no `localStorage` +
  um pequeno campo na página Controls) e anexe-o a `apiPost`/`apiGet`/WS quando presente.
- Documente em `dashboard/README.md` (mantenha o aviso existente de "não expor em redes
  não confiáveis").
- **Aceitação:** validadores/pytest verdes com o recurso tanto não definido quanto definido (adicione
  testes para 401 quando o token está definido e sucesso quando está correto).

### WP5 — Suporte à N2 nas ações da Visão geral (relatório §7.1; item P1 5)

- `build_trigger_handover_command` e `build_measure_interruption_command` passam a receber um
  argumento de topologia validado (`f1`, `n2-monolithic`, `n2-cu-du` — o mesmo padrão de lista
  de permissões dos testes rápidos), em vez do `"f1"` fixo no código; o gerenciador de ações passa a
  topologia detectada pelo backend. O `scripts/trigger_handover.sh` e o
  `scripts/measure_interruption.sh` já aceitam esses valores.
- `/api/actions/capabilities` expõe as topologias suportadas por ação; a Visão geral
  usa isso em vez das verificações `topology === "f1"` do lado do frontend. Os rótulos dos botões e
  o título principal passam a refletir a topologia ("Trigger N2 handover", "N2 monolithic RFsim
  handover cockpit" etc.).
- Honestidade quanto ao sentido na N2 (mínimo de projeto, não o controle completo do sentido): quando a topologia é
  N2, mostre uma legenda no cartão de disparo informando que disparos repetidos no mesmo sentido
  exigem reinicializar a topologia (semântica de `RESET_BETWEEN_RUNS=1`) e mostre a célula
  servidora somente quando observada — nunca a invente. NÃO construa nesta etapa uma interface de seleção de
  PCI de origem/destino.
- Atualize os testes dos novos construtores de comando (topologia inválida → 400; formato do argv por
  topologia).
- **Aceitação:** pytest verde; o frontend compila; *acompanhamento manual:* disparo N2 ao vivo
  a partir da Visão geral.

### WP6 — Documentação da semântica da medição (relatório §3; item P1 10)

- Amplie o `docs/en/guide-measurement-pipeline.md` com a captura de interrupção em alta
  resolução: o fluxo do `scripts/measure_interruption.sh` (sondas a cada 10 ms, ~2 s antes / ~4 s depois,
  substituições pelas variáveis `INTERRUPTION_*`), a regra do piso de resolução (a estimativa tem como piso
  o intervalo das sondas) e a regra de interpretação: **estimativa ≈ um intervalo de sonda
  com 0% de perda e nenhum icmp_seq faltando ⇒ handover sem interrupção, e não uma interrupção real; icmp_seq
  faltando é o sinal honesto de interrupção**.
- Leve a mesma interpretação para a interface: no cartão de interrupção da Visão geral, quando
  `packetLoss === 0` e a estimativa for ≤ ~2× o intervalo das sondas, mostre "no measurable
  user-plane outage (seamless)" (nenhuma interrupção mensurável do plano de usuário) ao lado do número.
- **Aceitação:** documento indexado, caso as novas seções não justifiquem um novo arquivo (não justificam — edite
  no próprio arquivo); o frontend compila.

### WP7 — Padronização dos nomes da documentação (relatório §4; item P1 9)

- Renomeie conforme a convenção e indexe em `docs/en/README.md`:
  `DASHBOARD_SPEC.md` → `spec-dashboard.md` (adicione uma linha "Spec" à convenção de nomes, ou
  use `record-dashboard-spec.md` se preferir não criar categorias novas — escolha uma),
  `dashboard_phase6_operator_overview.md` → `record-dashboard-phase6-overview.md`,
  `dashboard_overview_live_handoff.md` → `handoff-dashboard-overview-live.md`,
  `oai_rfsim_f1_smoke_handoff.md` → `handoff-f1-smoke-auth-failure.md`.
  Use `git mv`. Corrija todas as referências de entrada (`rg -l` para cada nome antigo).
- Adicione um breve aviso de resolução no início de `handoff-f1-smoke-auth-failure.md`,
  informando que o bloqueio de autenticação foi resolvido (PR #17, correção do seed — veja
  "F1 smoke-test subscriber diagnostics" em `dashboard/README.md`).
- **Aceitação:** o `rg` não encontra referências aos nomes antigos; todo documento em `docs/`
  aparece em `docs/en/README.md`.

### WP8 — Ferramentas do frontend + primitivas compartilhadas (relatório §6; itens P2 12 e 13)

- Mova `vite` e `@vitejs/plugin-react` para `devDependencies`.
- Adicione ESLint (configuração flat, `eslint-plugin-react` + plugin de hooks) e corrija os
  problemas apontados; adicione os scripts `"lint"` e `"test"`.
- Adicione Vitest + @testing-library/react. Primeiros testes: extraia os auxiliares puros de
  `Overview.jsx` (`buildInterruptionResult`, `runIdFromTail`, o preenchimento da janela do
  gráfico ao vivo) para `src/utils/` e teste-os (detecção de lacunas, nulos em séries densas,
  leitura do marcador, comprimento do preenchimento).
- Promova `Pill` e `Detail` de `Overview.jsx` para `src/components/` e reutilize-os.
- Adicione ESLint + Vitest ao CI.
- **Aceitação:** `npm run lint`, `npm run test` e `npm run build` todos verdes.

### WP9 — Sistematização da interface (revisão de design do relatório §6; item P1 11)

Aplique nesta ordem, começando pelo menor risco; mantenha a identidade visual existente.

- Design tokens: defina cores semânticas (status ok/aviso/ruim, destaque, texto esmaecido, série/perda/anotação
  de gráfico) na extensão de tema do `tailwind.config.js`, mais um
  `src/utils/chartTheme.js`; substitua hexadecimais fixos no código e classes de status por arquivo.
- Acessibilidade: indicações de status que não dependam só da cor (o `StatusDot` ganha um rótulo/forma associado),
  aumente o contraste dos microrrótulos (`slate-500` → `slate-400`, mínimo de 11px), `aria-expanded`
  nos recolhíveis da barra lateral, `aria-current` na aba de navegação ativa, anéis
  `focus-visible` visíveis.
- Roteamento por URL: `react-router-dom`; uma rota por página, rotas com parâmetro
  `/runs/:runId` e `/campaigns/:campaignId` ligadas às visões de detalhe existentes;
  a aba ativa é derivada da rota.
- Componente compartilhado `RttChart`, consumido tanto pelo gráfico de latência ao vivo quanto pelo de interrupção
  (eixos, tooltip, arredondamento do y máximo, anotações de lacuna/disparo como props);
  `dot={false}` para o traçado denso da interrupção.
- Pular nesta etapa (exige iteração visual ao vivo): reformulação do destaque com blocos de KPI,
  fontes hospedadas localmente, trilho recolhível na barra lateral.
- **Aceitação:** lint/test/build verdes; nenhum literal hexadecimal `#` restante no código JSX dos gráficos
  (`rg '#[0-9a-f]{6}' dashboard/frontend/src` restrito aos arquivos de tokens).

### WP10 — Limpeza (relatório §8; itens P2 16 e 17)

- Exclua a árvore vazia `metrics/` (só contém `.gitkeep`; substituída por `results/`).
  Antes, verifique que nada a referencia (`rg -l 'metrics/' scripts tools dashboard docs
  README.md` — será preciso remover a menção na seção de estrutura do README).
- Adicione configuração do `ruff` (`pyproject.toml` na raiz do repositório ou em `dashboard/backend`): lint +
  formatação para `dashboard/backend` e `tools`; corrija os achados; adicione ao CI.
- NÃO realoque nesta execução os arquivos de configuração F1 da raiz (isso mexe em caminhos de execução em
  `lib.sh`, no Compose e no registro do painel — arriscado demais sem supervisão).
- **Aceitação:** conjunto completo + ruff verdes.

## Explicitamente fora do escopo desta execução

- LICENSE (decisão do responsável pendente).
- Tudo o que exigir o testbed ao vivo: referências com n≥20, referências N2 repetidas, verificação
  ao vivo do comportamento do WP5/WP6, trabalho com USRP (fases 1–4 do relatório §7.2).
- Mudanças na ferramenta de commit automático, reescrita do histórico do git, criação de tags.
- Realocação dos arquivos de configuração da raiz; redesenho do destaque com KPIs; recolhimento do trilho da barra lateral; fontes.

## Requisitos do resumo final

Termine com: o status de cada pacote (feito/pulado + motivo), todas as decisões de julgamento tomadas, a lista
de itens que precisam de verificação no testbed ao vivo e a confirmação de que o conjunto completo de
validação e o workflow de CI passam.
