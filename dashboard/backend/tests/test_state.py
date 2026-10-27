"""Run artifacts, KPI history, UE-count sourcing, and telnet parsing
(formerly validate_phase2). Each validator is exposed as a granular test."""

import validate_phase2


def test_run_artifacts_missing():
    validate_phase2.validate_run_artifacts_missing()


def test_run_artifacts_partial():
    validate_phase2.validate_run_artifacts_partial()


def test_kpi_history_retention():
    validate_phase2.validate_kpi_history_retention()


def test_ue_count_sources():
    validate_phase2.validate_ue_count_sources()


def test_telnet_parsers():
    validate_phase2.validate_telnet_parsers()
