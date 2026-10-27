from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from actions import ActionError, ActionManager
from auth import verify_bearer, ws_token_ok
from collectors.campaigns import Campaigns
from collectors.config_parser import ConfigParser
from collectors.docker_monitor import DockerMonitor
from collectors.handover_events import HandoverEvents
from collectors.kpi_history import KpiHistory
from collectors.live_latency import LiveLatencyMonitor
from collectors.operator_overview import OperatorOverview
from collectors.results_collector import ResultsCollector
from collectors.run_artifacts import RunArtifacts
from collectors.snapshot import StateSnapshotService
from collectors.telnet_poller import TelnetPollerRegistry
from config import (
    ACTION_DEPLOY_TIMEOUT_SECONDS,
    ACTION_MEASURE_INTERRUPTION_TIMEOUT_SECONDS,
    ACTION_REPEATED_SMOKE_TIMEOUT_SECONDS,
    ACTION_SMOKE_TIMEOUT_SECONDS,
    ACTION_TEARDOWN_TIMEOUT_SECONDS,
    ACTION_TRIGGER_TIMEOUT_SECONDS,
    DASHBOARD_API_TOKEN,
    DASHBOARD_CORS_ORIGINS,
    DASHBOARD_ENABLE_ACTIONS,
    DASHBOARD_ENABLE_TELNET_POLLING,
    MEDIUM_INTERVAL_SECONDS,
    POLL_INTERVAL_SECONDS,
    REPO_ROOT,
    SLOW_INTERVAL_SECONDS,
    active_topology,
    topology_by_name,
)
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await snapshot_service.start()
    try:
        yield
    finally:
        await snapshot_service.stop()


app = FastAPI(title="OAI RFsim Handover Dashboard", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DASHBOARD_CORS_ORIGINS,
    # Auth is a bearer header, not a cookie, so credentialed CORS is not needed —
    # and "*" with credentials is a combination browsers reject outright.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency guarding action endpoints. No-op when DASHBOARD_API_TOKEN is unset."""
    verify_bearer(DASHBOARD_API_TOKEN, authorization)


docker_monitor = DockerMonitor()
config_parser = ConfigParser(REPO_ROOT)
results_collector = ResultsCollector(REPO_ROOT)
run_artifacts = RunArtifacts(REPO_ROOT)
handover_events = HandoverEvents(REPO_ROOT)
operator_overview = OperatorOverview(handover_events)
campaigns_collector = Campaigns(REPO_ROOT)
kpi_history = KpiHistory()
live_latency_monitor = LiveLatencyMonitor()
telnet_pollers = TelnetPollerRegistry()
action_manager = ActionManager(
    REPO_ROOT,
    actions_enabled=DASHBOARD_ENABLE_ACTIONS,
    trigger_timeout_seconds=ACTION_TRIGGER_TIMEOUT_SECONDS,
    measure_interruption_timeout_seconds=ACTION_MEASURE_INTERRUPTION_TIMEOUT_SECONDS,
    smoke_timeout_seconds=ACTION_SMOKE_TIMEOUT_SECONDS,
    repeated_smoke_timeout_seconds=ACTION_REPEATED_SMOKE_TIMEOUT_SECONDS,
    deploy_timeout_seconds=ACTION_DEPLOY_TIMEOUT_SECONDS,
    teardown_timeout_seconds=ACTION_TEARDOWN_TIMEOUT_SECONDS,
)


def current_topology() -> Any:
    """The topology the dashboard is currently monitoring, as detected by the collector."""
    return topology_by_name(build_state().get("topology"))


async def current_telnet_state() -> dict[str, Any]:
    """Telnet state for the current topology's control node: the CU for F1, the source
    gNB/CU for N2. Passive polling stays disabled by default."""
    poller = telnet_pollers.for_topology(current_topology())
    if poller is None:
        return TelnetPollerRegistry.no_endpoint_state()
    if not DASHBOARD_ENABLE_TELNET_POLLING:
        return poller.disabled_state()
    return await poller.poll()


snapshot_service = StateSnapshotService(
    repo_root=REPO_ROOT,
    topology_provider=active_topology,
    docker_monitor=docker_monitor,
    config_parser=config_parser,
    results_collector=results_collector,
    handover_events=handover_events,
    operator_overview=operator_overview,
    campaigns=campaigns_collector,
    kpi_history=kpi_history,
    live_latency_monitor=live_latency_monitor,
    action_manager=action_manager,
    telnet_state=current_telnet_state,
    fast_interval_seconds=POLL_INTERVAL_SECONDS,
    medium_interval_seconds=MEDIUM_INTERVAL_SECONDS,
    slow_interval_seconds=SLOW_INTERVAL_SECONDS,
)


def build_state() -> dict[str, Any]:
    """The latest snapshot published by the background collector."""
    return snapshot_service.current()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/topology")
async def topology() -> dict[str, Any]:
    return build_state()


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    state = build_state()
    return {"overview": state["overview"], "warnings": state["overview"].get("warnings", [])}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    parsed_config, warnings = await asyncio.to_thread(config_parser.parse_f1)
    return {"topology": "f1", "config": parsed_config, "warnings": warnings}


@app.get("/api/runs")
async def runs() -> dict[str, Any]:
    items, warnings = await asyncio.to_thread(run_artifacts.list_runs)
    return {"runs": items, "warnings": warnings}


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: str) -> dict[str, Any]:
    detail, warnings = await asyncio.to_thread(run_artifacts.get_run, run_id)
    if detail is None:
        return {"run_id": run_id, "run": None, "warnings": warnings}
    return {"run_id": run_id, "run": detail, "warnings": warnings}


@app.get("/api/kpi/history")
async def kpi_history_endpoint() -> dict[str, Any]:
    return {"history": kpi_history.samples(), "retention_seconds": kpi_history.retention_seconds}


@app.get("/api/ues")
async def ues() -> dict[str, Any]:
    telnet = await current_telnet_state()
    cu = telnet.get("cu", {})
    attached = cu.get("attached_ues", [])
    warnings = list(cu.get("warnings", []))
    if not attached:
        warnings.append("No live UE context available from current telemetry source.")
    return {"ues": attached, "ue_count": cu.get("ue_count"), "warnings": warnings, "telnet": cu}


@app.get("/api/gnb")
async def gnb() -> dict[str, Any]:
    state = build_state()
    return {
        "topology": state["topology"],
        "config": state["config"],
        "containers": [
            item for item in state["containers"] if item.get("role") in {"cu", "du", "gnb", "ue"}
        ],
        "telnet": state["telnet"],
        "live_kpis": state["live_kpis"],
        "history": state["kpi_history"],
        "warnings": state["warnings"],
        "freshness": state["freshness"],
    }


@app.get("/api/handover")
async def handover() -> dict[str, Any]:
    state = build_state()
    return {"handover": state["handover"], "warnings": state["handover"].get("warnings", [])}


@app.get("/api/handover/runs")
async def handover_runs() -> dict[str, Any]:
    runs, warnings = await asyncio.to_thread(handover_events.runs)
    return {"runs": runs, "warnings": warnings}


@app.get("/api/handover/runs/{run_id}")
async def handover_run_detail(run_id: str) -> dict[str, Any]:
    detail, warnings = await asyncio.to_thread(handover_events.run_detail, run_id)
    if detail is None:
        return {"run_id": run_id, "run": None, "warnings": warnings}
    return {"run_id": run_id, "run": detail, "warnings": warnings}


@app.get("/api/handover/message-flow/{run_id}")
async def handover_message_flow(run_id: str) -> dict[str, Any]:
    flow, warnings = await asyncio.to_thread(handover_events.message_flow, run_id)
    return {"run_id": run_id, "message_flow": flow, "warnings": warnings}


@app.get("/api/handover/durations")
async def handover_durations() -> dict[str, Any]:
    durations, warnings = await asyncio.to_thread(handover_events.durations)
    return {"durations": durations, "warnings": warnings}


@app.get("/api/campaigns")
async def campaigns() -> dict[str, Any]:
    items, warnings = await asyncio.to_thread(campaigns_collector.list_campaigns)
    return {"campaigns": items, "warnings": warnings}


@app.get("/api/campaigns/compare")
async def campaigns_compare() -> dict[str, Any]:
    comparison, warnings = await asyncio.to_thread(campaigns_collector.compare)
    return {"comparison": comparison, "warnings": warnings}


@app.get("/api/campaigns/export")
async def campaigns_export() -> dict[str, Any]:
    rows, warnings = await asyncio.to_thread(campaigns_collector.export_rows)
    return {"rows": rows, "warnings": warnings}


@app.get("/api/campaigns/{campaign_id}")
async def campaign_detail(campaign_id: str) -> dict[str, Any]:
    detail, warnings = await asyncio.to_thread(campaigns_collector.get_campaign, campaign_id)
    if detail is None:
        return {"campaign_id": campaign_id, "campaign": None, "warnings": warnings}
    return {"campaign_id": campaign_id, "campaign": detail, "warnings": warnings}


@app.get("/api/actions/capabilities", dependencies=[Depends(require_api_token)])
async def action_capabilities() -> dict[str, Any]:
    return action_manager.capabilities()


@app.post("/api/actions/trigger-handover", dependencies=[Depends(require_api_token)])
async def trigger_handover_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_trigger_handover(
            confirm=payload.get("confirm") is True,
            topology=current_topology().name,
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.post("/api/actions/measure-interruption", dependencies=[Depends(require_api_token)])
async def measure_interruption_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_measure_interruption(
            confirm=payload.get("confirm") is True,
            topology=current_topology().name,
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.post("/api/actions/smoke-test", dependencies=[Depends(require_api_token)])
async def smoke_test_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_smoke_test(
            confirm=payload.get("confirm") is True,
            topology=str(payload.get("topology") or ""),
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.post("/api/actions/deploy-topology", dependencies=[Depends(require_api_token)])
async def deploy_topology_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_deploy_topology(
            confirm=payload.get("confirm") is True,
            topology=str(payload.get("topology") or ""),
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.post("/api/actions/teardown-topology", dependencies=[Depends(require_api_token)])
async def teardown_topology_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_teardown_topology(
            confirm=payload.get("confirm") is True,
            topology=str(payload.get("topology") or ""),
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.post("/api/actions/repeated-smoke-test", dependencies=[Depends(require_api_token)])
async def repeated_smoke_test_action(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        job = await action_manager.start_repeated_smoke_test(
            confirm=payload.get("confirm") is True,
            topology=str(payload.get("topology") or ""),
            count=int(payload.get("count") or 0),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="count must be an integer") from exc
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"job": job}


@app.get("/api/actions/jobs", dependencies=[Depends(require_api_token)])
async def action_jobs() -> dict[str, Any]:
    return {"jobs": action_manager.jobs(include_tails=False), "running_job": action_manager.actions_summary()["running_job"]}


@app.get("/api/actions/jobs/{job_id}", dependencies=[Depends(require_api_token)])
async def action_job(job_id: str) -> dict[str, Any]:
    job = action_manager.job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Action job not found: {job_id}")
    return {"job": job}


@app.websocket("/ws")
async def websocket(websocket: WebSocket) -> None:
    if not ws_token_ok(DASHBOARD_API_TOKEN, websocket.query_params.get("token")):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    # Track the published version so each client sends every snapshot exactly once and
    # a new client gets the current state immediately instead of waiting a full cycle.
    version = -1
    try:
        while True:
            version, state = await snapshot_service.wait_for_next(version)
            await websocket.send_json(state)
    except WebSocketDisconnect:
        return
