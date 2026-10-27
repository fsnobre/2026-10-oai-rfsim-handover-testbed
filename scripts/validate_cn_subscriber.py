#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

EXPECTED_IMSI = "001010000000001"
EXPECTED_SUPI = f"imsi-{EXPECTED_IMSI}"
EXPECTED_KEY = "fec86ba6eb707ed08905757b1bb44b8f"
EXPECTED_OPC = "C42449363BBAD02B66D16BC975D77CC1"
EXPECTED_DNN = "oai"
EXPECTED_SST_PATTERNS = ("\\\"sst\\\": 1", "\"sst\": 1")
EXPECTED_SD_PATTERNS = ("\\\"sd\\\": \"FFFFFF\"", "\"sd\": \"FFFFFF\"")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _auth_insert_for(sql: str, ueid: str) -> str | None:
    pattern = re.compile(
        r"INSERT INTO `AuthenticationSubscription` .*?VALUES\s*\n\s*\((?P<values>.*?)\);",
        re.S,
    )
    needle = f"'{ueid}'"
    for match in pattern.finditer(sql):
        values = match.group("values")
        if needle in values:
            return values
    return None


def main() -> int:
    sql_path = _repo_root() / "oai-cn5g" / "database" / "oai_db.sql"
    sql = sql_path.read_text()
    failures: list[str] = []

    for ueid in (EXPECTED_IMSI, EXPECTED_SUPI):
        row = _auth_insert_for(sql, ueid)
        if row is None:
            failures.append(f"missing AuthenticationSubscription row for {ueid}")
            continue
        if EXPECTED_KEY not in row:
            failures.append(f"AuthenticationSubscription row for {ueid} has unexpected key")
        if EXPECTED_OPC not in row:
            failures.append(f"AuthenticationSubscription row for {ueid} has unexpected OPC")
        if "5G_AKA" not in row or "milenage" not in row:
            failures.append(f"AuthenticationSubscription row for {ueid} has unexpected auth method/algorithm")

    session_row_match = re.search(
        r"INSERT INTO `SessionManagementSubscriptionData` .*?VALUES\s*\n\('001010000000001'.*?\);",
        sql,
        re.S,
    )
    if session_row_match is None:
        failures.append("missing SessionManagementSubscriptionData row for 001010000000001")
    else:
        session_row = session_row_match.group(0)
        if EXPECTED_DNN not in session_row:
            failures.append("SessionManagementSubscriptionData row is missing DNN oai")
        if not re.search(r'\\?"sst\\?"\s*:\s*1', session_row) or not re.search(
            r'\\?"sd\\?"\s*:\s*\\?"FFFFFF\\?"', session_row
        ):
            failures.append("SessionManagementSubscriptionData row is missing slice SST 1 / SD FFFFFF")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}", file=sys.stderr)
        return 1

    print("[PASS] RFsim subscriber seed contains numeric and imsi-prefixed auth aliases, DNN oai, and SST 1 / SD FFFFFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
