#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TIMEOUT=180
TOPOLOGY=""

usage() {
  cat <<'EOF'
Usage: ./scripts/wait_ready.sh [topology] [--timeout seconds]

Polls ./scripts/status.sh until all critical checks pass or the timeout expires.

topology  One of: f1 (default), n2-monolithic, n2-cu-du, usrp-cots
          If omitted, auto-detects from running containers.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    f1|n2-monolithic|n2-cu-du|usrp-cots)
      TOPOLOGY="$1"
      shift
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        echo "--timeout requires a value" >&2
        exit 2
      fi
      TIMEOUT="$2"
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

if ! [[ "${TIMEOUT}" =~ ^[0-9]+$ ]]; then
  echo "Timeout must be an integer number of seconds" >&2
  exit 2
fi

deadline=$((SECONDS + TIMEOUT))

while [[ "${SECONDS}" -le "${deadline}" ]]; do
  if "${SCRIPT_DIR}/status.sh" ${TOPOLOGY:+"${TOPOLOGY}"} >/dev/null 2>&1; then
    echo "[wait_ready] Testbed is ready."
    exit 0
  fi
  remaining=$((deadline - SECONDS))
  if [[ "${remaining}" -le 0 ]]; then
    break
  fi
  echo "[wait_ready] Not ready yet; retrying in 5 seconds (${remaining}s remaining)."
  sleep 5
done

echo "[wait_ready] Timed out after ${TIMEOUT} seconds." >&2
exit 1
