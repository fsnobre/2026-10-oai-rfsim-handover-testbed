# Passagem de contexto: implementação das correções da avaliação

> Tradução para o português em Linguagem Simples. O original em inglês é o [handoff-evaluation-remediation.md](../en/handoff-evaluation-remediation.md). Se houver diferença entre os dois, vale o original.

> **Tipo de documento:** passagem de contexto (*handoff*)
>
> **Data:** 03/07/2026
>
> **Leitura prévia:** [relatório de avaliação do repositório](report-repository-evaluation.pt-BR-simples.md) (o *porquê* de cada tarefa daqui) e o `CLAUDE.md` na raiz do repositório (regras fixas e conjunto de validações).

Este documento transforma as recomendações do relatório de avaliação em pacotes de trabalho com ordem e escopo definidos. Ele se destina a um agente de implementação que trabalha sem acompanhamento. O relatório explica e justifica. Este documento dá as instruções. Se os dois parecerem discordar sobre o escopo, vale este documento.

## Regras básicas para o agente de implementação

1. Siga todas as regras fixas do `CLAUDE.md`. Em especial:
   - prepare os commits só com arquivos explícitos (nunca use `git add -A`);
   - não faça push;
   - não enfraqueça o modelo de segurança das ações do painel web;
   - não invente valores de telemetria.
2. Faça os pacotes **na ordem**. Faça um commit por pacote concluído, com uma mensagem descritiva. Se um pacote falhar no critério de aceitação, corrija-o ou desfaça-o antes de seguir. Não deixe o repositório quebrado entre pacotes.
3. O testbed da OAI **não está rodando**. O critério de aceitação de cada pacote é o conjunto de validações estáticas do `CLAUDE.md`, mais as conferências próprias do pacote, listadas abaixo. O que exigir a pilha rodando está marcado como *conferência manual posterior*. Implemente, confira de forma estática e liste o item no resumo final como "precisa de conferência com o testbed rodando".
4. O dono já tomou estas decisões. Não as discuta de novo:
   - **Licença: adiada.** NÃO acrescente um arquivo LICENSE. Onde o relatório disser "acrescente uma licença", pule e anote como "bloqueado, depende do dono".
   - **Escopo: tudo o que está abaixo** (de P0 a P2), menos os itens marcados para pular.
5. Se algo for ambíguo, escolha a menor mudança coerente com o relatório. Registre a escolha no resumo final. Não amplie o escopo além destes pacotes.

## Pacotes de trabalho

### WP1: organização do repositório (relatório §8; itens P0 1 e 3)

- Reescreva o `.gitignore`. Junte os modelos concatenados em um único arquivo planejado, com cerca de 40 linhas. Ele deve manter todas as regras que valem hoje:
  - arquivos de execução em results e logs, com as exceções `.gitkeep`;
  - caches do Python;
  - ambientes virtuais (venvs);
  - `.env`, com a exceção `!.env.example`;
  - `dist/`.

  Ele também deve **acrescentar `node_modules/`**. Confira com `git status --short` que nenhum arquivo rastreado passa a ser ignorado e que nada novo aparece preparado para commit.
- Crie um workflow do GitHub Actions em `.github/workflows/ci.yml`, que rode em push e em PR. Ele deve executar:
  - (a) o conjunto completo de validações do `CLAUDE.md`: validadores do backend, configuração do Compose, carga inicial de assinantes e `npm ci && npm run build` no frontend;
  - (b) `bash -n` em todos os `scripts/*.sh`;
  - (c) o `shellcheck`, pela action padrão do shellcheck. No começo, trate os avisos como não fatais (`SHELLCHECK_OPTS=-S error`), para a primeira execução do CI passar.

  Use só `docker compose config`, sem subir a pilha. Fixe as versões das actions.
- NÃO mexa na ferramenta de commit automático, que fica fora do repositório. NÃO acrescente um LICENSE (adiado). Criar a etiqueta `baseline-2026-06-19` é decisão do dono: pule.
- **Aceitação:** o conjunto de validações passa no computador local. O YAML do workflow é válido (use `docker run --rm rhysd/actionlint`, se estiver disponível, ou revise com cuidado). O `node_modules/` não aparece mais no `git status`.

### WP2: corrigir os defeitos apontados pelo shellcheck (relatório §2)

- Execute o shellcheck em `scripts/*.sh`. Se possível, instale-o no computador (`sudo apt-get install -y shellcheck`) ou use um contêiner. Corrija os achados de nível `error`. Só corrija os de nível `warning` quando a correção for claramente segura, como aspas ou variáveis sem uso. Não reestruture os scripts.
- **Aceitação:** `bash -n` sem erros, shellcheck sem erros, e os validadores continuam passando. Vários validadores conferem caminhos e comportamento dos scripts.

### WP3: passar os validadores do backend para o pytest (relatório §5; item P1 7)

- Converta `validate_phase2..6.py` e `validate_registry.py` em testes pytest, em `dashboard/backend/tests/`. Dê a cada arquivo o nome do assunto: `test_state.py`, `test_runs.py`, `test_handover.py`, `test_actions.py`, `test_campaigns.py`, `test_overview.py` e `test_registry.py`. Ao dividir, siga o conteúdo real. Mantenha todas as conferências atuais, inclusive as que leem o código-fonte (ausência de `shell=True` etc.).
- Escolha um destes caminhos e aplique-o sempre:
  - manter os `validate_*.py` originais como invólucros finos que chamam o pytest, para os comandos documentados continuarem funcionando; ou
  - atualizar todas as referências documentadas: `dashboard/README.md`, `docs/en/record-dashboard-phase6-overview.md`, o CI do WP1 e o `CLAUDE.md`.
- Acrescente o `pytest` a um novo `dashboard/backend/requirements-dev.txt`. Não o acrescente ao `requirements.txt` de execução.
- Acrescente testes com arquivos de referência (*golden files*) para o `tools/parse_ping.py`. Coloque-os em `tools/tests/`:
  - um `ping_raw.log` e um `events.csv` sintéticos, com uma falha conhecida e o `estimated_interruption_ms` esperado;
  - um caso de mistura com o teste inicial, para não repetir o erro histórico do analisador;
  - um caso sem interrupção, com 0% de perda.
- **Aceitação:** `pytest dashboard/backend tools` passa, e o CI foi atualizado para rodá-lo.

### WP4: autenticação e CORS no backend (relatório §5 e §9; item P1 8)

- Acrescente uma autenticação opcional por token fixo (*bearer token*), pela variável de ambiente `DASHBOARD_API_TOKEN`:
  - com a variável definida, exija `Authorization: Bearer <token>` em todos os endpoints `/api/actions/*` e na abertura do `/ws` (no WebSocket, por parâmetro de consulta ou por cabeçalho);
  - sem a variável, nada muda (padrão de laboratório);
  - recuse com 401. Nunca deixe o backend cair.
- Troque `allow_origins=["*"]` por `DASHBOARD_CORS_ORIGINS`, separada por vírgulas. O padrão é `*`, para manter o comportamento atual do laboratório. Documente que um uso mais próximo de produção deve definir essa variável.
- No frontend, leia o token de uma configuração simples: por exemplo, uma chave no `localStorage` e um pequeno campo na página Controls. Quando houver token, envie-o no `apiPost`, no `apiGet` e no WebSocket.
- Documente no `dashboard/README.md`. Mantenha o aviso atual de "não exponha em redes não confiáveis".
- **Aceitação:** os validadores e o pytest passam com a variável definida e sem ela. Acrescente testes: 401 com token definido e errado, e aprovação com o token certo.

### WP5: suporte ao N2 nas ações da visão geral (relatório §7.1; item P1 5)

- `build_trigger_handover_command` e `build_measure_interruption_command` passam a receber a topologia como argumento validado (`f1`, `n2-monolithic` ou `n2-cu-du`, com a mesma lista permitida dos testes rápidos), em vez do valor fixo `"f1"`. O gerenciador de ações passa a topologia detectada pelo backend. O `scripts/trigger_handover.sh` e o `scripts/measure_interruption.sh` já aceitam esses valores.
- O `/api/actions/capabilities` informa as topologias aceitas por cada ação. A visão geral usa essa informação, em vez das conferências `topology === "f1"` no frontend. Os textos dos botões e o título principal passam a depender da topologia, como "Trigger N2 handover" ou "N2 monolithic RFsim handover cockpit".
- Honestidade sobre o sentido do handover no N2 (o mínimo do projeto, sem controle completo do sentido):
  - quando a topologia for N2, mostre uma legenda no cartão do comando. Ela deve dizer que comandos repetidos no mesmo sentido exigem recriar a topologia (o mesmo efeito de `RESET_BETWEEN_RUNS=1`);
  - mostre a célula atual só quando ela for observada. Nunca a invente.

  NÃO crie, nesta etapa, uma interface para escolher o PCI de origem e de destino.
- Atualize os testes dos novos montadores de comando: topologia inválida retorna 400, e a lista de argumentos tem o formato certo para cada topologia.
- **Aceitação:** o pytest passa e o frontend compila. *Conferência manual posterior:* comando N2 ao vivo a partir da visão geral.

### WP6: documentar o significado das medidas (relatório §3; item P1 10)

- Amplie o `docs/en/guide-measurement-pipeline.md` com a captura de alta resolução da interrupção:
  - o fluxo do `scripts/measure_interruption.sh`: pings a cada 10 ms, cerca de 2 s antes e cerca de 4 s depois do comando, e as variáveis `INTERRUPTION_*`;
  - a regra do limite de resolução: a estimativa nunca fica abaixo do intervalo entre pings;
  - a regra de interpretação: **estimativa perto de um intervalo, com 0% de perda e nenhum `icmp_seq` faltando, indica handover sem interrupção, e não uma interrupção real. Um `icmp_seq` faltando é o sinal confiável de interrupção.**
- Mostre a mesma interpretação na interface, no cartão de interrupção da visão geral. Quando `packetLoss === 0` e a estimativa for de até cerca de 2 intervalos, mostre ao lado do número: "no measurable user-plane outage (seamless)" (nenhuma interrupção mensurável no plano de usuário).
- **Aceitação:** as seções novas ficam no próprio arquivo, sem criar outro; o frontend compila.

### WP7: padronizar os nomes dos documentos (relatório §4; item P1 9)

- Renomeie os arquivos conforme a regra e inclua-os no índice `docs/en/README.md`:
  - `DASHBOARD_SPEC.md` → `spec-dashboard.md`. Acrescente uma linha "Spec" à regra de nomes, ou use `record-dashboard-spec.md` se preferir não criar categoria nova. Escolha uma opção.
  - `dashboard_phase6_operator_overview.md` → `record-dashboard-phase6-overview.md`;
  - `dashboard_overview_live_handoff.md` → `handoff-dashboard-overview-live.md`;
  - `oai_rfsim_f1_smoke_handoff.md` → `handoff-f1-smoke-auth-failure.md`.

  Use `git mv`. Corrija todas as referências a cada nome antigo (encontre-as com `rg -l`).
- Acrescente um aviso curto no início do `handoff-f1-smoke-auth-failure.md`. Ele deve dizer que o bloqueio de autenticação foi resolvido (PR #17, correção da carga inicial de assinantes). Veja "F1 smoke-test subscriber diagnostics" no `dashboard/README.md`.
- **Aceitação:** o `rg` não encontra referências aos nomes antigos, e todos os documentos de `docs/` aparecem no `docs/en/README.md`.

### WP8: ferramentas do frontend e componentes compartilhados (relatório §6; itens P2 12 e 13)

- Passe o `vite` e o `@vitejs/plugin-react` para `devDependencies`.
- Acrescente o ESLint (configuração *flat*, com `eslint-plugin-react` e o plugin de hooks) e corrija os problemas apontados. Acrescente os scripts `"lint"` e `"test"`.
- Acrescente o Vitest e o @testing-library/react. Primeiros testes:
  1. Tire do `Overview.jsx` as funções puras (`buildInterruptionResult`, `runIdFromTail` e o preenchimento da janela do gráfico ao vivo).
  2. Mova-as para `src/utils/`.
  3. Teste a detecção de falhas, os valores nulos em séries densas, a leitura da linha de marcação e o tamanho do preenchimento.
- Mova o `Pill` e o `Detail` do `Overview.jsx` para `src/components/` e reaproveite-os.
- Acrescente o ESLint e o Vitest ao CI.
- **Aceitação:** `npm run lint`, `npm run test` e `npm run build` passam.

### WP9: sistematizar a interface (análise de design do relatório §6; item P1 11)

Aplique nesta ordem, do menor risco para o maior. Mantenha a identidade visual atual.

- **Tokens de design:** defina cores com significado no `tailwind.config.js`, como extensão do tema, e em um `src/utils/chartTheme.js`. Exemplos: estado bom, alerta e ruim; destaque; texto apagado; séries, perda e anotações dos gráficos. Troque as cores fixas em hexadecimal e as classes de estado repetidas em cada arquivo.
- **Acessibilidade:**
  - indique o estado também sem cor: o `StatusDot` ganha um rótulo ou uma forma;
  - aumente o contraste das etiquetas pequenas (`slate-500` → `slate-400`, com no mínimo 11 px);
  - use `aria-expanded` nos itens recolhíveis da barra lateral;
  - use `aria-current` na aba de navegação ativa;
  - deixe visíveis os contornos de foco (`focus-visible`).
- **Rotas por URL:** use o `react-router-dom`, com uma rota por página. Ligue as rotas com parâmetro `/runs/:runId` e `/campaigns/:campaignId` às telas de detalhe que já existem. A aba ativa vem da rota.
- **Componente `RttChart` compartilhado**, usado pelo gráfico de latência ao vivo e pelo gráfico de interrupção. Ele recebe como propriedades os eixos, a dica (*tooltip*), o arredondamento do eixo y e as anotações de falha e de comando. Use `dot={false}` no traço denso da interrupção.
- Pule nesta etapa, porque precisam de ajustes visuais com o sistema rodando: a reformulação dos cartões de indicadores no topo, as fontes hospedadas no próprio projeto e a barra lateral recolhível.
- **Aceitação:** lint, testes e compilação passam. Não sobra nenhuma cor em hexadecimal no código JSX dos gráficos. Confira com `rg '#[0-9a-f]{6}' dashboard/frontend/src`, que só deve encontrar os arquivos de tokens.

### WP10: limpeza (relatório §8; itens P2 16 e 17)

- Apague a pasta vazia `metrics/`. Ela só tem arquivos `.gitkeep` e foi substituída por `results/`. Antes, confira se nada a cita: `rg -l 'metrics/' scripts tools dashboard docs README.md`. A seção de organização do README vai precisar perder a menção.
- Acrescente a configuração do `ruff` (`pyproject.toml` na raiz do repositório ou em `dashboard/backend`), para lint e formatação de `dashboard/backend` e `tools`. Corrija os achados. Acrescente ao CI.
- NÃO mude de lugar, nesta execução, os arquivos de configuração do F1 na raiz. Isso afeta caminhos usados em tempo de execução pelo `lib.sh`, pelo Compose e pelo registro do painel. É arriscado demais sem acompanhamento.
- **Aceitação:** o conjunto completo de validações e o ruff passam.

## Fora do escopo desta execução

- LICENSE (decisão do dono pendente).
- Tudo o que exigir o testbed rodando:
  - resultados de referência com 20 ou mais execuções;
  - resultados de referência repetidos do N2;
  - conferência ao vivo do comportamento do WP5 e do WP6;
  - trabalho com USRP (relatório §7.2, fases 1 a 4).
- Mudanças na ferramenta de commit automático, reescrita do histórico do git e criação de etiquetas.
- Mudança de lugar dos arquivos de configuração da raiz, reformulação dos cartões de indicadores, barra lateral recolhível e fontes.

## O que o resumo final deve ter

Termine com:

- o estado de cada pacote (feito ou pulado, e por quê);
- todas as escolhas de julgamento feitas;
- a lista de itens que precisam de conferência com o testbed rodando;
- a confirmação de que o conjunto completo de validações e o workflow do CI passam.
