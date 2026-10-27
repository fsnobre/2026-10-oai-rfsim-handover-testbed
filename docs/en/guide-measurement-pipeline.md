# Measurement Pipeline and Run Lifecycle

> **Document type:** Guide
>
> **Required reading:** [F01 — Functional readiness model](foundation-f01-functional-readiness-model.md) and [F02 — User-plane and DN reachability](foundation-f02-dn-reachability.md)

This document describes how a single smoke-test run is orchestrated end to end:
how the data plane is measured across a handover, how raw captures become
metrics, and how the run is gated so that it either produces trustworthy
numbers or is explicitly marked invalid.

It is the connective tissue between two existing references:

- [Functional readiness model](foundation-f01-functional-readiness-model.md) — what "ready"
  means and which layer each check belongs to.
- [N2 handover guide](guide-n2-handover.md) — topology-specific configuration
  and the handover trigger itself.

This document does not repeat those; it covers the measurement and lifecycle
that sit on top of them.

---

## 1. Design principles

Two principles shape the entire pipeline:

1. **Never `sleep` and hope — poll for an observable condition.** Readiness is
   established by polling container state, control-plane ports, and actual
   data-plane reachability, not by fixed delays. The only fixed sleeps in a run
   are the deliberate measurement windows (a short settle before the trigger and
   the post-handover capture window).
2. **A measurement is either trustworthy or explicitly invalid — never silently
   wrong.** Every gate is recorded as a boolean in `summary.json`, and a run is
   only declared `pass` after the parser confirms usable samples were captured.

Both principles exist because an OAI process can be alive while the protocol
stack is unusable (see the readiness invariants in the functional readiness
model).

---

## 2. Run lifecycle

The driver is `scripts/run_smoke_test.sh`, invoked as
`./scripts/run_smoke_test.sh <topology>` where topology is `f1`,
`n2-monolithic`, or `n2-cu-du`. `apply_topology` selects the compose file,
experiment config, and critical-container list; everything downstream is
topology-agnostic.

The ordered sequence:

1. **`create_run_dir`** — a timestamped results directory
   `results/runs/<run_id>_<tag>/` is created, and a `trap finish_summary EXIT`
   is installed immediately so that *every* exit path writes a `summary.json`.
2. **Preflight** (`preflight_check.sh`) — host prerequisites.
3. **Startup** — `status.sh` is checked; if not already ready, `up.sh` starts
   the topology.
4. **`wait_ready.sh`** — polls `status.sh` until all critical checks pass
   (180 s default).
5. **`poststart_check.sh`** — non-blocking diagnostics and fatal-log scan.
6. **`wait_ue_data_ready.sh`** — the decisive gate: loops
   `docker exec oai-nr-ue ping -c1 -W1 <target>` until the UE can actually pass user
   traffic through `oaitun_ue1`. Container liveness is not sufficient; this
   confirms the PDU session forwards. Failure here aborts the run before any
   handover.
7. **Start ping capture** (`start_ping_capture.sh`).
8. **Optionally start iperf** in the background (`run_iperf_test.sh`).
9. **Settle** — `sleep 3` to collect baseline replies.
10. **Trigger handover** (`trigger_handover.sh`), bracketed by the
    `before_handover` and `after_handover` events.
11. **Recovery window** — keep pinging `PING_POST_HANDOVER_SECONDS` (10 s
    default) to capture recovery after the trigger.
12. **Stop capture**, `wait` on iperf, then **parse** both captures.
13. **Validate** parser output, **collect logs**, finalize `summary.json`.

Because the `EXIT` trap always runs `finish_summary`, a run that crashes
midway still leaves a structured record showing how far it progressed
(`ue_data_ready`, `ping_precheck_passed`, `handover_triggered`, and so on are
each tracked as booleans).

---

## 3. Ping capture

`scripts/start_ping_capture.sh` runs a timestamped ping (`ping -D`) from inside
the `oai-nr-ue` container in the background and writes to `ping_raw.log`.

### Precheck/capture file separation

A 2-packet precheck runs first to confirm reachability before committing to the
long capture. The precheck writes to a **separate** file
(`ping_precheck_raw.log`), never to `ping_raw.log`.

This separation is load-bearing. When the precheck and the long capture shared
`ping_raw.log`, a race on flushing the long capture's final statistics line
could cause the parser to read the precheck's `packets transmitted, 2` instead
of the real capture count — reporting `packets_transmitted: 2` for a run that
actually captured dozens of replies. Keeping `ping_raw.log` long-capture-only
makes the final statistics line unambiguous.

The header comment lines (target, interface, interval, source container) are the
only content written to `ping_raw.log` before the long capture begins.

Files produced in the run directory:

- `ping_raw.log` — long capture only (header + `ping -D` output).
- `ping_precheck_raw.log` — the 2-packet precheck output.
- `ping_command.txt` — the exact long-capture command.
- `ping.pid`, `ping_target.txt`, `ping_interface.txt`,
  `ping_precheck_status.txt`.

---

## 4. Ping parsing and the interruption estimate

`tools/parse_ping.py` turns `ping_raw.log` into `ping.csv` plus a
`ping_summary.json` of metrics.

### Reply and summary extraction

Three regexes match reply lines (`[ts] N bytes from … icmp_seq=… time=… ms`),
the trailing `packets transmitted, … received, …% packet loss` line, and the
`rtt min/avg/max/mdev` line. A `long_capture_started` flag ensures the summary
and rtt lines are only accepted *after* the first real reply — a second layer of
defense against precheck contamination, on top of the file separation above.

`packet_loss_percent` is derived from transmitted vs. received counts; rtt
statistics are taken from the trailing line if present, otherwise computed from
the parsed replies.

### Handover interruption estimate

This is the headline metric. The parser joins ping reply timestamps against
`events.csv`:

- It locates the handover time from the `handover_trigger_start` event
  (fallback: `before_handover`).
- Replies are split into those **before** and **at/after** the handover time.
- `estimated_interruption_ms = (first reply after) − (last reply before)`,
  in milliseconds.
- `first_ping_after_handover_ms = (first reply after) − (handover time)`.

> **Event-name dependency.** The interruption estimate depends on the
> `handover_trigger_start` event being present in `events.csv`. The unified
> `trigger_handover.sh` emits this same event name for all topologies (F1 and
> both N2 variants). If a future change renames it to a topology-specific event,
> the interruption estimate silently becomes `null`. Keep the event name stable.

### Resolution and interpretation

The estimate is bounded by the ping interval (0.2 s by default), so it is a
**functional reference, not a precise interruption measurement**. The validated
results set treats it accordingly: a single run per topology is a sanity check,
not a statistically meaningful baseline. A real comparative study needs repeated
cold-start trials, fixed host load, pinned image digests, and confidence
intervals.

### Validity gate

`ping_metrics_valid` is set to `parsed_reply_count > 0`. After parsing, the
driver re-checks both `ping_metrics_valid` and `packets_transmitted != 0`; if
either fails, the run is marked failed with a `ping_metrics_invalid` event even
though the handover command was sent. Invalid metrics never masquerade as a pass.

### High-resolution interruption capture (`measure_interruption.sh`)

The smoke test's default 0.2 s ping interval is too coarse to resolve a
tens-of-milliseconds user-plane outage: the estimate is floored by the interval,
so a seamless handover and a 150 ms outage can both report roughly one interval.
`scripts/measure_interruption.sh` exists to measure that outage directly.

It is a **bounded, high-rate capture around a single triggered handover** that
reuses the same `parse_ping.py` pipeline. Unlike the smoke test it does **not**
bring up the stack or run iperf — it assumes the topology is already active (the
same precondition as the dashboard quick trigger). The flow:

1. `wait_ue_data_ready.sh` — the same decisive data-plane gate.
2. `start_ping_capture.sh` at `INTERRUPTION_PING_INTERVAL` (default **0.01 s = 10 ms**).
3. `sleep INTERRUPTION_PRE_SECONDS` (default 2 s) of baseline.
4. `trigger_handover.sh <topology>` — emits the same `handover_trigger_start`
   event the parser anchors on.
5. `sleep INTERRUPTION_POST_SECONDS` (default 4 s) of recovery.
6. `stop_ping_capture` + `parse_ping.py`, then print the `INTERRUPTION_RUN_DIR=`
   sentinel so the dashboard can locate the run.

| Env override | Default | Meaning |
|---|---|---|
| `INTERRUPTION_PING_INTERVAL` | `0.01` | seconds between probes (10 ms) |
| `INTERRUPTION_PRE_SECONDS` | `2` | baseline capture before the trigger |
| `INTERRUPTION_POST_SECONDS` | `4` | capture after the trigger |
| `UE_DATA_READY_TIMEOUT` | `60` | data-plane readiness timeout |
| `PING_TARGET` / `PING_INTERFACE` | from config | override the experiment values |

Sub-200 ms intervals require the ping to run as root, which the `oai-nr-ue`
container already does. It accepts `f1`, `n2-monolithic`, or `n2-cu-du`.

#### Interpreting the result — seamless vs. real outage

The estimate is still floored by the probe interval, so a 10 ms cadence resolves
outages down to about 10 ms, no finer. Read the result together with packet loss:

- **Estimate ≈ one probe interval, 0% loss, no missing `icmp_seq`** → the
  handover was **seamless**: no user-plane packet was actually lost, and the
  reported few-millisecond "interruption" is just the gap between two adjacent
  successful probes, not an outage. Do not quote it as an interruption time.
- **Missing `icmp_seq` values (packet loss > 0)** → this is the **honest outage
  signal**. The span of missing sequence numbers, not the reply-to-reply time
  delta, is what a real interruption looks like.

In other words: the RTT-gap estimate is a convenient number, but **packet loss /
missing sequence numbers are the ground truth for whether traffic was actually
interrupted**. The dashboard Overview interruption card reflects this — it plots
the per-`icmp_seq` reply stream (breaking the line across missing sequences) and
labels a result with 0% loss and an estimate within about two probe intervals as
a seamless handover rather than a measured outage.

---

## 5. Optional iperf measurement

When `IPERF_ENABLED=1` (or `IPERF_REQUIRED=1`), `run_iperf_test.sh` runs
concurrently with the ping capture across the handover. It binds to the UE PDU
address with `iperf3 -B <ue_ip>` (the OAI image's iperf3 does not support
`--bind-dev`), so traffic flows over `oaitun_ue1` rather than the container's
Docker `eth0`.

`tools/parse_iperf.py` reads the iperf3 JSON and branches on protocol:

- **UDP** → throughput (`mbps`), `jitter_ms`, `lost_packets`, `lost_percent`
  from `end.sum`.
- **TCP** → throughput from `sum_received` and `retransmits` from `sum_sent`.

By default iperf failures are **non-fatal**: a valid ping/handover result is not
invalidated by an iperf problem, and the failure is recorded in
`iperf_status` / `iperf_error`. Set `IPERF_REQUIRED=1` to make a failed or
missing iperf measurement fail the whole run.

---

## 6. The run summary

`summary.json` is the single structured record per run. It is assembled with
small inline `python3` helpers (`json_metric`, `json_shell_string_or_null`) that
null-coalesce any missing sub-metric, so the schema is stable regardless of which
measurements actually ran. It captures:

- **Identity and gating**: `run_id`, `topology`, start/end time, `status`,
  `containers_checked`, and the boolean gates (`ue_data_ready`,
  `ping_capture_started`, `ping_precheck_passed`, `ping_parsed`,
  `ping_metrics_valid`, `handover_triggered`).
- **Ping metrics**: transmitted/received counts, loss, rtt min/avg/max,
  `estimated_interruption_ms`, `first_ping_after_handover_ms`.
- **iperf metrics**: status, protocol, throughput, jitter, loss, retransmits.
- **`notes`**: a human-readable account of how the run ended.

Alongside it the run directory holds `ping_summary.json`, `iperf_summary.json`,
`ping.csv`, `events.csv` (the timeline that drives the interruption estimate),
and collected logs and Docker state.

`run_repeated_smoke_tests.sh` invokes this lifecycle N times and aggregates the
per-run summaries under `results/repeated/`.

---

## 7. Where to look when a metric is missing or wrong

| Symptom | Likely cause | Where to check |
|---|---|---|
| `estimated_interruption_ms: null` | No `handover_trigger_start` event, or no replies after the trigger | `events.csv`; confirm the trigger succeeded |
| `packets_transmitted` implausibly small | Precheck contaminating `ping_raw.log` (should not happen post-fix) | `ping_raw.log` vs. `ping_precheck_raw.log` |
| `ping_metrics_valid: false` | Zero parsed replies | UE data-plane readiness; `ping_raw.log` |
| Run failed before trigger | UE data plane never became reachable | `ue_data_ready_*` events; functional readiness model |
| `iperf_status: failed` (run still passed) | Non-required iperf problem | `iperf_runner.log`, `iperf_error.txt` |
| `iperf_status: failed` (run failed) | `IPERF_REQUIRED=1` and iperf failed | same as above |
