#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

topology_arg=""
for arg in "$@"; do
  case "${arg}" in
    f1|n2-monolithic|n2-cu-du|usrp-cots) topology_arg="${arg}" ;;
  esac
done

"${SCRIPT_DIR}/down.sh" "$@"
"${SCRIPT_DIR}/up.sh" ${topology_arg:+"${topology_arg}"}
