from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import yaml

ASSIGN_RE = re.compile(r"(?P<key>[A-Za-z0-9_]+)\s*=\s*(?P<value>[^;,\n#]+)")


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"//.*$", "", line)
        line = re.sub(r"#.*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def _clean_value(value: str) -> Any:
    value = value.strip().strip(",").strip()
    if value.endswith("L"):
        value = value[:-1]
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if re.fullmatch(r"0x[0-9a-fA-F]+", value):
        return value
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _assignments(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {}, [f"Config file missing: {path}"]
    try:
        text = _strip_comments(path.read_text())
    except Exception as exc:
        return {}, [f"Could not read {path}: {exc}"]

    values: dict[str, Any] = {}
    for match in ASSIGN_RE.finditer(text):
        values[match.group("key")] = _clean_value(match.group("value"))

    plmn = re.search(
        r"mcc\s*=\s*(?P<mcc>\d+).*?mnc\s*=\s*(?P<mnc>\d+).*?mnc_length\s*=\s*(?P<mnc_length>\d+)",
        text,
        flags=re.S,
    )
    if plmn:
        values["plmn"] = {
            "mcc": plmn.group("mcc"),
            "mnc": plmn.group("mnc"),
            "mnc_length": int(plmn.group("mnc_length")),
        }
    snssai = [int(item) for item in re.findall(r"sst\s*=\s*(\d+)", text)]
    if snssai:
        values["snssai"] = snssai
    amf = re.search(r"amf_ip_address\s*=\s*\(\{\s*ipv4\s*=\s*\"(?P<ip>[^\"]+)\"", text, flags=re.S)
    if amf:
        values["amf_ip_address"] = amf.group("ip")
    return values, warnings


def _compose(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"Compose file missing: {path}"]
    try:
        return yaml.safe_load(path.read_text()) or {}, []
    except Exception as exc:
        return {}, [f"Could not parse compose file {path}: {exc}"]


def _additional_options(service: dict[str, Any]) -> dict[str, Any]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env if "=" in item)
    options = str(env.get("USE_ADDITIONAL_OPTIONS", ""))
    tokens = shlex.split(options)
    parsed: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--") and index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
            parsed[token[2:]] = _clean_value(tokens[index + 1])
            index += 2
        else:
            if token.startswith("--"):
                parsed[token[2:]] = True
            index += 1
    return parsed


def _pick(values: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: values.get(key) for key in keys if key in values}


class ConfigParser:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def parse_f1(self) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        cu, cu_warnings = _assignments(self.repo_root / "conf-cu.conf")
        du, du_warnings = _assignments(self.repo_root / "conf-du.conf")
        ue, ue_warnings = _assignments(self.repo_root / "conf-nr-ue.conf")
        compose, compose_warnings = _compose(self.repo_root / "gnb-docker-compose.yaml")
        warnings.extend(cu_warnings + du_warnings + ue_warnings + compose_warnings)

        services = compose.get("services", {}) if isinstance(compose, dict) else {}
        du1_options = _additional_options(services.get("du1", {}))
        cu_options = _additional_options(services.get("cu", {}))

        du_common = {
            "gNB_ID": du.get("gNB_ID"),
            "gNB_name": du.get("gNB_name"),
            "plmn": du.get("plmn"),
            "snssai": du.get("snssai"),
            "tracking_area_code": du.get("tracking_area_code"),
            "band": du.get("dl_frequencyBand"),
            "ssb_arfcn": du.get("absoluteFrequencySSB"),
            "point_a": du.get("dl_absoluteFrequencyPointA"),
            "carrier_bandwidth": du.get("dl_carrierBandwidth"),
            "subcarrier_spacing": du.get("subcarrierSpacing") or du.get("dl_subcarrierSpacing"),
            "tdd_pattern": _pick(
                du,
                "dl_UL_TransmissionPeriodicity",
                "nrofDownlinkSlots",
                "nrofDownlinkSymbols",
                "nrofUplinkSlots",
                "nrofUplinkSymbols",
            ),
        }

        du0 = du_common | {
            "name": "DU0",
            "container": "oai-du0",
            "gNB_DU_ID": du.get("gNB_DU_ID"),
            "nr_cellid": du.get("nr_cellid"),
            "pci": du.get("physCellId"),
            "f1_local_address": du.get("local_n_address"),
            "f1_remote_address": du.get("remote_n_address"),
            "overrides": {},
        }
        du1_override_map = {
            "gNB_DU_ID": "gNBs.[0].gNB_DU_ID",
            "nr_cellid": "gNBs.[0].nr_cellid",
            "pci": "gNBs.[0].servingCellConfigCommon.[0].physCellId",
            "ssb_arfcn": "gNBs.[0].servingCellConfigCommon.[0].absoluteFrequencySSB",
            "point_a": "gNBs.[0].servingCellConfigCommon.[0].dl_absoluteFrequencyPointA",
            "ssb_bitmap": "gNBs.[0].servingCellConfigCommon.[0].ssb_PositionsInBurst_Bitmap",
            "f1_local_address": "MACRLCs.[0].local_n_address",
        }
        overrides = {public: du1_options[source] for public, source in du1_override_map.items() if source in du1_options}
        du1 = du_common | {
            "name": "DU1",
            "container": "oai-du1",
            "gNB_DU_ID": overrides.get("gNB_DU_ID", du.get("gNB_DU_ID")),
            "nr_cellid": overrides.get("nr_cellid", du.get("nr_cellid")),
            "pci": overrides.get("pci", du.get("physCellId")),
            "ssb_arfcn": overrides.get("ssb_arfcn", du.get("absoluteFrequencySSB")),
            "point_a": overrides.get("point_a", du.get("dl_absoluteFrequencyPointA")),
            "f1_local_address": overrides.get("f1_local_address", du.get("local_n_address")),
            "f1_remote_address": du.get("remote_n_address"),
            "overrides": overrides,
        }

        required = [
            ("CU gNB_ID", cu.get("gNB_ID")),
            ("CU AMF address", cu.get("amf_ip_address")),
            ("DU0 PCI", du0.get("pci")),
            ("DU1 PCI override", overrides.get("pci")),
            ("DU1 local F1 address override", overrides.get("f1_local_address")),
        ]
        for label, value in required:
            if value in {None, ""}:
                warnings.append(f"Unavailable field: {label}")

        return {
            "topology": "f1",
            "handover": {"type": "f1", "command": "ci trigger_f1_ho", "telnet": {"host": "192.168.70.150", "port": 9090}},
            "cu": {
                "container": "oai-cu",
                "gNB_ID": cu.get("gNB_ID"),
                "gNB_name": cu.get("gNB_name"),
                "plmn": cu.get("plmn"),
                "snssai": cu.get("snssai"),
                "tracking_area_code": cu.get("tracking_area_code"),
                "nr_cellid": cu.get("nr_cellid"),
                "f1_local_address": cu.get("local_s_address"),
                "f1_remote_address": cu.get("remote_s_address"),
                "amf_ip_address": cu.get("amf_ip_address"),
                "ng_amf_address": cu.get("GNB_IPV4_ADDRESS_FOR_NG_AMF"),
                "ngu_address": cu.get("GNB_IPV4_ADDRESS_FOR_NGU"),
                "compose_overrides": cu_options,
            },
            "dus": [du0, du1],
            "ue": {
                "container": "oai-nr-ue",
                "imsi": ue.get("imsi"),
                "dnn": ue.get("dnn"),
                "nssai_sst": ue.get("nssai_sst"),
                "rfsim_serveraddr": ue.get("serveraddr"),
            },
        }, warnings
