#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

status=0

check_container() {
  local container="$1"

  if ! container_running "${container}"; then
    echo "${container}: not_running"
    status=1
    return 0
  fi

  if docker exec "${container}" sh -lc 'command -v iperf3' >/dev/null 2>&1; then
    echo "${container}: iperf3_available"
  else
    echo "${container}: tool_missing"
    status=1
  fi
}

check_container oai-nr-ue
check_container oai-ext-dn

exit "${status}"
