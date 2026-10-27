# Repository Evaluation: Practices, Standards, and User Experience

> **Document type:** Report
>
> **Date:** 2026-07-03
>
> **Context:** Whole-repository review — automation harness, measurement pipeline, documentation set, and dashboard — compared against software-engineering best practices, industry standards, and operator/researcher user experience.

## 1. Scope and method

This report evaluates everything built in this repository to date:

- the RFsim handover automation harness (`scripts/`, `tools/`, `experiments/`, `oai-cn5g/`);
- the measurement pipeline and its result artifacts (`results/`);
- the documentation set (`docs/`);
- the web dashboard (`dashboard/backend`, `dashboard/frontend`);
- repository hygiene (git history, ignore rules, licensing, CI, tooling).

Each area is scored against three lenses: **best practices** (would a senior engineer sign off on this?), **industry standards** (what comparable open-source telecom/testbed projects do), and **user experience** (a researcher or demo operator using it cold). Findings are ranked at the end into prioritized recommendations.

**Overall verdict:** this is an unusually disciplined research testbed. The measurement methodology, readiness modeling, safety posture of the dashboard actions, and documentation architecture are all *above* the norm for academic testbed repositories — several practices here (validity gates, confidence-labeled telemetry, curated validated results) are worth publishing as methodology in their own right. The gaps fall into two families: **project infrastructure** (no CI, no license, noisy git history, non-standard test tooling, mutable image tags, a drifted documentation index) and **coverage parity** — the dashboard cockpit serves F1-on-RFsim only, while the harness underneath already supports N2 and (partially) USRP real radio (Section 7).

---

## 2. Automation harness (`scripts/`, `tools/`)

### What is done well

- **Shell discipline.** Every script uses `set -euo pipefail`, resolves paths from `BASH_SOURCE`, and sources a single shared `lib.sh` (570 lines) for topology selection, readiness helpers, and network validation. Configuration is layered correctly: CLI arg → environment variable → `config.yaml` default → hardcoded fallback (see the `IPERF_*` cascade in `run_smoke_test.sh`). This is textbook 12-factor-style configurability for shell tooling.
- **"Never sleep and hope."** The stated design principle — poll for an observable condition instead of fixed delays — is actually followed. The only fixed sleeps are deliberate measurement windows, and the docs say so explicitly. Most testbed repos get this wrong.
- **Crash-safe result records.** `run_smoke_test.sh` installs `trap finish_summary EXIT` immediately after creating the run directory, so *every* exit path produces a `summary.json` with boolean progress gates. A run that dies mid-way still leaves a structured record of how far it got. This is a genuinely strong pattern.
- **Layered readiness (F01).** The eight-layer readiness model (host → container → transport → radio → control plane → session → user plane → handover) with explicit non-implications (`container running != RFsim connected`, etc.) is the intellectual backbone of the harness and is correctly encoded in `preflight_check.sh` / `up.sh` / `status.sh` / `wait_ue_data_ready.sh` with clear separation of responsibilities.
- **Diagnostics as first-class tooling.** `diagnose_dn_reachability.sh` is read-only, writes structured evidence under `results/diagnostics/`, and distinguishes `tool_missing` from real reachability failure — a subtle correctness point (the UPF container lacks `ping`) that was found the hard way and then institutionalized.
- **Preflight failure catalog.** The README's failure-mode table (Tailscale/WireGuard routing, stale containers, missing TUN/SCTP modules, AppArmor, clock skew) maps one-to-one onto automated preflight checks. Encoding known operational failure modes as executable checks is exactly what industrial test automation does.

### Gaps

- **No `shellcheck` anywhere.** It is not installed on the dev host and nothing runs it. For ~3,300 lines of bash across 23 scripts, static analysis is the single cheapest defect filter available. (Priority: high, trivial cost.)
- **No script-level tests.** The bash layer is verified only by running the real testbed. Most of `lib.sh` (topology parsing, config readers, network spec validation) is pure logic that could be exercised by a fast bats-core or even plain-bash test file without Docker.
- **`tools/` parsers lack unit tests.** `parse_ping.py` computes the headline research metric (`estimated_interruption_ms`) and has already had one real bug (precheck-statistics contamination, fixed and documented). There is still no regression test pinning that fix with a synthetic `ping_raw.log` + `events.csv` fixture. For a metric that will appear in publications, a golden-file test is the standard bar.
- **Fragile event-name contract.** The interruption estimate silently becomes `null` if `handover_trigger_start` is ever renamed. The guide documents this ("keep the event name stable"), which is good, but a shared constant (single definition consumed by `trigger_handover.sh` and `parse_ping.py`) or a parser warning when events.csv contains handover-ish events with no recognized name would turn a documented trap into an enforced contract.

---

## 3. Measurement methodology and scientific rigor

### What is done well

- **"Trustworthy or explicitly invalid — never silently wrong."** Validity gates (`ping_metrics_valid`, `packets_transmitted != 0`) are re-checked after parsing, and a run with a sent handover command but unusable samples is *failed*, with a `ping_metrics_invalid` event. Silent-wrong is the most common failure of academic measurement pipelines; this repo designed against it explicitly.
- **Honest resolution accounting.** The docs state plainly that the 0.2 s ping interval bounds the interruption estimate, that RTT includes RFsim/Docker/host-scheduling noise, and that a single run per topology is a sanity check, not a baseline. `report-baseline-results.md` freezes the historical ping-only numbers and explicitly refuses to retroactively mix in iperf data ("a new multi-run iperf baseline should be recorded separately"). This is correct data provenance practice.
- **Curated validated results.** `results/validated/2026-06-19/` commits a chosen reference set while `.gitignore` excludes raw run output. Separating "evidence we stand behind" from "working artifacts" is what reproducibility guidelines (e.g., ACM artifact badging) ask for.
- **Statistics handled honestly in the dashboard.** Nulls are excluded from campaign statistics rather than coerced; nearest-rank p95; deterministic results; malformed artifacts produce warnings, never fabricated values.

### Gaps

- **Sample sizes and uncertainty.** The published baseline is n=5 with mean/std/min/max. The docs already acknowledge that a real comparative study needs repeated cold-start trials and confidence intervals — the tooling supports `RUNS=20`; the missing piece is just running and documenting a larger baseline with CIs (and the repeated-runs aggregator emitting a confidence interval alongside mean/std would make that automatic).
- **Mutable image tags undermine reproducibility.** All OAI images are pinned to `:develop` (and `ims:latest`). The measurement guide itself lists "pinned image digests" as a requirement for a real study, and the README's "OAI version v2.4.0" table row does not match the `develop` tags actually in the compose files. Recommendation: pin by digest (`image: oaisoftwarealliance/oai-gnb@sha256:…`) or at minimum a fixed version tag, record the digests in each run's `summary.json`, and reconcile the README claim.
- **Interruption-resolution semantics deserve a doc.** The new high-rate interruption measurement (10 ms probes via `scripts/measure_interruption.sh` and the Overview card) fixes the resolution problem, but the key interpretation rule — *an estimate ≈ one probe interval with 0% loss means a seamless handover, not a real outage; missing icmp_seq is the honest outage signal* — currently lives only in session history. It should be written into `guide-measurement-pipeline.md` (and ideally displayed in the UI) before anyone quotes those numbers.

---

## 4. Documentation (`docs/`)

### What is done well

- **A real information architecture.** The purpose-based taxonomy (`foundation-fNN` / `guide` / `tutorial` / `report` / `record` / `handoff`) with stable foundation IDs, explicit "required reading" headers, and per-goal reading paths in `docs/README.md` is a homegrown equivalent of the Diátaxis framework and better organized than the documentation of most established open-source projects. The rule "IDs are identifiers, not difficulty levels; never renumber" shows real curation intent.
- **Foundations capture *why*, not just *how*.** F00 (network ownership: why `docker network create` by hand is a trap), F01 (readiness invariants), F04 (enum-index config values like `ra_ResponseWindow = 4` meaning 10 slots) — each one records a class of mistake and the rule that prevents it. This is institutional memory done right.
- **Load-bearing rationale is written down.** The precheck/long-capture file separation is documented *with the race it prevents*; the event-name dependency is flagged; the UE-as-RFsim-server constraint and its multi-UE ceiling are called out in the xApp handoff. A new contributor can learn why the code is shaped the way it is.
- **Handoff documents as a genre.** `handoff-xapp-integration.md` (context for a future research effort, with a phased E2/FlexRIC integration plan and named risks) and the smoke-failure handoff are excellent practice for multi-session, multi-agent research work.

### Gaps

- **The index had drifted** (resolved 2026-07-03). Four newer documents followed neither the naming convention nor appeared in `docs/README.md`. They were renamed to `spec-dashboard.md`, `record-dashboard-phase6-overview.md`, `handoff-dashboard-overview-live.md`, and `handoff-f1-smoke-auth-failure.md`, and all are now indexed (a `spec-` category was added to the naming convention).
- **Phase-numbered names encode history, not content.** "Phase 6" is meaningful only to someone who lived through phases 1–5. Purpose-based names (which the taxonomy already prescribes) age better; keep phase numbers inside the document body as history.
- **Stale-state risk in handoffs** (resolved 2026-07-03). The F1 smoke-test handoff described a then-current blocker (AUSF `CONTEXT_NOT_FOUND`) that was subsequently fixed (PR #17); it now carries a one-line resolution banner. Remaining handoff/record docs should get the same treatment when their central problem is resolved, so a future reader doesn't re-debug a fixed issue.
- **`record-development-history.md` is chat-shaped.** It is honest and useful, but written as "you/we" session narration. Fine for a `record-`, worth knowing that it reads as provenance, not reference — the index correctly classifies it, so this is a minor note.

---

## 5. Dashboard backend

### What is done well

- **The action-safety model is the standout.** Disabled by default; explicit `confirm` required; whitelisted scripts only with fixed argv (no `shell=True` anywhere — and the validators *assert on the source code* that this stays true); single-job concurrency (409 on overlap); process-group SIGTERM→SIGKILL timeout handling; bounded 200-line output tails; read-only repo mount except `results/`; capabilities endpoint that *reports its own safety guarantees*. This is a better command-execution posture than many commercial internal tools.
- **Degraded-mode-first design.** The backend is required to start and stay useful with the testbed down, Docker socket broken, telnet unavailable, or artifacts malformed — all surfaced as warnings, never crashes. The validators test empty/malformed/missing-artifact cases explicitly.
- **Epistemically honest telemetry.** The `observed / parsed / inferred / unknown` confidence taxonomy, the strict separation of "AMF registration events seen in logs" from "currently attached UE count", and the rule that an unobserved serving DU renders as "DU not observed" rather than an invented `UE → Unknown → CU` path — this is a research-grade honesty standard almost no dashboard meets. It should be kept as a hard invariant.
- **Operational lessons captured in code.** Passive CU telnet polling is disabled by default because repeated `help` probes crashed the OAI CU (`*** buffer overflow detected ***`); when enabled it is rate-limited with cached capability discovery. Host-visible bind-mount paths for Docker-in-Docker-adjacent actions are documented with a working compose override.

### Gaps

- **No authentication and `allow_origins=["*"]`.** Documented honestly ("do not expose on untrusted networks when actions are enabled"), and acceptable for a single-host lab. But actions-enabled mode drives the host Docker daemon; the standard next step is cheap: a static bearer token (env var, checked by middleware on `/api/actions/*` and `/ws`) and a CORS origin list defaulting to the frontend origin. That converts a documented warning into an enforced control.
- **Custom validators instead of pytest.** `validate_phase2..6.py` + `validate_registry.py` are real tests with good coverage, but the bespoke runner has already caused one masked failure (an `AssertionError` that exited 0 during this project's own development). Porting the functions to pytest is nearly mechanical (they already look like test functions), buys granular reporting, `-k` selection, fixtures, and removes the exit-code class of bugs. Keep `validate_registry.py` drift-checking — that idea (assert the dashboard's container registry against the actual compose files) is excellent.
- **Phase-numbered test files.** Same accretion problem as the docs: `validate_phase4.py` tells you *when* it was written, not *what* it protects. Rename by subject (`test_actions.py`, `test_campaigns.py`, …) during the pytest move.
- **In-memory-only job state** resets on restart (documented). Fine for now; if campaigns grow longer than backend uptime, persist minimal job records under `results/`.

---

## 6. Dashboard frontend and operator UX

### What is done well

- **Overview-as-cockpit is the right call.** The Phase 6 redesign was driven by real operator feedback (dedupe cards, collapse groups, remove stale badges, replace a misleading "live handover duration" with a live packet-delivery plot) and, crucially, the *reasoning* was recorded. Iterating a monitoring UI against actual demo use is the industry-standard path; documenting each iteration is rarer.
- **Truthful visualization.** The live latency chart renders missed probes as gaps/markers instead of interpolating through them; the new interruption chart breaks the line on missing icmp_seq (`connectNulls=false`) and marks the trigger with a reference line and the gap with a shaded band. Not lying through interpolation is the most important chart-integrity rule and it is followed.
- **Empty and unavailable states are designed, not accidental** ("No live latency samples yet…", Unavailable labels, RFsim-synthetic KPI caveats). The validation checklist explicitly requires the Overview to render with the stack down and with zero historical runs.
- **Sane, lean stack.** React 18 + Vite + Recharts + Tailwind, no state-management framework the app doesn't need, WebSocket for push with REST for artifacts, large artifacts deliberately kept off the socket.

### Gaps

- **Zero frontend tests and no linting.** There is no ESLint/Prettier config and no test runner in `package.json`. The empty-state regression that was caught by hand this week (`data.length` vs `visibleSamples.length` after window-padding) is precisely the class of bug a component test would pin. Minimum bar: ESLint + a handful of Vitest/react-testing-library tests for the data-shaping helpers (`buildInterruptionResult`, run-ID sentinel parsing, window padding) — those are pure functions and trivially testable.
- **Build tooling in the wrong dependency block.** `vite` and `@vitejs/plugin-react` are in `dependencies` rather than `devDependencies`. Cosmetic in a Docker build, but it misstates the runtime footprint.
- **Page components are drifting large.** `Overview.jsx` is ~490 lines and `CampaignsPage.jsx` ~425, holding data-fetching, transformation, and presentation together. Extracting the pure data-shaping functions into `src/utils/` would both shrink the pages and make them testable (same refactor serves both gaps).
- **UX polish opportunities** (small, in impact order):
  1. Show the "≤ one probe interval + 0% loss ⇒ no measurable outage (seamless)" interpretation directly on the interruption card, so the operator can't misread 11 ms as a real outage.
  2. Persist last-seen results (e.g., `localStorage` or re-fetch latest run on mount) so a page refresh doesn't blank the interruption card.
  3. A visible "actions disabled" affordance that says *how* to enable them (the exact env-var command), not just a disabled button.

### UI and visual design review

The repo has no stated design requirements, so this section evaluates the UI against general design best practices and names the techniques that would raise it. The current look — dark slate base (`#0f172a`/`slate-950`), glassy cards (`rounded-2xl border-white/10 bg-white/[0.06]`), a single cyan accent, emerald/amber/rose status hues, monospace for technical values, tracked uppercase micro-labels — is already coherent and appropriate for an ops console. The dashboard spec's design direction ("dense but organized, monitoring tool for researchers") is being followed. What follows is how to go from "clean" to "well-designed":

1. **Introduce design tokens (the highest-leverage design technique here).** Colors are hardcoded per file today: chart hexes (`#22d3ee`, `#fb7185`, `#94a3b8`) inside Recharts props, status colors duplicated between `StatusDot`, `Pill`, and chart markers, and only one shared class (`.card`). Define semantic tokens once — `status-ok`, `status-warn`, `status-bad`, `accent`, `text-muted`, plus a small chart palette — in the Tailwind theme and a tiny `chartTheme.js`, and consume them everywhere. This makes every future page consistent by default instead of by discipline, and makes a light theme or print/export styling a token swap rather than a rewrite.
2. **Accessibility is the biggest concrete defect.** `StatusDot` encodes container health with color alone (green/orange/red), which fails WCAG 1.4.1 (use of color) and is indistinguishable for red-green colorblind users — pair the dot with a short text/badge (it already sits next to `health || status` text in the sidebar rows, so the fix is mostly to guarantee that pairing everywhere and add an icon/shape difference). Micro-labels at ~10px in `text-slate-500` (`#64748b`) on near-black are borderline on WCAG AA contrast for small text — lift to `slate-400` and ≥11px. Add `aria-expanded` on the collapsible sidebar cards, `aria-current` on the active nav tab, and visible `focus-visible` rings (the dark theme makes default focus outlines nearly invisible). Technique: adopt Radix UI primitives (or shadcn/ui) for tabs/collapsible/toast — they ship correct keyboard and ARIA behavior for free while keeping the existing Tailwind styling.
3. **Add URL routing.** Navigation is `useState("Overview")` — a refresh dumps the operator back to Overview, no page or run can be deep-linked or shared, and the browser back button does nothing. A monitoring tool lives on shareable URLs (`/runs/<id>`, `/campaigns/<id>`). `react-router` with one route per page plus param routes for run/campaign detail is a half-day change and the single biggest usability upgrade available.
4. **Establish visual hierarchy around the numbers that matter.** The Overview's headline research metric — interruption ms — renders as a small pill, while a mostly-static hero paragraph gets the largest text on the page. Invert that: replace the hero prose with a KPI strip of stat tiles (stack health, serving DU, last interruption, live delivery state, packet loss) using large numerals with small labels, and let explanatory prose live in tooltips/captions. Dense-console best practice is "biggest ink = most important value."
5. **Consolidate the chart code.** `LiveLatencyChart` and the interruption chart duplicate axis, tooltip, y-max rounding, and line styling with slight drift. Extract one shared `RttChart` (axes, tooltip formatting, gap/trigger annotation props) — this yields visual consistency, halves the code, and gives one place to fix chart-wide issues. Chart-specific improvements: for the dense 10 ms trace, drop per-point dots (`dot={false}` with `activeDot`) — 600 dots at r=2 is visual noise and render cost; give the live chart a real time axis (it currently plots slot indexes with mostly-empty tick labels); when a quick handover fires, annotate the trigger moment on the *live* chart too (the backend knows the job start time), tying the two cards together; and use a distinct marker shape (not only color) for missed probes.
6. **Promote the locally-defined primitives.** `Pill` and `Detail` are defined inside `Overview.jsx`; other pages will (or already do) re-implement variants. Move them to `components/` alongside `StatusDot`/`MetricCard` and make them the only way status chips and key-value details are rendered.
7. **Typography.** The spec calls for Inter + JetBrains Mono; the app currently ships system defaults. Self-host both via `@fontsource` (no CDN dependency, fine for offline labs) — monospace tabular numerals in particular stop the live RTT pill from jittering in width as values change.
8. **Layout details.** The fixed `w-80` sidebar is not collapsible and the two-column grid only splits at `xl` — on a typical 1366px laptop everything stacks. Make the sidebar collapsible (it already has per-card collapse; add whole-rail collapse) and tune the breakpoint to `lg`. Keep the current information-density philosophy; do not add decoration.

None of this is a redesign — the aesthetic is fine. It is systematization: tokens, accessibility semantics, routing, hierarchy, and shared primitives.

---

## 7. Topology and radio coverage parity (F1-only vs N2, RFsim vs USRP)

The testbed layer supports three RFsim handover topologies plus USRP X310 real-radio operation. The dashboard — and especially the Overview cockpit — currently serves **one** of those combinations: F1 on RFsim. This asymmetry is the largest *functional* gap in the project, and it is worth stating precisely, because part of it is trivial to close and part of it is a real design problem.

### 7.1 N2 support in the Overview (cheap to close)

Current state, verified in code:

- `actions.py` hardcodes `"f1"` into the trigger argv (`trigger_handover.sh f1`) and into the interruption-capture argv (`measure_interruption.sh f1`).
- The Overview gates both the quick trigger and the interruption card on `topology === "f1"`, and the hero titles itself "F1 RFsim handover cockpit".
- The backend config parser returns `not_implemented_in_phase_1` for non-F1 topologies, so N2 stacks get container status but no parsed config or topology diagram detail.

Meanwhile the *harness underneath already supports all of it*: `trigger_handover.sh` handles all three topologies (with auto-detection and `N2_SOURCE_GNB_TELNET_HOST`/`N2_TARGET_PCI`/`N2_UE_RRC_ID` overrides), `measure_interruption.sh` takes a topology argument and computes its run tag for all three, and the smoke/repeated-smoke actions already accept `n2-monolithic`/`n2-cu-du`. The F1-only restriction lives almost entirely in the dashboard layer. Closing it:

1. Make `build_trigger_handover_command` and `build_measure_interruption_command` take the *detected* topology (the backend already computes `active_topology()`), keeping the existing whitelist validation.
2. Make the Overview topology-aware: dynamic title, dynamic button label ("Trigger N2 handover → PCI 1"), and per-topology support flags in `/api/actions/capabilities` instead of a frontend-side `=== "f1"` check.
3. Extend the config parser/topology diagram to the two N2 shapes (2 gNBs; 2 CU+DU pairs) — the registry entries for container discovery already exist.

One genuinely new UX problem comes with N2, and it deserves design rather than wiring: **direction**. After an N2 handover the UE sits on the target gNB, so a second same-direction trigger silently no-ops or fails; the harness solves this with `RESET_BETWEEN_RUNS=1`. The Overview should surface the current serving cell (the honest confidence-labeled way, as it already does for F1 serving DU) and either offer a direction-aware trigger (source/target PCI selection, bounded and validated server-side like the repeated-count parameter) or clearly tell the operator that a reset is needed before re-triggering. Anything less will produce confusing "trigger did nothing" demos.

### 7.2 USRP / real radio (a real design problem, phase it)

The dashboard has no notion of `usrp-cots` or the distributed `usrp_handover` topologies, and — more fundamentally — its two signature Overview features are built on RFsim assumptions:

- The live latency probe and the interruption capture both measure from *inside the `oai-nr-ue` container* (`docker exec oai-nr-ue ping -I oaitun_ue1 …`). With a COTS phone there is no UE container, no `oaitun_ue1`, and no shell on the UE. The docs already acknowledge this ("data-plane measurement from the handset is manual; automated smoke tests are rfsim-only") — the point here is that the dashboard's headline features inherit that limitation wholesale.
- The Docker monitor watches the *local* socket only. In the distributed one-radio-per-host deployment, every RAN node is on a different host, so the dashboard would show an empty/red RAN even when the testbed is healthy.

Recommended phasing, cheapest first:

1. **Single-host `usrp-cots` (mostly wiring).** Register the topology, show gNB container health, NG association, and AMF-log registration events (all already collectible locally). Suppress the UE-container-based cards honestly ("COTS UE — no in-container probe available") instead of showing them broken.
2. **Pivot the real-radio Overview to the metrics that become *real*.** On RFsim, RF KPIs (CQI, RSRP, BLER, MCS) are synthetic and the dashboard rightly deprioritizes them; on real radio they are the interesting data, and gNB telnet MAC stats become genuinely valuable. The existing rate-limited telnet poller (currently disabled by default for CU-stability reasons) is the natural source; per-UE MAC stats from the gNB side work regardless of UE type. Radio-health signals (underflow/overflow counts from gNB logs) belong on this Overview too — they are the USRP failure mode the operator actually watches for.
3. **User-plane measurement with a COTS UE needs a new measurement design, not a port.** Realistic options, in increasing effort: downlink probing from `oai-ext-dn` toward the phone's UPF-assigned IP (works only if the handset answers ICMP — many don't); UPF/SMF session counters as a delivery proxy; or a small measurement agent app on the phone (iperf3 server / UDP echo), which is the only way to get an interruption number comparable to the RFsim baseline. This is roadmap-level work — the README already lists "automated measurement from a COTS UE" as a future milestone — but the *report-level* point is: do not present RFsim interruption numbers and future real-radio numbers as the same metric without documenting the measurement-path difference.
4. **Distributed visibility is the biggest lift and should be scoped deliberately.** Options: one dashboard instance per host (works today, no code, poor UX); SSH/`docker context`-based remote container polling; or a thin per-host status agent. Note that the *action* path is already distributed-ready — `trigger_handover.sh` env overrides reach remote telnet endpoints over the LAN — so a middle ground exists where one dashboard can trigger and observe handover on a distributed deployment while container health remains per-host.

### 7.3 Same lens applied beyond the dashboard

The F1/RFsim-first bias is milder in the rest of the repo but present: the baseline report and validated results are F1-centric (single validated runs exist for the N2 topologies; no repeated N2 baseline is published), and the new high-resolution interruption capture has been exercised on F1 only even though the script accepts all three topologies. A repeated N2 baseline (both variants, with resets) would make the three-topology claim of the repo empirically symmetric and is pure machine time with existing tooling.

## 8. Repository hygiene, git, and project infrastructure

This is where the repo diverges most from industry standard, and every item is cheap to fix.

- **No CI.** The repo has an excellent validation suite (`compileall`, six validators, registry drift check, frontend build, `docker compose config`, subscriber-seed validation — all listed in `dashboard/README.md`) and *nothing runs it automatically*. A single GitHub Actions workflow running exactly that list plus `shellcheck scripts/*.sh` and `bash -n` would catch the constructor-propagation and pinned-check-set breakages that have already happened in practice. This is the highest-leverage single improvement available.
- **No LICENSE.** On GitHub, no license means all-rights-reserved: nobody may legally reuse or cite-and-build-on this testbed, which defeats the purpose of a research artifact. OAI components are OAI Public License / Apache-adjacent; the harness itself can be Apache-2.0 or MIT. Add one file.
- **Git history noise.** 14 of 57 commits on `main` are auto-commit "." messages interleaved with real PR-based work. This destroys bisectability and makes `git log` unreadable. Point the auto-commit tool at a scratch branch (or disable it), and keep `main` PR-only. Also: tag the validated baselines (`baseline-2026-06-19`) so published numbers are pinned to a commit.
- **`.gitignore` is two templates concatenated.** The Python GitHub template and a local block are pasted together, duplicating `results/runs/*`, `__pycache__/`, `.venv/` etc. — and despite ~300 lines, **`node_modules/` is not ignored** (it shows as untracked right now, one auto-commit misfire away from a 200 MB commit). Deduplicate to ~40 intentional lines and add `node_modules/`.
- **Dead scaffolding** (resolved 2026-07-03). `metrics/{ping,parsed,iperf}/` contained only `.gitkeep` — the structure was superseded by `results/runs/<id>/` and has been removed. No code referenced it.
- **Root-level config sprawl.** `conf-cu.conf`, `conf-du.conf`, `conf-nr-ue.conf`, `gnb-docker-compose.yaml` sit at the repo root while every other topology lives under `experiments/<name>/`. Moving the F1 files to `experiments/manual_f1_handover/` (with path updates in `lib.sh` and the dashboard registry — the drift validator will catch stragglers) would make the layout uniform. Medium effort; do it opportunistically.
- **No `pyproject.toml`/ruff for the Python code.** `requirements.txt` is properly pinned (good), but there is no formatter/linter config for the backend or `tools/`. Adding ruff (lint+format) to the CI workflow standardizes style for free.
- **AGENTS.md is a good, modern practice** — hard facts (container names, telnet endpoint, "do not invent a generic `handover` command") that keep multiple AI-assisted sessions from re-deriving or violating invariants. Keep extending it as invariants accumulate (the `handover_trigger_start` event-name contract belongs there too).

---

## 9. Security posture

- **Strengths:** no arbitrary command execution; no shell interpolation (asserted in tests); action gating + confirmation; read-only mounts; bounded outputs; the SIM credentials in docs are OAI's public test vectors, not secrets; `.env` files are gitignored with `.env.example` committed (correct pattern for the USRP LAN configs).
- **Weaknesses:** no authentication + wildcard CORS (Section 5); the Docker socket mounted into the backend container is root-equivalent on the host — inherent to the design and acceptable for a lab, but it means the "do not expose on untrusted networks" warning is load-bearing and should be enforced by the token recommended above; dashboard frontend nginx serves without any hardening headers (minor for lab use).

---

## 10. Prioritized recommendations

**P0 — do these first (each < 1 hour):**

1. Add a GitHub Actions CI workflow running the already-documented validation list + `bash -n`/`shellcheck` + frontend build.
2. Add a LICENSE file.
3. Fix `.gitignore`: deduplicate, and add `node_modules/`.
4. Stop auto-committing "." to `main` (scratch branch or disable); tag `baseline-2026-06-19`.

**P1 — near-term (a day or two total):**

5. Extend the Overview's quick trigger and interruption capture to N2 (Section 7.1): pass the detected topology through the existing action whitelist, make the Overview topology-aware, and design the direction/reset UX. The harness already supports all of it.
6. Pin OAI images by digest (or fixed tag), record digests in `summary.json`, and reconcile the README's "v2.4.0" claim with reality.
7. Port `validate_phase*.py` to pytest with subject-based names; add golden-file tests for `parse_ping.py` (including a regression fixture for the precheck-contamination bug and a synthetic missing-seq outage).
8. Add token auth + explicit CORS origins to the backend; keep the "no exposure" doc warning as defense-in-depth.
9. Bring the four unconverted docs into the naming convention and index them in `docs/README.md`; add resolution banners to closed handoffs.
10. Document the high-resolution interruption measurement (10 ms probes, resolution-floor interpretation, seamless-vs-outage semantics) in `guide-measurement-pipeline.md`, and surface the same interpretation on the dashboard card.
11. UI systematization pass (Section 6): design tokens + shared status/chart primitives, WCAG fixes (non-color status cues, contrast, focus rings, ARIA on tabs/collapsibles), and URL routing with deep-linkable runs/campaigns.

**P2 — opportunistic:**

12. ESLint + Vitest for the frontend; extract pure data-shaping helpers from the large page components and test those first.
13. Move `vite`/`@vitejs/plugin-react` to `devDependencies`.
14. Record a larger (n≥20) F1 baseline with confidence intervals, and a first repeated N2 baseline (both variants, with resets) so the three-topology claim is empirically symmetric; have the aggregator emit CIs.
15. Register `usrp-cots` in the dashboard with honest suppression of UE-container-based cards; pivot a real-radio Overview toward telnet MAC stats and radio-health signals (Section 7.2), and treat COTS-UE user-plane measurement as its own design effort.
16. Remove or document the empty `metrics/` tree; consider relocating root-level F1 confs under `experiments/`.
17. Add `ruff` config for backend + tools; add the event-name contract (`handover_trigger_start`) to AGENTS.md or enforce it via a shared constant.

## 11. Closing assessment

The scientific core of this repository — readiness modeling, measurement validity gating, honest resolution accounting, confidence-labeled telemetry, and a documentation system with real information architecture — is stronger than the vast majority of research testbeds and needs no rework. The action-safety model in the dashboard is production-grade thinking. What remains falls into three buckets: ordinary software-project infrastructure (CI, license, git hygiene, standard test/lint tooling, pinned images — none architectural, all cheap); a UI systematization pass (tokens, accessibility, routing — a refinement of a sound design, not a redesign); and coverage parity, where the N2 half is mostly wiring because the harness already did the hard work, and the USRP half is a real measurement-design problem that should be phased deliberately rather than ported naively.
