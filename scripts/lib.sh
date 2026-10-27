#!/usr/bin/env bash

# lib.sh is a sourced library: the variables it defines (CORE_COMPOSE_DIR,
# RAN_COMPOSE_FILE, RAN_COMPOSE_ARGS, CRITICAL_CONTAINERS, HANDOVER_TYPE,
# RADIO_MODE, ...) are
# consumed by the scripts that source it, so ShellCheck cannot observe their use
# from within this file. This file-wide directive suppresses the resulting
# false-positive SC2034 warnings.
# shellcheck disable=SC2034

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CORE_COMPOSE_DIR="${PROJECT_ROOT}/oai-cn5g"
CORE_COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-oai-cn5g}"
RAN_COMPOSE_FILE="${PROJECT_ROOT}/gnb-docker-compose.yaml"
EXPERIMENT_CONFIG="${PROJECT_ROOT}/experiments/manual_f1_handover/config.yaml"

# Optional Compose overlays layered over the topology's RAN compose file.
# RAN_COMPOSE_OVERLAY is a colon-separated list of paths; each becomes an
# additional `-f` argument after the base file. This lets an external
# experiment override service settings (extra softmodem options, alternate
# mounted configs) without editing this repository's compose files. The base
# file stays first, so the Compose project directory and project name are
# unchanged.
RAN_COMPOSE_OVERLAY="${RAN_COMPOSE_OVERLAY:-}"
RAN_COMPOSE_ARGS=()

build_ran_compose_args() {
  RAN_COMPOSE_ARGS=(-f "${RAN_COMPOSE_FILE}")

  [[ -n "${RAN_COMPOSE_OVERLAY}" ]] || return 0

  local -a overlays=()
  IFS=':' read -r -a overlays <<< "${RAN_COMPOSE_OVERLAY}"

  local overlay
  for overlay in "${overlays[@]}"; do
    [[ -n "${overlay}" ]] || continue
    if [[ ! -f "${overlay}" ]]; then
      echo "RAN_COMPOSE_OVERLAY entry not found: ${overlay}" >&2
      exit 2
    fi
    # Absolute, because callers cd between the project root and compose dirs.
    RAN_COMPOSE_ARGS+=(-f "$(cd "$(dirname "${overlay}")" && pwd)/$(basename "${overlay}")")
  done
}

CU_TELNET_HOST="${CU_TELNET_HOST:-192.168.70.150}"
CU_TELNET_PORT="${CU_TELNET_PORT:-9090}"

build_ran_compose_args

CRITICAL_CONTAINERS=(oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue)
HANDOVER_TYPE="f1"
N2_TOPOLOGY_INTERNAL=""
RADIO_MODE="rfsim"

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

run_id_now() {
  date +"%Y%m%d_%H%M%S"
}

ensure_project_root() {
  cd "${PROJECT_ROOT}"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

core_docker_network_specs() {
  printf '%s\n' \
    'oai-cn5g-public-net 192.168.70.128/26 public_net' \
    'oai-ext-dn-traffic-net 192.168.71.128/26 traffic_net'
}

docker_network_exists() {
  local name="$1"
  docker network inspect "${name}" >/dev/null 2>&1
}

validate_core_docker_network() {
  local name="$1"
  local expected_subnet="$2"
  local compose_network="$3"
  local driver
  local subnets
  local compose_project_label
  local compose_network_label

  driver="$(docker network inspect -f '{{.Driver}}' "${name}" 2>/dev/null || true)"
  subnets="$(docker network inspect -f '{{range .IPAM.Config}}{{println .Subnet}}{{end}}' "${name}" 2>/dev/null || true)"
  compose_project_label="$(
    docker network inspect \
      -f '{{if .Labels}}{{index .Labels "com.docker.compose.project"}}{{end}}' \
      "${name}" 2>/dev/null || true
  )"
  compose_network_label="$(
    docker network inspect \
      -f '{{if .Labels}}{{index .Labels "com.docker.compose.network"}}{{end}}' \
      "${name}" 2>/dev/null || true
  )"

  if [[ "${driver}" != "bridge" ]]; then
    printf 'driver is %s (expected bridge)' "${driver:-unknown}"
    return 1
  fi
  if ! printf '%s\n' "${subnets}" | grep -Fxq "${expected_subnet}"; then
    printf 'subnet is %s (expected %s)' "${subnets//$'\n'/,}" "${expected_subnet}"
    return 1
  fi
  if [[ "${compose_project_label}" != "${CORE_COMPOSE_PROJECT}" ]] \
    || [[ "${compose_network_label}" != "${compose_network}" ]]; then
    printf 'not owned by Compose project %s as network %s' \
      "${CORE_COMPOSE_PROJECT}" "${compose_network}"
    return 1
  fi
}

ue_data_interface_ip() {
  docker exec oai-nr-ue ip -4 -o addr show oaitun_ue1 2>/dev/null \
    | awk '{print $4}' \
    | cut -d/ -f1 \
    | head -1
}

ue_data_plane_reachable() {
  local target="${1:-$(config_ping_target)}"
  local interface="${2:-$(config_ping_interface)}"
  local ping_args=(-c 1 -W 1)

  [[ -n "${interface}" ]] && ping_args+=(-I "${interface}")
  docker exec oai-nr-ue ping "${ping_args[@]}" "${target}" >/dev/null 2>&1
}

# Real-radio (USRP) readiness helpers. These gate on the NG (N2) association to
# the AMF instead of an in-container UE, because the USRP topology has no nr-ue
# container — the UE is an external COTS handset.
ngap_associated() {
  local gnb_name="${1:-oai-gnb}"

  container_running "${gnb_name}" || return 1
  docker logs "${gnb_name}" 2>&1 \
    | grep -qiE 'NGSetupResponse|Connected to AMF' || return 1
}

wait_ngap_associated() {
  local gnb_name="${1:-oai-gnb}"
  local timeout="$2"
  local deadline=$((SECONDS + timeout))

  while [[ "${SECONDS}" -le "${deadline}" ]]; do
    if ngap_associated "${gnb_name}"; then
      echo "[ready] ${gnb_name}: NG association to AMF established"
      return 0
    fi
    sleep 2
  done

  echo "[ready] ${gnb_name}: NG association not established after ${timeout}s" >&2
  return 1
}

# Best-effort count of UEs that have registered, parsed from AMF logs. Returns 0
# (not an error) when the AMF is not running or no UE has attached yet.
amf_registered_ue_count() {
  if ! container_running oai-amf; then
    printf '0\n'
    return 0
  fi
  local count
  count="$(docker logs oai-amf 2>&1 \
    | grep -ciE 'Registration accept|Registration Accept|5GMM-REGISTERED' || true)"
  printf '%s\n' "${count:-0}"
}

remaining_timeout() {
  local start_seconds="$1"
  local timeout="$2"
  local elapsed=$((SECONDS - start_seconds))
  local remaining=$((timeout - elapsed))

  if [[ "${remaining}" -le 0 ]]; then
    printf '0\n'
  else
    printf '%s\n' "${remaining}"
  fi
}

container_exists() {
  local name="$1"
  docker inspect "${name}" >/dev/null 2>&1
}

container_running() {
  local name="$1"
  local running
  running="$(docker inspect -f '{{.State.Running}}' "${name}" 2>/dev/null || true)"
  [[ "${running}" == "true" ]]
}

container_health_status() {
  local name="$1"
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${name}" 2>/dev/null || true
}

wait_container_running() {
  local name="$1"
  local timeout="$2"
  local deadline=$((SECONDS + timeout))

  while [[ "${SECONDS}" -le "${deadline}" ]]; do
    if container_running "${name}"; then
      echo "[ready] ${name}: running"
      return 0
    fi
    sleep 2
  done

  echo "[ready] ${name}: not running after ${timeout}s" >&2
  return 1
}

wait_container_stably_running() {
  local name="$1"
  local timeout="$2"
  local stable_seconds="${3:-5}"
  local deadline=$((SECONDS + timeout))

  while [[ "${SECONDS}" -le "${deadline}" ]]; do
    if container_running "${name}"; then
      break
    fi
    sleep 2
  done

  if ! container_running "${name}"; then
    echo "[ready] ${name}: not running after ${timeout}s" >&2
    return 1
  fi

  echo "[ready] ${name}: running — verifying stability for ${stable_seconds}s"
  local stable_end=$((SECONDS + stable_seconds))
  while [[ "${SECONDS}" -le "${stable_end}" ]]; do
    if ! container_running "${name}"; then
      echo "[ready] ${name}: exited unexpectedly — last 80 log lines:" >&2
      docker logs --tail 80 "${name}" 2>&1 >&2 || true
      return 1
    fi
    sleep 1
  done

  echo "[ready] ${name}: stable"
  return 0
}

wait_container_healthy_or_running() {
  local name="$1"
  local timeout="$2"
  local deadline=$((SECONDS + timeout))
  local health

  while [[ "${SECONDS}" -le "${deadline}" ]]; do
    if container_running "${name}"; then
      health="$(container_health_status "${name}")"
      case "${health}" in
        healthy)
          echo "[ready] ${name}: healthy"
          return 0
          ;;
        none)
          echo "[ready] ${name}: running (no healthcheck)"
          return 0
          ;;
      esac
    fi
    sleep 2
  done

  health="$(container_health_status "${name}")"
  echo "[ready] ${name}: not ready after ${timeout}s (health=${health:-unknown})" >&2
  return 1
}

port_reachable() {
  local host="$1"
  local port="$2"

  if command_exists nc; then
    nc -z -w 2 "${host}" "${port}" >/dev/null 2>&1
  else
    bash -c ":</dev/tcp/${host}/${port}" >/dev/null 2>&1
  fi
}

wait_port() {
  local host="$1"
  local port="$2"
  local timeout="$3"
  local deadline=$((SECONDS + timeout))

  while [[ "${SECONDS}" -le "${deadline}" ]]; do
    if port_reachable "${host}" "${port}"; then
      echo "[ready] ${host}:${port}: reachable"
      return 0
    fi
    sleep 2
  done

  echo "[ready] ${host}:${port}: not reachable after ${timeout}s" >&2
  return 1
}

tailscale_iface_exists() {
  ip link show tailscale0 >/dev/null 2>&1
}

tailscale_is_active() {
  # Returns 0 only if Tailscale is actively routing traffic.
  # Does NOT classify as active based on interface existence alone.

  if command_exists tailscale; then
    # Prefer JSON status: BackendState = "Running" is authoritative.
    local state
    state="$(tailscale status --json 2>/dev/null \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' 2>/dev/null \
      || true)"
    case "${state}" in
      Running)
        return 0 ;;
      Stopped|NeedsLogin|NoNetwork|NoState|Starting)
        return 1 ;;
    esac
    # JSON unavailable or unrecognised state: fall back to text.
    local text
    text="$(tailscale status 2>&1 || true)"
    if printf '%s\n' "${text}" | grep -qi 'tailscale is stopped'; then
      return 1
    fi
    # A peer IP list in the output means the daemon is actively connected.
    if printf '%s\n' "${text}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[[:space:]]'; then
      return 0
    fi
    # Binary present but state unclear — if the daemon is up, be conservative.
    if command_exists systemctl && systemctl is-active --quiet tailscaled 2>/dev/null; then
      return 0
    fi
    return 1
  fi

  # No tailscale binary — if the daemon is running, treat as active.
  if command_exists systemctl && systemctl is-active --quiet tailscaled 2>/dev/null; then
    return 0
  fi

  return 1
}

tailscale_may_be_active() {
  tailscale_is_active
}

warn_tailscale() {
  if tailscale_may_be_active; then
    cat <<'EOF'
WARNING: Tailscale appears to be active or tailscale0 exists.
The CU Telnet nc command can fail when Tailscale interferes with routing.
If handover triggering fails, you may need to run:
  sudo tailscale down
EOF
  fi
}

create_run_dir() {
  local suffix="${1:-manual_f1_handover}"
  local run_id
  run_id="$(run_id_now)"
  local run_dir="${PROJECT_ROOT}/results/runs/${run_id}_${suffix}"
  mkdir -p "${run_dir}"
  printf '%s\n' "${run_dir}"
}

append_event() {
  local run_dir="${1:-}"
  local event="${2:-}"
  local details="${3:-}"

  [[ -n "${run_dir}" ]] || return 0
  mkdir -p "${run_dir}"
  local events_file="${run_dir}/events.csv"
  if [[ ! -f "${events_file}" ]]; then
    printf 'timestamp,event,details\n' >"${events_file}"
  fi
  printf '%s,%s,%s\n' "$(timestamp_utc)" "${event}" "${details}" >>"${events_file}"
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/ }"
  printf '%s' "${value}"
}

config_value_after_key() {
  local key="$1"
  local default_value="${2:-}"

  if [[ ! -f "${EXPERIMENT_CONFIG}" ]]; then
    printf '%s\n' "${default_value}"
    return 0
  fi

  local value
  value="$(awk -F': *' -v key="${key}" '
    $1 ~ "^[[:space:]]*" key "$" {
      value = $2
      sub(/[[:space:]]+#.*/, "", value)
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "${EXPERIMENT_CONFIG}" || true)"
  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
  else
    printf '%s\n' "${default_value}"
  fi
}

config_ping_target() {
  config_value_after_key "target" "192.168.71.135"
}

config_ping_interface() {
  config_value_after_key "interface" ""
}

config_ping_interval() {
  config_value_after_key "interval_seconds" "0.2"
}

config_ping_post_handover_seconds() {
  config_value_after_key "post_handover_seconds" "10"
}

config_iperf_value() {
  local key="$1"
  local default_value="${2:-}"
  local value

  if [[ ! -f "${EXPERIMENT_CONFIG}" ]]; then
    printf '%s\n' "${default_value}"
    return 0
  fi

  value="$(awk -v key="${key}" '
    /^[[:space:]]*iperf:[[:space:]]*$/ {
      section_indent = match($0, /[^[:space:]]/) - 1
      in_iperf = 1
      next
    }
    in_iperf {
      first_content = match($0, /[^[:space:]]/)
      if (first_content == 0) next
      current_indent = first_content - 1
      if (current_indent <= section_indent) {
        in_iperf = 0
        next
      }

      line = $0
      sub(/^[[:space:]]*/, "", line)
      if (line ~ ("^" key ":[[:space:]]*")) {
        sub(/^[^:]+:[[:space:]]*/, "", line)
        print line
        exit
      }
    }
  ' "${EXPERIMENT_CONFIG}" 2>/dev/null || true)"

  if [[ -n "${value}" ]]; then
    printf '%s\n' "${value}"
  else
    printf '%s\n' "${default_value}"
  fi
}

config_iperf_enabled() {
  config_iperf_value "enabled" "false"
}

config_iperf_target() {
  config_iperf_value "target" ""
}

config_iperf_mode() {
  config_iperf_value "mode" ""
}

config_iperf_duration() {
  config_iperf_value "duration_seconds" ""
}

config_n2_source_gnb_ip() {
  if [[ "${N2_TOPOLOGY_INTERNAL:-}" == "cu_du" ]]; then
    printf '192.168.70.150\n'
  else
    config_value_after_key "source_gnb_ip" "192.168.70.160"
  fi
}

config_n2_source_gnb_port() {
  config_value_after_key "source_gnb_port" "9090"
}

config_n2_target_pci() {
  config_value_after_key "target_pci" "1"
}

config_n2_ue_rrc_id() {
  config_value_after_key "ue_rrc_id" "1"
}

apply_topology() {
  local topology="${1:-f1}"
  case "${topology}" in
    f1)
      RAN_COMPOSE_FILE="${PROJECT_ROOT}/gnb-docker-compose.yaml"
      EXPERIMENT_CONFIG="${PROJECT_ROOT}/experiments/manual_f1_handover/config.yaml"
      CRITICAL_CONTAINERS=(oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-nr-ue)
      HANDOVER_TYPE="f1"
      N2_TOPOLOGY_INTERNAL=""
      RADIO_MODE="rfsim"
      ;;
    n2-monolithic)
      RAN_COMPOSE_FILE="${PROJECT_ROOT}/experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml"
      EXPERIMENT_CONFIG="${PROJECT_ROOT}/experiments/n2_handover/config.yaml"
      CRITICAL_CONTAINERS=(oai-amf oai-smf oai-upf oai-gnb0 oai-gnb1 oai-nr-ue)
      HANDOVER_TYPE="n2"
      N2_TOPOLOGY_INTERNAL="monolithic"
      RADIO_MODE="rfsim"
      ;;
    n2-cu-du)
      RAN_COMPOSE_FILE="${PROJECT_ROOT}/experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml"
      EXPERIMENT_CONFIG="${PROJECT_ROOT}/experiments/n2_handover/config.yaml"
      CRITICAL_CONTAINERS=(oai-amf oai-smf oai-upf oai-cu0 oai-du0 oai-cu1 oai-du1 oai-nr-ue)
      HANDOVER_TYPE="n2"
      N2_TOPOLOGY_INTERNAL="cu_du"
      RADIO_MODE="rfsim"
      ;;
    usrp-cots)
      RAN_COMPOSE_FILE="${PROJECT_ROOT}/experiments/usrp_x310/gnb-docker-compose.yaml"
      EXPERIMENT_CONFIG="${PROJECT_ROOT}/experiments/usrp_x310/config.yaml"
      CRITICAL_CONTAINERS=(oai-amf oai-smf oai-upf oai-gnb)
      HANDOVER_TYPE="none"
      N2_TOPOLOGY_INTERNAL=""
      RADIO_MODE="usrp"
      ;;
    *)
      echo "Unknown topology: ${topology}. Valid options: f1, n2-monolithic, n2-cu-du, usrp-cots" >&2
      exit 2
      ;;
  esac

  build_ran_compose_args
}

detect_topology() {
  if container_exists oai-cu; then
    printf 'f1\n'
  elif container_exists oai-gnb0; then
    printf 'n2-monolithic\n'
  elif container_exists oai-cu0; then
    printf 'n2-cu-du\n'
  elif container_exists oai-gnb; then
    printf 'usrp-cots\n'
  else
    printf 'f1\n'
  fi
}

stop_ping_capture() {
  local run_dir="$1"
  local pid_file="${run_dir}/ping.pid"

  [[ -f "${pid_file}" ]] || return 0

  local pid
  pid="$(cat "${pid_file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill -INT "${pid}" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5; do
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -TERM "${pid}" >/dev/null 2>&1 || true
    fi
  fi

  append_event "${run_dir}" "ping_capture_stop" "pid=${pid}"
}
