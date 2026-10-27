#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

REMOVE_VOLUMES=0
TOPOLOGY=""

usage() {
  cat <<'EOF'
Usage: ./scripts/down.sh [topology] [--volumes]

Stops the RAN and core Docker Compose stacks.

topology  One of: f1 (default), n2-monolithic, n2-cu-du, usrp-cots
          If omitted, auto-detects from running containers.

Options:
  --volumes  Also remove Compose-managed volumes. This is destructive for
             persisted state and is intentionally opt-in.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    f1|n2-monolithic|n2-cu-du|usrp-cots)
      TOPOLOGY="$1"
      shift
      ;;
    --volumes)
      REMOVE_VOLUMES=1
      shift
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

if [[ -z "${TOPOLOGY}" ]]; then
  TOPOLOGY="$(detect_topology)"
  echo "[down] Auto-detected topology: ${TOPOLOGY}"
fi

apply_topology "${TOPOLOGY}"
ensure_project_root

down_args=(down)
if [[ "${REMOVE_VOLUMES}" -eq 1 ]]; then
  down_args+=(--volumes)
fi

echo "[down] Stopping RAN compose stack (${TOPOLOGY})"
docker compose "${RAN_COMPOSE_ARGS[@]}" "${down_args[@]}" || true

echo "[down] Stopping 5GC core compose stack"
(
  cd "${CORE_COMPOSE_DIR}"
  docker compose "${down_args[@]}"
)

echo "[down] Done."
