#!/usr/bin/env bash

# Make the dockerized 5GC reachable from distributed RAN hosts WITHOUT changing
# the CN. The 5GC stays on its bridge (oai-cn5g-public-net, 192.168.70.128/26);
# this script — run once on the CORE host — enables IPv4 forwarding and allows
# the CN bridge subnet through the FORWARD chain. Each RAN host then routes that
# subnet via the core host (printed below). The gNBs reach the AMF/UPF at their
# bridge addresses (AMF_N2_IP=192.168.70.132 by default).
#
# This is preferred over host-networking the AMF/UPF, which would break the CN
# SBI mesh (all NFs share SBI port 8080 and resolve each other on the bridge).
#
# Run on the core host:  sudo ./scripts/usrp_core_routing.sh [CORE_HOST_LAN_IP]

set -euo pipefail

CN_SUBNET="${CN_SUBNET:-192.168.70.128/26}"
CORE_HOST_IP="${1:-${CORE_HOST_IP:-<core-host-lan-ip>}}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script changes sysctl and iptables — re-run with sudo." >&2
  exit 1
fi

echo "[core-routing] Enabling IPv4 forwarding"
sysctl -w net.ipv4.ip_forward=1 >/dev/null

ensure_forward_rule() {
  local direction="$1" subnet="$2"
  if ! iptables -C FORWARD "${direction}" "${subnet}" -j ACCEPT 2>/dev/null; then
    iptables -I FORWARD "${direction}" "${subnet}" -j ACCEPT
    echo "[core-routing] Added FORWARD ACCEPT (${direction} ${subnet})"
  else
    echo "[core-routing] FORWARD ACCEPT already present (${direction} ${subnet})"
  fi
}

ensure_forward_rule -d "${CN_SUBNET}"
ensure_forward_rule -s "${CN_SUBNET}"

cat <<EOF

[core-routing] Core host is ready to forward to the 5GC bridge (${CN_SUBNET}).

On EACH RAN host (CU/DU/gNB), add a route so it can reach the 5GC:
    sudo ip route add ${CN_SUBNET} via ${CORE_HOST_IP}

Verify from a RAN host:
    ping -c1 192.168.70.132     # AMF
    ping -c1 192.168.70.134     # UPF (N3)

Then the gNB/CU amf_ip_address (AMF_N2_IP=192.168.70.132) and the SMF-provided
UPF N3 address (192.168.70.134) are reachable over the LAN.
EOF
