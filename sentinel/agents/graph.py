"""Graph-reasoning agent: a deterministic diagnostic engine with no LLM.

Key ideas an SRE applies, encoded explicitly:
1. Anomaly detection straight from metrics (not alerts, which a silent root never fires).
2. Root = anomalous service with no anomalous dependency (symptoms flow up the call graph).
3. Fault classification from metric *shape*, recent changes, and the service's role.
"""
import json
import statistics

from ..environment import Env
from ..simulator import FAULTS, METRICS, SERVICES, TOPOLOGY

# per-metric (relative, absolute) thresholds vs the pre-incident baseline
THRESH = {"error_rate": (4.0, 2.0), "p99_ms": (1.8, 150.0), "cpu": (1.5, 20.0), "mem": (1.25, 12.0)}


def _series(env: Env, svc: str, metric: str) -> list[float]:
    return json.loads(env.get_metrics(svc, metric, 60))["values"]


def anomaly(values: list[float], metric: str) -> bool:
    base, recent = statistics.mean(values[:20]), statistics.mean(values[-5:])
    rel, ab = THRESH[metric]
    return recent > base * rel and recent - base > ab


def graph_agent(env: Env) -> dict:
    flags: dict[str, set[str]] = {s: set() for s in SERVICES}
    for s in SERVICES:
        for m in METRICS:
            if anomaly(_series(env, s, m), m):
                flags[s].add(m)
    degraded = {s for s, f in flags.items() if f}
    if not degraded:  # fall back to alerts
        degraded = {a["service"] for a in json.loads(env.list_alerts())} or {"gateway"}
    roots = [s for s in degraded if not any(d in degraded for d in TOPOLOGY[s])]
    # prefer the root with the most anomalous signals
    root = max(roots, key=lambda s: len(flags[s])) if roots else sorted(degraded)[0]

    changes = [c for c in json.loads(env.get_recent_changes()) if c["service"] == root]
    f = flags[root]
    if "mem" in f:
        fault = "memory_leak"
    elif any(c["kind"] == "config" for c in changes):
        fault = "bad_config"
    elif any(c["kind"] == "deploy" and "healthy" not in c["detail"] for c in changes):
        fault = "bad_deploy"
    elif "p99_ms" in f:
        fault = "db_pool" if root == "db" else "bad_config"
    elif root == "cache":
        fault = "cache_down"
    elif root == "db":
        fault = "disk_full"
    else:
        fault = "cert_expiry"
    return {"root_cause_service": root, "fault_type": fault,
            "remediation": {"action": FAULTS[fault][0], "service": root}}
