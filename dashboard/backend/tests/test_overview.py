"""Operator Overview data model: empty repo, inferred vs live UE paths, serving-DU
maps, and the live-latency parser (formerly validate_phase6)."""

import validate_phase6


def test_empty_repo():
    validate_phase6.validate_empty_repo()


def test_latest_run_chart_and_inferred_path():
    validate_phase6.validate_latest_run_chart_and_inferred_path()


def test_live_attached_ue_path():
    validate_phase6.validate_live_attached_ue_path()


def test_du_maps():
    validate_phase6.validate_du_maps()


def test_live_latency_parser():
    validate_phase6.validate_live_latency_parser()
