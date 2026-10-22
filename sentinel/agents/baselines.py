"""Three agents with a common interface: agent(env) -> report dict
{root_cause_service, fault_type, remediation:{action,service}}."""
import json
import re

from ..environment import Env
from ..simulator import FAULTS, TOPOLOGY


def naive_agent(env: Env) -> dict:
    """Follows the loudest alert and applies the most common fix. The baseline to beat."""
    alerts = json.loads(env.list_alerts())
    top = alerts[0] if alerts else {"service": "gateway"}  # first/loudest user-facing alert
    return {"root_cause_service": top["service"], "fault_type": "bad_deploy",
            "remediation": {"action": "rollback", "service": top["service"]}}


LOG_RULES = [(r"NullPointer", "bad_deploy"), (r"pool exhausted", "db_pool"), (r"OutOfMemory", "memory_leak"),
             (r"connection refused", "cache_down"), (r"timeout_ms", "bad_config"),
             (r"no space left", "disk_full"), (r"certificate", "cert_expiry")]


def rules_agent(env: Env) -> dict:
    """Expert-system: finds the deepest degraded service, classifies fault from logs.
    Brittle when logs are missing (silent failures)."""
    alerts = {a["service"] for a in json.loads(env.list_alerts())}
    # root candidate = alerting service none of whose dependencies alert
    cands = [s for s in alerts if not any(d in alerts for d in TOPOLOGY[s])]
    root = cands[0] if cands else "gateway"
    logs = env.search_logs(root, "")
    fault = next((f for pat, f in LOG_RULES if re.search(pat, logs)), "bad_deploy")
    return {"root_cause_service": root, "fault_type": fault,
            "remediation": {"action": FAULTS[fault][0], "service": root}}
