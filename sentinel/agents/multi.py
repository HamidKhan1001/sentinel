"""Multi-agent mode: three specialists investigate in parallel lanes, a commander decides.

Specialists get *restricted* tool subsets (least privilege) and return structured findings;
the commander sees only findings plus the topology, then makes the single remediation call.
"""
import json

from ..environment import TOOL_SPECS, Env
from .llm import REPORT_SCHEMA, Usage, make_client, parse_json_tail, tool_loop

SPECIALISTS = {
    "metrics": (["get_metrics", "get_topology"],
                "You are the METRICS analyst. For every service, check error_rate, p99_ms, cpu and mem. "
                "Report which services are anomalous, onset shape (step vs ramp vs spike), and which looks "
                "like the deepest/earliest. Reply with a short JSON findings object."),
    "logs": (["search_logs", "list_alerts"],
             "You are the LOGS analyst. Search non-INFO logs on every service. Report error signatures per "
             "service and which services have no relevant logs at all. Reply with a short JSON findings object."),
    "changes": (["get_recent_changes", "get_topology"],
                "You are the CHANGE analyst. Report deploys/config changes, which are plausibly causal "
                "(landed just before onset) versus decoys. Reply with a short JSON findings object."),
}

COMMANDER = f"""You are the incident COMMANDER. You receive findings from specialist analysts. Symptoms \
propagate UP the call graph; the root cause is the deepest degraded dependency, even if it is silent. \
Decide the root cause, call run_remediation ONCE, then end with JSON: {REPORT_SCHEMA}"""


def multi_agent(env: Env, usage: Usage | None = None, client=None) -> dict:
    usage = usage if usage is not None else Usage()
    client = client or make_client()
    by_name = {t["name"]: t for t in TOOL_SPECS}
    findings = {}
    for name, (tool_names, system) in SPECIALISTS.items():
        tools = [by_name[n] for n in tool_names]
        dispatch = {n: getattr(env, n) for n in tool_names}
        findings[name] = tool_loop(client, system, "Investigate the incident and report findings.",
                                   tools, dispatch, usage, max_steps=10)
    tools = [by_name[n] for n in ("get_topology", "run_remediation")]
    dispatch = {n: getattr(env, n) for n in ("get_topology", "run_remediation")}
    prompt = "Specialist findings:\n" + json.dumps(findings, indent=1)
    text = tool_loop(client, COMMANDER, prompt, tools, dispatch, usage, max_steps=6)
    return parse_json_tail(text)
