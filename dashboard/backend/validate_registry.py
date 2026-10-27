from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from config import REPO_ROOT, TOPOLOGIES


def _container_names(compose_path: Path) -> set[str]:
    data: dict[str, Any] = yaml.safe_load(compose_path.read_text()) or {}
    services = data.get("services", {})
    names: set[str] = set()
    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        names.add(str(service.get("container_name") or service_name))
    return names


def main() -> int:
    failures: list[str] = []
    for topology in TOPOLOGIES.values():
        compose_names: set[str] = set()
        missing_files: list[str] = []
        for relative in topology.compose_files:
            path = REPO_ROOT / relative
            if not path.exists():
                missing_files.append(relative)
                continue
            compose_names.update(_container_names(path))

        if missing_files:
            failures.append(f"{topology.name}: missing compose files: {', '.join(missing_files)}")
            continue

        registry_names = {node.container for node in topology.nodes}
        missing_from_compose = sorted(registry_names - compose_names)
        if missing_from_compose:
            failures.append(
                f"{topology.name}: dashboard registry containers not found in compose: "
                f"{', '.join(missing_from_compose)}"
            )

        print(f"{topology.name}: registry={sorted(registry_names)}")
        print(f"{topology.name}: compose={sorted(compose_names)}")

    if failures:
        print("\nRegistry validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("\nRegistry validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
