"""Detect whether the repository path actions run from is the path the host sees.

The backend drives the *host* Docker daemon through the mounted socket, but bind-mount
paths inside a compose file are resolved by that daemon. So when the backend runs from an
in-container alias such as ``/repo``, every compose stack it starts asks the host for
``/repo/...`` — which does not exist there. Docker does not fail on a missing bind source:
it silently creates an empty directory. The OAI containers then get empty directories
mounted where ``config.yaml`` and the subscriber database should be, the core never comes
up, and root-owned junk is left on the host filesystem.

That failure is invisible from inside the container, so it is detected here by comparing
the repository root against the host-side source of the backend's own bind mount, and
compose-spawning actions are refused when they do not match.

Blocking requires positive evidence of a mismatch. If the mount cannot be inspected, or
the backend is not containerised at all, actions proceed as before.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import docker
    from docker.errors import DockerException
except ModuleNotFoundError:  # pragma: no cover - lightweight validation environments
    docker = None

    class DockerException(Exception):
        pass


# Distinguishes "read the mounts from the environment" from "the mounts are unknown".
_UNSET = object()

# Set by dashboard/docker-compose.dashboard.yml. Overridable for non-standard deployments.
BACKEND_CONTAINER_NAME = os.environ.get("DASHBOARD_BACKEND_CONTAINER", "oai-dashboard-backend")

REMEDIATION = (
    "The backend runs actions from {repo_root}, but the host Docker daemon sees that "
    "content at {host_path}. Compose stacks started from here would resolve their bind "
    "mounts against {repo_root} on the host, where Docker silently creates empty "
    "directories in place of the OAI config files. Restart the dashboard with the "
    "host-actions override so the repository is mounted at its real host path:\n"
    '  DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \\\n'
    "    docker compose -f dashboard/docker-compose.dashboard.yml \\\n"
    "      -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build"
)


def running_in_container() -> bool:
    return Path("/.dockerenv").exists()


def backend_container_mounts() -> list[dict[str, Any]] | None:
    """Bind mounts of the backend's own container, or None if they cannot be read."""
    if docker is None:
        return None
    try:
        client = docker.from_env()
        container = client.containers.get(BACKEND_CONTAINER_NAME)
        return container.attrs.get("Mounts") or []
    except (DockerException, Exception):
        return None


def _mount_for(mounts: list[dict[str, Any]], repo_root: str) -> dict[str, Any] | None:
    """The mount whose destination is the repo root or its closest containing parent."""
    best: dict[str, Any] | None = None
    for mount in mounts:
        destination = str(mount.get("Destination") or "")
        if not destination:
            continue
        if destination == repo_root or repo_root.startswith(destination.rstrip("/") + "/"):
            if best is None or len(destination) > len(str(best.get("Destination") or "")):
                best = mount
    return best


def host_repo_root_status(
    repo_root: Path | str,
    mounts: list[dict[str, Any]] | None | object = _UNSET,
    in_container: bool | None = None,
) -> dict[str, Any]:
    """Whether ``repo_root`` is a path the host Docker daemon resolves the same way.

    ``mounts`` and ``in_container`` are injectable for testing. Omitting ``mounts`` reads
    them from the running environment; passing ``None`` explicitly means they could not
    be determined, which never blocks.
    """
    root = str(repo_root)
    containerised = running_in_container() if in_container is None else in_container

    if not containerised:
        return {
            "host_visible": True,
            "verified": True,
            "repo_root": root,
            "host_path": root,
            "detail": None,
        }

    if mounts is _UNSET:
        mounts = backend_container_mounts()
    if mounts is None:
        return {
            "host_visible": True,
            "verified": False,
            "repo_root": root,
            "host_path": None,
            "detail": "Could not inspect the backend container's mounts; repository path not verified.",
        }

    mount = _mount_for(mounts, root)
    if mount is None:
        return {
            "host_visible": True,
            "verified": False,
            "repo_root": root,
            "host_path": None,
            "detail": "No bind mount covers the repository root; repository path not verified.",
        }

    destination = str(mount.get("Destination") or "")
    source = str(mount.get("Source") or "")
    # Translate the repo root through the mount to the equivalent host path.
    suffix = root[len(destination.rstrip("/")):] if destination != root else ""
    host_path = f"{source.rstrip('/')}{suffix}" if suffix else source

    if host_path == root:
        return {
            "host_visible": True,
            "verified": True,
            "repo_root": root,
            "host_path": host_path,
            "detail": None,
        }

    return {
        "host_visible": False,
        "verified": True,
        "repo_root": root,
        "host_path": host_path,
        "detail": REMEDIATION.format(repo_root=root, host_path=host_path),
    }
