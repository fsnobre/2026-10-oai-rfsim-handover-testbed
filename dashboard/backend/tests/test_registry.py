"""Registry drift check: the dashboard container registry must still match the
compose files. Wraps validate_registry so the check runs under pytest."""

import validate_registry


def test_registry_matches_compose_files():
    assert validate_registry.main() == 0
