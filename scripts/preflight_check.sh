#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TOPOLOGY="${1:-f1}"
apply_topology "${TOPOLOGY}"

if [[ "${SKIP_PREFLIGHT:-0}" == "1" ]]; then
  echo "[preflight] Skipped (SKIP_PREFLIGHT=1)."
  exit 0
fi

FIX="${PREFLIGHT_FIX:-0}"
_fix_tried=0

_try_fix() {
  local description="$1"
  shift
  if [[ "${FIX}" == "1" ]]; then
    echo "[preflight] Applying fix: ${description}"
    "$@" && _fix_tried=1 || echo "[preflight] Fix failed: ${description}" >&2
  fi
}

failures=0
warnings=0
docker_available=0
compose_available=0

_pass() { printf '[PASS] %s\n' "$1"; }
_warn() { printf '[WARN] %s\n' "$1"; warnings=$(( warnings + 1 )); }
_fail() { printf '[FAIL] %s\n' "$1" >&2; failures=$(( failures + 1 )); }
_info() { printf '[INFO] %s\n' "$1"; }

echo "=== OAI RFsim testbed — pre-flight checks ==="
echo

# 1. Docker daemon
if docker info >/dev/null 2>&1; then
  _pass "Docker daemon is running"
  docker_available=1
else
  _fail "Docker daemon is not running — sudo systemctl start docker"
fi

# 2. Docker Compose v2
if docker compose version >/dev/null 2>&1; then
  _pass "Docker Compose v2 available"
  compose_available=1
else
  _fail "docker compose (v2) not available — install the Docker Compose plugin"
fi

# 3. Required host tools
for tool in nc python3 ip ss; do
  if command_exists "${tool}"; then
    _pass "Tool present: ${tool}"
  else
    _fail "Required tool missing: ${tool}"
  fi
done

# 4. Compose configuration, CN subscriber seed, and CN-managed Docker networks
if command_exists python3 && python3 "${SCRIPT_DIR}/validate_cn_subscriber.py" >/dev/null; then
  _pass "RFsim subscriber seed contains expected IMSI/SUPI, key/OPC, DNN, and slice"
elif command_exists python3; then
  _fail "RFsim subscriber seed validation failed — run: python3 scripts/validate_cn_subscriber.py"
else
  _fail "python3 is required to validate the RFsim subscriber seed"
fi

if [[ "${compose_available}" -eq 1 ]]; then
  if (
    cd "${CORE_COMPOSE_DIR}"
    docker compose config --quiet
  ); then
    _pass "OAI CN Compose configuration is valid"
  else
    _fail "OAI CN Compose configuration is invalid"
  fi

  if docker compose "${RAN_COMPOSE_ARGS[@]}" config --quiet; then
    _pass "RAN Compose configuration is valid (${TOPOLOGY})"
  else
    _fail "RAN Compose configuration is invalid (${TOPOLOGY})"
  fi
fi

if [[ "${docker_available}" -eq 1 ]]; then
  while read -r network subnet compose_network; do
    if ! docker_network_exists "${network}"; then
      _info "Docker network ${network} is absent — OAI CN Compose will create it"
      continue
    fi

    network_error=""
    if network_error="$(
      validate_core_docker_network "${network}" "${subnet}" "${compose_network}"
    )"; then
      _pass "Docker network ${network} is compatible and managed by OAI CN Compose"
    else
      _fail "Docker network ${network} is incompatible: ${network_error}.
       Stop containers attached to it, then remove it:
         docker network rm ${network}
       OAI CN Compose will recreate it with the required configuration."
    fi
  done < <(core_docker_network_specs)
fi

# 5. /dev/net/tun (required by nr-ue for oaitun_ue1)
if [[ "${RADIO_MODE}" == "usrp" ]]; then
  _info "/dev/net/tun check skipped (USRP mode has no in-container UE)"
elif [[ -c /dev/net/tun ]]; then
  _pass "/dev/net/tun present"
else
  _try_fix "sudo modprobe tun" sudo modprobe tun
  if [[ -c /dev/net/tun ]]; then
    _pass "/dev/net/tun loaded via modprobe tun"
  else
    _fail "/dev/net/tun missing — sudo modprobe tun"
  fi
fi

# 6. SCTP kernel support (F1AP and NGAP both use SCTP)
if [[ -f /proc/net/sctp/assocs ]] || lsmod 2>/dev/null | grep -q '^sctp '; then
  _pass "SCTP kernel support available"
else
  _try_fix "sudo modprobe sctp" sudo modprobe sctp
  if [[ -f /proc/net/sctp/assocs ]] || lsmod 2>/dev/null | grep -q '^sctp '; then
    _pass "SCTP loaded via modprobe sctp"
  else
    _warn "SCTP not detected in /proc/net/sctp — run: sudo modprobe sctp
       (Skip this warning if sctp is built into the kernel rather than a loadable module)"
  fi
fi

# 7. Tailscale / VPN route sanity
if tailscale_is_active; then
  route_to_cu="$(ip -4 route get "${CU_TELNET_HOST}" 2>/dev/null || true)"

  if printf '%s\n' "${route_to_cu}" | grep -q ' dev tailscale0 '; then
    _fail "Tailscale is routing CU Telnet target ${CU_TELNET_HOST} via tailscale0.
       If you are using an exit node, run:
         tailscale set --exit-node-allow-lan-access=true
       Or disable the exit node / Tailscale for this experiment."
  else
    _warn "Tailscale is active, but route to CU Telnet target does not appear to use tailscale0:
       ${route_to_cu:-route unavailable}
       If Telnet/nc fails while using an exit node, run:
         tailscale set --exit-node-allow-lan-access=true"
  fi
elif tailscale_iface_exists; then
  _warn "stale tailscale0 interface exists but Tailscale is stopped — no action needed"
else
  _pass "Tailscale not active"
fi

# 8. WireGuard
if ip link show 2>/dev/null | grep -qE '^[0-9]+: wg[0-9]+:'; then
  _warn "WireGuard interface detected — may interfere with 192.168.70.x routing"
fi

# 9. OpenVPN / other TUN-based VPNs (tun0, tun1, ... but not oaitun_ue1)
if ip link show 2>/dev/null | grep -qE '^[0-9]+: tun[0-9]+:'; then
  _warn "TUN interface (tun0/tun1/...) detected — possibly OpenVPN; may interfere with routing"
fi

# 10. Subnet conflicts: non-Docker host interfaces using 192.168.70.x or 192.168.71.x
for octet in 70 71; do
  conflict="$(ip -4 addr show 2>/dev/null \
    | grep "192\.168\.${octet}\." \
    | awk '{print $NF, $2}' \
    | grep -vE '(br-|veth|docker)' \
    || true)"
  if [[ -n "${conflict}" ]]; then
    _warn "Non-Docker interface with 192.168.${octet}.x address: $(echo "${conflict}" | tr '\n' ' ')"
  else
    _pass "No conflicting host interfaces on 192.168.${octet}.x"
  fi
done

# 11. Port conflicts: 9090 (gNB Telnet), 4043 (rfsim)
if [[ "${RADIO_MODE}" == "usrp" ]]; then
  _info "rfsim/Telnet port check skipped (USRP mode uses neither port 9090 nor 4043)"
else
  for port in 9090 4043; do
    if ss -tlnp 2>/dev/null | awk 'NR>1 {print $4}' | grep -qE ":${port}$"; then
      holder="$(ss -tlnp 2>/dev/null | awk -v p=":${port}" 'NR>1 && $4 ~ p"$" {print $NF; exit}' || true)"
      _warn "Port ${port} already in use (${holder:-unknown}) — kill if it is not a running testbed container"
    else
      _pass "Port ${port} is free"
    fi
  done
fi

# 12. Stale OAI containers
stale=()
for name in oai-amf oai-smf oai-upf oai-cu oai-du0 oai-du1 oai-gnb0 oai-gnb1 oai-cu0 oai-cu1 oai-nr-ue; do
  if docker inspect "${name}" >/dev/null 2>&1; then
    stale+=("${name}")
  fi
done
if [[ ${#stale[@]} -gt 0 ]]; then
  _warn "Stale OAI containers found: ${stale[*]}
       Remove with: docker rm -f ${stale[*]}"
else
  _pass "No stale OAI containers"
fi

# 13. iptables FORWARD policy (skip gracefully if not readable without sudo)
if iptables -L FORWARD -n 2>/dev/null | head -1 | grep -q 'DROP'; then
  _warn "iptables FORWARD policy is DROP — may block inter-container traffic
       (Docker usually adds its own ACCEPT rules, but this can interfere)"
elif ! iptables -L FORWARD -n >/dev/null 2>&1; then
  _info "iptables FORWARD policy not readable without sudo — skipping"
else
  _pass "iptables FORWARD chain is not set to DROP"
fi

# 14. OAI images pulled locally
for image in "oaisoftwarealliance/oai-gnb:develop" "oaisoftwarealliance/oai-nr-ue:develop"; do
  if docker image inspect "${image}" >/dev/null 2>&1; then
    _pass "Image present: ${image}"
  else
    _warn "Image not pulled: ${image} — will be fetched on first start (needs internet)"
  fi
done

# 15. Disk space in results/ (warn if < 1 GiB free)
avail_kib="$(df -k "${PROJECT_ROOT}/results" 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)"
if [[ "${avail_kib}" -lt 1048576 ]]; then
  _warn "Less than 1 GiB free in results/ ($(( avail_kib / 1024 )) MiB) — old runs may need cleanup"
else
  _pass "Disk space OK: $(( avail_kib / 1024 )) MiB free in results/"
fi

# 16. System clock synchronisation (warn only)
if command_exists timedatectl; then
  if timedatectl status 2>/dev/null | grep -q 'synchronized: yes'; then
    _pass "System clock is synchronised"
  else
    _warn "System clock may not be synchronised — NAS authentication can fail in some OAI versions"
  fi
fi

# 17. USRP X310 real-radio checks (USRP mode only)
if [[ "${RADIO_MODE}" == "usrp" ]]; then
  sdr_addr="$(config_value_after_key "sdr_addr" "192.168.40.2")"

  if ping -c 1 -W 2 "${sdr_addr}" >/dev/null 2>&1; then
    _pass "USRP X310 reachable at ${sdr_addr}"
  else
    _fail "USRP X310 not reachable at ${sdr_addr}.
       Check the 10GbE cabling and the host NIC address on the ${sdr_addr%.*}.0/24 link.
       Override sdr_addr in experiments/usrp_x310/config.yaml and conf-gnb-usrp.conf if needed."
  fi

  if command_exists uhd_find_devices; then
    if uhd_find_devices --args "addr=${sdr_addr}" >/dev/null 2>&1; then
      _pass "uhd_find_devices found a device at ${sdr_addr}"
    else
      _warn "uhd_find_devices found no device at ${sdr_addr} — UHD also runs inside the gNB image; try ./scripts/check_usrp.sh"
    fi
  else
    _info "uhd_find_devices not on host — UHD ships inside the gNB image; use ./scripts/check_usrp.sh"
  fi

  rmem_max="$(cat /proc/sys/net/core/rmem_max 2>/dev/null || echo 0)"
  if [[ "${rmem_max}" -ge 24000000 ]]; then
    _pass "net.core.rmem_max is ${rmem_max} (adequate for 10GbE)"
  else
    _warn "net.core.rmem_max is ${rmem_max} — X310 10GbE may underrun. Apply on the host:
       sudo sysctl -w net.core.rmem_max=33554432 net.core.wmem_max=33554432"
  fi
fi

echo
echo "=== Pre-flight: ${failures} failure(s), ${warnings} warning(s) ==="

if [[ "${failures}" -gt 0 ]]; then
  if [[ "${FIX}" != "1" ]]; then
    echo "[preflight] Tip: re-run with PREFLIGHT_FIX=1 to automatically load missing kernel modules." >&2
  fi
  echo "[preflight] FAILED — fix the issues above before starting the testbed." >&2
  echo "[preflight] To skip (not recommended): set SKIP_PREFLIGHT=1 before the command." >&2
  exit 1
fi

if [[ "${warnings}" -gt 0 ]]; then
  echo "[preflight] PASSED with warnings."
else
  echo "[preflight] All checks passed."
fi
exit 0
