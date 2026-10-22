from fastapi.testclient import TestClient

from sentinel.postmortem import build_postmortem
from sentinel.server.api import app

client = TestClient(app)


def test_health_and_ui():
    assert client.get("/api/health").json()["status"] == "ok"
    assert "Sentinel" in client.get("/").text


def test_run_graph_agent_returns_trace_postmortem_truth():
    d = client.post("/api/incidents/7/run?agent=graph&reveal=true").json()
    assert d["ground_truth"]["root"] == d["report"]["root_cause_service"]
    assert d["trace"] and d["postmortem"].startswith("# Incident postmortem")


def test_unknown_agent_and_missing_key():
    assert client.post("/api/incidents/1/run?agent=zzz").status_code == 404
    assert client.post("/api/incidents/1/run?agent=claude").status_code == 400


def test_postmortem_handles_empty_report():
    from sentinel.environment import Env
    from sentinel.simulator import generate
    assert "Incident postmortem" in build_postmortem(Env(generate(1)), {})


def test_mcp_server_registers_tools():
    import asyncio

    from sentinel.server.mcp_server import build
    names = {t.name for t in asyncio.run(build(3).list_tools())}
    assert {"list_alerts", "get_metrics", "run_remediation"} <= names
