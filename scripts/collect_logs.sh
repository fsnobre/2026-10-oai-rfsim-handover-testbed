#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

RUN_DIR_ARG=""

usage() {
  cat <<'EOF'
Usage: ./scripts/collect_logs.sh [--run-dir path]

Collects Docker logs and host metadata. Without --run-dir, creates:
  results/runs/YYYYmmdd_HHMMSS_manual_f1_handover/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir)
      if [[ $# -lt 2 ]]; then
        echo "--run-dir requires a value" >&2
        exit 2
      fi
      RUN_DIR_ARG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

ensure_project_root

topology="$(detect_topology)"
apply_topology "${topology}"

if [[ -n "${RUN_DIR_ARG}" ]]; then
  run_dir="${RUN_DIR_ARG}"
  mkdir -p "${run_dir}"
else
  run_dir="$(create_run_dir manual_f1_handover)"
fi

logs_dir="${run_dir}/docker_logs"
mkdir -p "${logs_dir}"

for container in "${CRITICAL_CONTAINERS[@]}"; do
  if container_exists "${container}"; then
    docker logs "${container}" >"${logs_dir}/${container}.log" 2>&1 || true
  else
    printf 'container %s does not exist\n' "${container}" >"${logs_dir}/${container}.log"
  fi
done

docker ps -a >"${run_dir}/docker_ps.txt"

# Include a fresh post-start snapshot so every log bundle is self-contained
"${SCRIPT_DIR}/poststart_check.sh" >"${run_dir}/poststart_check.txt" 2>&1 || true

{
  echo "date:"
  date
  echo
  echo "uname -a:"
  uname -a
  echo
  echo "docker version:"
  docker version || true
  echo
  echo "docker compose version:"
  docker compose version || true
  echo
  echo "ip addr:"
  ip addr || true
  echo
  echo "ip route:"
  ip route || true
} >"${run_dir}/host_info.txt" 2>&1

if [[ ! -f "${run_dir}/events.csv" ]]; then
  printf 'timestamp,event,details\n' >"${run_dir}/events.csv"
fi

if [[ ! -f "${run_dir}/summary.json" ]]; then
  cat >"${run_dir}/summary.json" <<EOF
{
  "run_id": "$(json_escape "$(basename "${run_dir}")")",
  "collected_at": "$(timestamp_utc)",
  "status": "logs_collected",
  "containers_checked": ["oai-amf", "oai-smf", "oai-upf", "oai-cu", "oai-du0", "oai-du1", "oai-nr-ue"],
  "notes": "Standalone log collection."
}
EOF
fi

echo "${run_dir}"
