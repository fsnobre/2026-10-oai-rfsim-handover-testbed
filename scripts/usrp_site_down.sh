#!/usr/bin/env bash

# Stop one role of a distributed USRP handover site. Run on the host that owns
# the role.
#
#   ./scripts/usrp_site_down.sh <topology> <role>
#     topology: f1 | n2-monolithic | n2-cu-du
#     role:     the service to stop on this host (e.g. du0, gnb1, cu0)
#
# Env:
#   ENV_FILE  override the .env path (default: <topology-dir>/.env)

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
ensure_project_root

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <f1|n2-monolithic|n2-cu-du> <role>" >&2
  exit 2
fi

TOPOLOGY="$1"
ROLE="$2"

case "${TOPOLOGY}" in
  f1)                          topo_dir="f1" ;;
  n2-monolithic|n2_monolithic) topo_dir="n2_monolithic" ;;
  n2-cu-du|n2_cu_du)           topo_dir="n2_cu_du" ;;
  *) echo "Unknown topology: ${TOPOLOGY} (use f1, n2-monolithic, n2-cu-du)" >&2; exit 2 ;;
esac

TOPO_PATH="${PROJECT_ROOT}/experiments/usrp_handover/${topo_dir}"
COMPOSE_FILE="${TOPO_PATH}/compose-${ROLE}.yaml"
ENV_FILE="${ENV_FILE:-${TOPO_PATH}/.env}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "No compose file for role '${ROLE}' in ${topo_dir} (expected ${COMPOSE_FILE})." >&2
  exit 2
fi

# --env-file is only needed for interpolation; fall back to the example so
# `down` works even if .env was removed.
if [[ ! -f "${ENV_FILE}" ]]; then
  ENV_FILE="${TOPO_PATH}/.env.example"
fi

echo "[site-down] Stopping ${ROLE} (${TOPOLOGY})"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down || true
echo "[site-down] Done."
