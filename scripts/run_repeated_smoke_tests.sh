#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

TOPOLOGY="${1:-f1}"
apply_topology "${TOPOLOGY}"

RUNS="${RUNS:-5}"
RESET_BETWEEN_RUNS_VALUE="${RESET_BETWEEN_RUNS:-}"
RESET_BETWEEN_RUNS_ENABLED=false

if [[ -z "${RESET_BETWEEN_RUNS_VALUE}" && "${HANDOVER_TYPE}" == "n2" ]]; then
  RESET_BETWEEN_RUNS_VALUE=1
fi
case "${RESET_BETWEEN_RUNS_VALUE,,}" in
  1|true|yes|on) RESET_BETWEEN_RUNS_ENABLED=true ;;
esac

if ! [[ "${RUNS}" =~ ^[0-9]+$ ]] || [[ "${RUNS}" -lt 1 ]]; then
  echo "RUNS must be a positive integer" >&2
  exit 2
fi

if ! command_exists python3; then
  echo "python3 is required for repeated smoke-test aggregation." >&2
  exit 1
fi

case "${TOPOLOGY}" in
  f1)            run_tag="f1_handover_smoke" ; repeat_tag="f1_repeated" ;;
  n2-monolithic) run_tag="n2_monolithic_smoke" ; repeat_tag="n2_monolithic_repeated" ;;
  n2-cu-du)      run_tag="n2_cu_du_smoke" ; repeat_tag="n2_cu_du_repeated" ;;
esac

repeat_id="$(run_id_now)_${repeat_tag}"
repeat_dir="${PROJECT_ROOT}/results/repeated/${repeat_id}"
mkdir -p "${repeat_dir}"

runs_file="${repeat_dir}/runs.txt"
: >"${runs_file}"

echo "[repeat] output=${repeat_dir}"
echo "[repeat] runs=${RUNS}"
echo "[repeat] topology=${TOPOLOGY}"
echo "[repeat] reset_between_runs=${RESET_BETWEEN_RUNS_ENABLED}"

for run_index in $(seq 1 "${RUNS}"); do
  if [[ "${RESET_BETWEEN_RUNS_ENABLED}" == "true" ]]; then
    echo "[repeat] resetting ${TOPOLOGY} before run ${run_index}/${RUNS}"
    "${SCRIPT_DIR}/down.sh" "${TOPOLOGY}" >/dev/null 2>&1 || true
  fi

  echo "[repeat] starting run ${run_index}/${RUNS}"
  log_file="${repeat_dir}/run_${run_index}.log"

  set +e
  "${SCRIPT_DIR}/run_smoke_test.sh" "${TOPOLOGY}" 2>&1 | tee "${log_file}"
  smoke_status="${PIPESTATUS[0]}"
  set -e

  run_dir="$(awk -v tag="${run_tag}" '/\/results\/runs\// && $0 ~ tag {candidate=$0} END {print candidate}' "${log_file}" || true)"
  if [[ -z "${run_dir}" || ! -d "${run_dir}" ]]; then
    run_dir="$(ls -td "${PROJECT_ROOT}/results/runs/"*"_${run_tag}" 2>/dev/null | head -n 1 || true)"
  fi

  if [[ -n "${run_dir}" ]]; then
    printf '%s\n' "${run_dir}" >>"${runs_file}"
    echo "[repeat] run ${run_index}/${RUNS}: status=${smoke_status} dir=${run_dir}"
  else
    echo "[repeat] run ${run_index}/${RUNS}: status=${smoke_status} dir=unknown" >&2
  fi
done

python3 - "${repeat_dir}" "${RUNS}" <<'PY'
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path


repeat_dir = Path(sys.argv[1])
requested_runs = int(sys.argv[2])
runs_file = repeat_dir / "runs.txt"
summary_csv = repeat_dir / "summary.csv"
summary_json = repeat_dir / "summary.json"

csv_fields = [
    "run_id",
    "status",
    "packets_transmitted",
    "packets_received",
    "packet_loss_percent",
    "rtt_min_ms",
    "rtt_avg_ms",
    "rtt_max_ms",
    "estimated_interruption_ms",
    "first_ping_after_handover_ms",
    "iperf_status",
    "iperf_protocol",
    "iperf_mbps",
    "iperf_sender_mbps",
    "iperf_jitter_ms",
    "iperf_lost_packets",
    "iperf_packets",
    "iperf_lost_percent",
    "iperf_retransmits",
]

aggregate_fields = [
    "packet_loss_percent",
    "rtt_avg_ms",
    "rtt_max_ms",
    "estimated_interruption_ms",
    "first_ping_after_handover_ms",
    "iperf_mbps",
    "iperf_sender_mbps",
    "iperf_jitter_ms",
    "iperf_lost_percent",
    "iperf_retransmits",
]


def load_summary(run_dir: Path) -> dict[str, object]:
    path = run_dir / "summary.json"
    if not path.exists():
        return {"run_id": run_dir.name, "status": "missing_summary"}
    with path.open() as handle:
        data = json.load(handle)
    data.setdefault("run_id", run_dir.name)
    data.setdefault("status", "unknown")
    return data


def numeric(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


run_dirs = [Path(line.strip()) for line in runs_file.read_text().splitlines() if line.strip()]
rows = [load_summary(run_dir) for run_dir in run_dirs]

with summary_csv.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=csv_fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in csv_fields})

aggregates: dict[str, dict[str, float | int | None]] = {}
for field in aggregate_fields:
    values = [value for row in rows if (value := numeric(row.get(field))) is not None]
    if values:
        aggregates[field] = {
            "count": len(values),
            "mean": statistics.fmean(values),
            "min": min(values),
            "max": max(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }
    else:
        aggregates[field] = {
            "count": 0,
            "mean": None,
            "min": None,
            "max": None,
            "std": None,
        }

status_counts: dict[str, int] = {}
iperf_status_counts: dict[str, int] = {}
for row in rows:
    status = str(row.get("status", "unknown"))
    status_counts[status] = status_counts.get(status, 0) + 1
    iperf_status = str(row.get("iperf_status", "unknown"))
    iperf_status_counts[iperf_status] = iperf_status_counts.get(iperf_status, 0) + 1

summary = {
    "repeat_id": repeat_dir.name,
    "requested_runs": requested_runs,
    "recorded_run_dirs": len(run_dirs),
    "completed_summaries": len(rows),
    "status_counts": status_counts,
    "iperf_status_counts": iperf_status_counts,
    "runs": [str(path) for path in run_dirs],
    "aggregates": aggregates,
}

summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
PY

echo "[repeat] wrote ${repeat_dir}/summary.csv"
echo "[repeat] wrote ${repeat_dir}/summary.json"
echo "${repeat_dir}"
