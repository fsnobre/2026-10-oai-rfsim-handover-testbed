# Handoff: Evaluation Remediation Implementation

> **Document type:** Handoff
>
> **Date:** 2026-07-03
>
> **Required reading:** [Repository evaluation report](report-repository-evaluation.md) (the *why* behind every task here), `CLAUDE.md` at the repo root (hard invariants and validation suite).

This document turns the evaluation report's recommendations into ordered, scoped work
packages for an implementation agent running unattended. The report explains and
justifies; this document instructs. Where they seem to disagree on scope, this document
wins.

## Ground rules for the implementing agent

1. Obey every invariant in `CLAUDE.md`. In particular: explicit staging only (never
   `git add -A`), no pushing, no weakening of the dashboard action-safety model, no
   fabricated telemetry values.
2. Work through the packages **in order**. Commit once per completed work package with a
   descriptive message. If a package fails its acceptance check, fix or revert it before
   moving on — do not leave the tree broken between packages.
3. The live OAI testbed is **not running**. Acceptance for every package is the static
   validation suite in `CLAUDE.md` (plus package-specific checks below). Anything
   requiring a live stack is explicitly marked *manual follow-up* — implement it, verify
   statically, and list it in your final summary as "needs live verification".
4. Decisions already made by the owner — do not re-litigate:
   - **License: deferred.** Do NOT add a LICENSE file. Where the report says "add a
     license", skip it and note it as blocked-on-owner.
   - **Scope: everything below** (P0 through P2), except items marked skip.
5. If something is ambiguous, choose the smallest change consistent with the report and
   record the choice in your final summary. Do not expand scope beyond these packages.

## Work packages

### WP1 — Repo hygiene (report §8; P0 items 1, 3)

- Rewrite `.gitignore`: deduplicate the concatenated templates into one intentional
  file (~40 lines) that preserves all currently-effective rules (results/logs run
  artifacts with `.gitkeep` keeps, Python caches, venvs, `.env` with `!.env.example`,
  `dist/`) and **adds `node_modules/`**. Verify with `git status --short` that no
  currently-tracked file becomes ignored and nothing new appears staged.
- Add a GitHub Actions workflow at `.github/workflows/ci.yml` running on push/PR:
  (a) the full validation suite from `CLAUDE.md` (backend validators, compose config,
  subscriber seed, frontend `npm ci && npm run build`); (b) `bash -n` on all
  `scripts/*.sh`; (c) `shellcheck` (via the standard shellcheck action; treat warnings
  as non-fatal initially — `SHELLCHECK_OPTS=-S error` — so the first CI run is green).
  Use `docker compose config` only (no stack startup). Pin action versions.
- Do NOT touch the auto-commit tool (external to the repo). Do NOT add a LICENSE
  (deferred). Tagging `baseline-2026-06-19` is owner's call — skip.
- **Acceptance:** validation suite passes locally; the workflow YAML parses
  (`docker run --rm rhysd/actionlint` if available, otherwise careful review);
  `node_modules/` no longer shows in `git status`.

### WP2 — Fix shellcheck-reported defects (report §2)

- Run shellcheck (install locally if possible: `sudo apt-get install -y shellcheck`
  or use a container) across `scripts/*.sh`. Fix `error`-severity findings; fix
  `warning`-severity findings only where the fix is obviously safe (quoting, unused
  vars). Do not restructure scripts.
- **Acceptance:** `bash -n` clean; shellcheck error-free; validators still pass
  (several assert on script paths/behavior).

### WP3 — pytest port of the backend validators (report §5; P1 item 7)

- Convert `validate_phase2..6.py` and `validate_registry.py` into pytest tests under
  `dashboard/backend/tests/`, named by subject (`test_state.py`, `test_runs.py`,
  `test_handover.py`, `test_actions.py`, `test_campaigns.py`, `test_overview.py`,
  `test_registry.py` — match actual content when splitting). Preserve every existing
  assertion, including the source-code assertions (`shell=True` absent, etc.).
- Keep the original `validate_*.py` files as thin wrappers that invoke pytest (so
  documented commands keep working), or update every documented reference
  (`dashboard/README.md`, `docs/en/record-dashboard-phase6-overview.md`, CI from WP1,
  `CLAUDE.md`) — pick one approach and apply it consistently.
- Add `pytest` to a new `dashboard/backend/requirements-dev.txt` (do not add it to
  runtime `requirements.txt`).
- Add golden-file tests for `tools/parse_ping.py`: a synthetic `ping_raw.log` +
  `events.csv` fixture with a known gap (expected `estimated_interruption_ms`), a
  precheck-contamination fixture (regression for the historical parser bug), and a
  0%-loss seamless case. Place under `tools/tests/`.
- **Acceptance:** `pytest dashboard/backend tools` green; CI updated to run it.

### WP4 — Backend auth + CORS (report §5, §9; P1 item 8)

- Add optional static bearer-token auth: env var `DASHBOARD_API_TOKEN`; when set,
  require `Authorization: Bearer <token>` on all `/api/actions/*` endpoints and the
  `/ws` handshake (query param or header for WS). When unset, behavior is unchanged
  (lab default). Reject with 401, never crash.
- Replace `allow_origins=["*"]` with `DASHBOARD_CORS_ORIGINS` (comma-separated, default
  `*` to preserve current lab behavior; document that production-ish use should set it).
- Frontend: read the token from a simple settings affordance (e.g. `localStorage` key +
  small input on the Controls page) and attach it to `apiPost`/`apiGet`/WS when present.
- Document in `dashboard/README.md` (keep the existing "do not expose on untrusted
  networks" warning).
- **Acceptance:** validators/pytest green with the feature both unset and set (add
  tests for 401-when-token-set, pass-when-correct).

### WP5 — N2 support in Overview actions (report §7.1; P1 item 5)

- `build_trigger_handover_command` and `build_measure_interruption_command` take a
  validated topology argument (`f1`, `n2-monolithic`, `n2-cu-du` — same whitelist
  pattern as smoke tests) instead of hardcoded `"f1"`; the action manager passes the
  backend's detected topology. `scripts/trigger_handover.sh` and
  `scripts/measure_interruption.sh` already accept these values.
- `/api/actions/capabilities` exposes per-action supported topologies; the Overview
  uses that instead of the frontend-side `topology === "f1"` checks. Button labels and
  the hero title become topology-aware ("Trigger N2 handover", "N2 monolithic RFsim
  handover cockpit", etc.).
- N2 direction honesty (design minimum, not full direction control): when topology is
  N2, show a caption on the trigger card stating that repeated same-direction triggers
  require a topology reset (`RESET_BETWEEN_RUNS=1` semantics), and show the serving
  cell only when observed — never invent it. Do NOT build source/target PCI selection
  UI in this pass.
- Update tests for the new command builders (bad topology → 400; argv shape per
  topology).
- **Acceptance:** pytest green; frontend builds; *manual follow-up:* live N2 trigger
  from the Overview.

### WP6 — Measurement-semantics documentation (report §3; P1 item 10)

- Extend `docs/en/guide-measurement-pipeline.md` with the high-resolution interruption
  capture: `scripts/measure_interruption.sh` flow (10 ms probes, ~2 s pre / ~4 s post,
  `INTERRUPTION_*` env overrides), the resolution-floor rule (estimate is floored by
  the probe interval), and the interpretation rule: **estimate ≈ one probe interval
  with 0% loss and no missing icmp_seq ⇒ seamless handover, not a real outage; missing
  icmp_seq is the honest outage signal**.
- Surface the same interpretation in the UI: on the Overview interruption card, when
  `packetLoss === 0` and the estimate is ≤ ~2× the probe interval, show "no measurable
  user-plane outage (seamless)" alongside the number.
- **Acceptance:** doc indexed if new sections warrant no new file (they don't — edit in
  place); frontend builds.

### WP7 — Docs convention pass (report §4; P1 item 9)

- Rename to convention and index in `docs/en/README.md`:
  `DASHBOARD_SPEC.md` → `spec-dashboard.md` (add a "Spec" naming-convention line, or
  use `record-dashboard-spec.md` if you prefer zero new categories — pick one),
  `dashboard_phase6_operator_overview.md` → `record-dashboard-phase6-overview.md`,
  `dashboard_overview_live_handoff.md` → `handoff-dashboard-overview-live.md`,
  `oai_rfsim_f1_smoke_handoff.md` → `handoff-f1-smoke-auth-failure.md`.
  Use `git mv`. Fix every inbound reference (`rg -l` for each old name).
- Add a short resolution banner at the top of `handoff-f1-smoke-auth-failure.md`
  noting the auth blocker was resolved (PR #17, seed fix — see
  `dashboard/README.md` "F1 smoke-test subscriber diagnostics").
- **Acceptance:** `rg` finds no references to old filenames; every doc in `docs/`
  appears in `docs/en/README.md`.

### WP8 — Frontend tooling + shared primitives (report §6; P2 items 12, 13)

- Move `vite` and `@vitejs/plugin-react` to `devDependencies`.
- Add ESLint (flat config, `eslint-plugin-react` + hooks plugin) and fix reported
  issues; add `"lint"` and `"test"` scripts.
- Add Vitest + @testing-library/react. First tests: extract the pure helpers from
  `Overview.jsx` (`buildInterruptionResult`, `runIdFromTail`, the live-chart window
  padding) into `src/utils/` and test those (gap detection, dense-series nulls,
  sentinel parsing, padding length).
- Promote `Pill` and `Detail` from `Overview.jsx` into `src/components/` and reuse.
- Add ESLint + Vitest to CI.
- **Acceptance:** `npm run lint`, `npm run test`, `npm run build` all green.

### WP9 — UI systematization (report §6 design review; P1 item 11)

Apply in this order, smallest risk first; keep the existing visual identity.

- Design tokens: define semantic colors (status ok/warn/bad, accent, muted text, chart
  series/loss/annotation) in `tailwind.config.js` theme extension plus a
  `src/utils/chartTheme.js`; replace hardcoded hexes and per-file status classes.
- Accessibility: non-color status cues (`StatusDot` gains a paired label/shape),
  raise micro-label contrast (`slate-500` → `slate-400`, min 11px), `aria-expanded`
  on sidebar collapsibles, `aria-current` on active nav tab, visible
  `focus-visible` rings.
- URL routing: `react-router-dom`; one route per page, param routes
  `/runs/:runId` and `/campaigns/:campaignId` wired to the existing detail views;
  active tab derives from the route.
- Shared `RttChart` component consumed by both the live latency and interruption
  charts (axes, tooltip, y-max rounding, gap/trigger annotations as props);
  `dot={false}` for the dense interruption trace.
- Skip for this pass (needs live visual iteration): KPI stat-tile hero rework,
  self-hosted fonts, collapsible sidebar rail.
- **Acceptance:** lint/test/build green; no `#`-hex literals left in JSX chart code
  (`rg '#[0-9a-f]{6}' dashboard/frontend/src` limited to the token files).

### WP10 — Cleanup (report §8; P2 items 16, 17)

- Delete the empty `metrics/` tree (only `.gitkeep`s; superseded by `results/`).
  Verify nothing references it first (`rg -l 'metrics/' scripts tools dashboard docs
  README.md` — README's layout section will need its mention removed).
- Add `ruff` config (`pyproject.toml` at repo root or `dashboard/backend`): lint +
  format for `dashboard/backend` and `tools`; fix findings; add to CI.
- Do NOT relocate the root-level F1 conf files in this run (touches runtime paths in
  `lib.sh`, compose, dashboard registry — too risky unattended).
- **Acceptance:** full suite + ruff green.

## Explicitly out of scope for this run

- LICENSE (owner decision pending).
- Anything requiring the live testbed: n≥20 baselines, repeated N2 baselines, live
  verification of WP5/WP6 behavior, USRP work (report §7.2 phases 1–4).
- Auto-commit tool changes, git history rewriting, tagging.
- Root-level conf relocation; KPI hero redesign; sidebar rail collapse; fonts.

## Final summary requirements

End with: per-package status (done/skipped + why), every judgment call made, the list
of items needing live-testbed verification, and confirmation that the full validation
suite and CI workflow pass.
