#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

diag_id="$(run_id_now)_dn_reachability"
diag_dir="${PROJECT_ROOT}/results/diagnostics/${diag_id}"
mkdir -p "${diag_dir}/networks" "${diag_dir}/containers" "${diag_dir}/pings" "${diag_dir}/traces" "${diag_dir}/firewall"

run_capture() {
  local output_file="$1"
  shift
  {
    printf '$'
    printf ' %q' "$@"
    printf '\n\n'
    "$@"
  } >"${output_file}" 2>&1 || true
}

run_container_capture() {
  local container="$1"
  local output_file="$2"
  shift 2

  if container_exists "${container}"; then
    run_capture "${output_file}" docker exec "${container}" "$@"
  else
    printf 'container %s does not exist\n' "${container}" >"${output_file}"
  fi
}

run_container_shell_capture() {
  local container="$1"
  local output_file="$2"
  local command="$3"

  if container_exists "${container}"; then
    run_capture "${output_file}" docker exec "${container}" sh -lc "${command}"
  else
    printf 'container %s does not exist\n' "${container}" >"${output_file}"
  fi
}

ping_probe() {
  local label="$1"
  local container="$2"
  local output_file="$3"
  shift 3

  if ! container_running "${container}"; then
    printf '%s=not_running\n' "${label}" >>"${diag_dir}/probe_status.env"
    printf 'container %s is not running\n' "${container}" >"${output_file}"
    return 1
  fi

  if ! docker exec "${container}" sh -lc 'command -v ping' >/dev/null 2>&1; then
    printf '%s=tool_missing\n' "${label}" >>"${diag_dir}/probe_status.env"
    {
      printf 'ping is not installed in container %s\n' "${container}"
      printf 'probe was not classified as a reachability failure\n'
    } >"${output_file}"
    return 0
  fi

  if docker exec "${container}" "$@" >"${output_file}" 2>&1; then
    printf '%s=pass\n' "${label}" >>"${diag_dir}/probe_status.env"
    return 0
  fi

  printf '%s=fail\n' "${label}" >>"${diag_dir}/probe_status.env"
  return 1
}

container_networks() {
  local container="$1"
  docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "${container}" 2>/dev/null || true
}

: >"${diag_dir}/probe_status.env"

echo "[diag] output=${diag_dir}"

run_capture "${diag_dir}/docker_ps.txt" docker ps -a
run_capture "${diag_dir}/docker_network_ls.txt" docker network ls

networks=(oai-cn5g-public-net oai-ext-dn-traffic-net)
for container in oai-cu oai-du0 oai-du1 oai-nr-ue; do
  while IFS= read -r network; do
    [[ -n "${network}" ]] && networks+=("${network}")
  done < <(container_networks "${container}")
done

mapfile -t unique_networks < <(printf '%s\n' "${networks[@]}" | sort -u)
for network in "${unique_networks[@]}"; do
  safe_name="${network//[^A-Za-z0-9_.-]/_}"
  run_capture "${diag_dir}/networks/${safe_name}.json" docker network inspect "${network}"
done

for container in oai-nr-ue oai-upf oai-ext-dn oai-smf; do
  run_container_capture "${container}" "${diag_dir}/containers/${container}_ip_addr.txt" ip addr
  run_container_capture "${container}" "${diag_dir}/containers/${container}_ip_route.txt" ip route
done

ping_probe ue_to_8_8_8_8 oai-nr-ue "${diag_dir}/pings/nr-ue_to_8.8.8.8_via_oaitun_ue1.txt" ping -I oaitun_ue1 -c 5 -W 2 8.8.8.8 || true
ping_probe ue_to_ext_dn oai-nr-ue "${diag_dir}/pings/nr-ue_to_192.168.71.135_via_oaitun_ue1.txt" ping -I oaitun_ue1 -c 5 -W 2 192.168.71.135 || true
ping_probe ue_to_upf_tun oai-nr-ue "${diag_dir}/pings/nr-ue_to_10.0.0.1_via_oaitun_ue1.txt" ping -I oaitun_ue1 -c 5 -W 2 10.0.0.1 || true
ping_probe upf_to_ue oai-upf "${diag_dir}/pings/upf_to_10.0.0.2.txt" ping -c 5 -W 2 10.0.0.2 || true
ping_probe upf_to_ext_dn oai-upf "${diag_dir}/pings/upf_to_192.168.71.135.txt" ping -c 5 -W 2 192.168.71.135 || true
ping_probe ext_dn_to_ue oai-ext-dn "${diag_dir}/pings/ext-dn_to_10.0.0.2.txt" ping -c 5 -W 2 10.0.0.2 || true
ping_probe ext_dn_to_upf_tun oai-ext-dn "${diag_dir}/pings/ext-dn_to_10.0.0.1.txt" ping -c 5 -W 2 10.0.0.1 || true

run_container_shell_capture oai-nr-ue "${diag_dir}/traces/nr-ue_to_8.8.8.8_via_oaitun_ue1.txt" 'if command -v tracepath >/dev/null 2>&1; then tracepath -i oaitun_ue1 8.8.8.8; elif command -v traceroute >/dev/null 2>&1; then traceroute -i oaitun_ue1 8.8.8.8; else echo "tracepath/traceroute not installed"; fi'
run_container_shell_capture oai-nr-ue "${diag_dir}/traces/nr-ue_to_192.168.71.135_via_oaitun_ue1.txt" 'if command -v tracepath >/dev/null 2>&1; then tracepath -i oaitun_ue1 192.168.71.135; elif command -v traceroute >/dev/null 2>&1; then traceroute -i oaitun_ue1 192.168.71.135; else echo "tracepath/traceroute not installed"; fi'
run_container_shell_capture oai-upf "${diag_dir}/traces/upf_to_192.168.71.135.txt" 'if command -v tracepath >/dev/null 2>&1; then tracepath 192.168.71.135; elif command -v traceroute >/dev/null 2>&1; then traceroute 192.168.71.135; else echo "tracepath/traceroute not installed"; fi'
run_container_shell_capture oai-ext-dn "${diag_dir}/traces/ext-dn_to_10.0.0.2.txt" 'if command -v tracepath >/dev/null 2>&1; then tracepath 10.0.0.2; elif command -v traceroute >/dev/null 2>&1; then traceroute 10.0.0.2; else echo "tracepath/traceroute not installed"; fi'

for container in oai-upf oai-ext-dn; do
  run_container_shell_capture "${container}" "${diag_dir}/firewall/${container}_iptables_S.txt" 'if command -v iptables >/dev/null 2>&1; then iptables -S; else echo "iptables not installed"; fi'
  run_container_shell_capture "${container}" "${diag_dir}/firewall/${container}_iptables_nat_S.txt" 'if command -v iptables >/dev/null 2>&1; then iptables -t nat -S; else echo "iptables not installed"; fi'
  run_container_shell_capture "${container}" "${diag_dir}/firewall/${container}_nft_ruleset.txt" 'if command -v nft >/dev/null 2>&1; then nft list ruleset; else echo "nft not installed"; fi'
  run_container_shell_capture "${container}" "${diag_dir}/containers/${container}_sysctl_ip_forward.txt" 'sysctl net.ipv4.ip_forward 2>/dev/null || cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo "ip_forward unavailable"'
done

status_value() {
  local key="$1"
  awk -F= -v key="${key}" '$1 == key {value=$2} END {print value}' "${diag_dir}/probe_status.env"
}

ue_internet="$(status_value ue_to_8_8_8_8)"
ue_ext_dn="$(status_value ue_to_ext_dn)"
upf_ext_dn="$(status_value upf_to_ext_dn)"
ext_dn_ue="$(status_value ext_dn_to_ue)"
upf_to_ue="$(status_value upf_to_ue)"
upf_ping_tool_available=true
if [[ "${upf_ext_dn}" == "tool_missing" || "${upf_to_ue}" == "tool_missing" ]]; then
  upf_ping_tool_available=false
fi

local_dn_reachability=false
if [[ "${ue_ext_dn}" == "pass" && "${ext_dn_ue}" == "pass" ]]; then
  local_dn_reachability=true
fi

if [[ "${local_dn_reachability}" == "true" ]]; then
  next_point="Local DN reachability is working; use ext-dn as the default research/smoke target."
elif [[ "${ue_internet}" == "pass" && "${ue_ext_dn}" != "pass" && "${upf_ext_dn}" == "pass" ]]; then
  next_point="Check ext-dn return path/NAT/firewall for UE subnet 10.0.0.0/24."
elif [[ "${ue_internet}" == "pass" && "${upf_ext_dn}" != "pass" && "${upf_ext_dn}" != "tool_missing" ]]; then
  next_point="Check UPF connectivity to traffic network 192.168.71.0/26 and ext-dn attachment."
elif [[ "${upf_ext_dn}" == "tool_missing" ]]; then
  next_point="UPF ping is unavailable in the image; rely on UE/ext-dn probes or inspect UPF routes/interfaces."
elif [[ "${ue_internet}" != "pass" ]]; then
  next_point="Check UE PDU session, oaitun_ue1 route, and UPF datapath before ext-dn-specific debugging."
else
  next_point="Compare ext-dn routes/firewall with UPF tunnel and traffic network captures."
fi

cat >"${diag_dir}/summary.txt" <<EOF
UE can reach internet via oaitun_ue1: ${ue_internet:-unknown}
UE can reach ext-dn 192.168.71.135 via oaitun_ue1: ${ue_ext_dn:-unknown}
UPF can reach ext-dn 192.168.71.135: ${upf_ext_dn:-unknown}
ext-dn can reach UE tunnel IP 10.0.0.2: ${ext_dn_ue:-unknown}
UPF ping tool available: ${upf_ping_tool_available}
Local DN reachability: ${local_dn_reachability}
Likely next investigation point: ${next_point}
EOF

cat >"${diag_dir}/summary.json" <<EOF
{
  "diagnostic_id": "$(json_escape "${diag_id}")",
  "local_dn_reachability": ${local_dn_reachability},
  "upf_ping_tool_available": ${upf_ping_tool_available},
  "ue_can_reach_internet": "$(json_escape "${ue_internet:-unknown}")",
  "ue_can_reach_ext_dn": "$(json_escape "${ue_ext_dn:-unknown}")",
  "upf_can_reach_ext_dn": "$(json_escape "${upf_ext_dn:-unknown}")",
  "ext_dn_can_reach_ue_tunnel_ip": "$(json_escape "${ext_dn_ue:-unknown}")",
  "likely_next_investigation_point": "$(json_escape "${next_point}")"
}
EOF

echo
cat "${diag_dir}/summary.txt"
echo
echo "[diag] wrote ${diag_dir}"
