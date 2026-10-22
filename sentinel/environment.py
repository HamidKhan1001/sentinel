"""Tool surface an agent sees. Same API is exposed over MCP and to the LLM agent."""
import json
from dataclasses import dataclass, field

from .simulator.engine import METRICS, MINUTES, SERVICES, TOPOLOGY, Scenario, depth_from

ACTIONS = ("rollback", "restart", "scale_pool", "revert_config", "expand_disk", "renew_cert")
DESTRUCTIVE = {"restart", "rollback"}


@dataclass
class Env:
    sc: Scenario
    calls: list = field(default_factory=list)
    trace: list = field(default_factory=list)         # [{tool, args, result}] for UIs and postmortems
    remediations: list = field(default_factory=list)  # (action, service, approved)

    def _rec(self, name, **kw):
        self.calls.append((name, kw))

    def _out(self, name: str, kw: dict, result: str) -> str:
        self.trace.append({"tool": name, "args": kw, "result": result})
        return result

    # ---- read-only tools ----
    def list_alerts(self) -> str:
        self._rec("list_alerts")
        return self._out(*self.calls[-1], json.dumps(self.sc.alerts))

    def get_topology(self) -> str:
        self._rec("get_topology")
        return self._out(*self.calls[-1], json.dumps(TOPOLOGY))

    def get_metrics(self, service: str, metric: str, last_minutes: int = 30) -> str:
        self._rec("get_metrics", service=service, metric=metric)
        if service not in SERVICES or metric not in METRICS:
            return self._out(*self.calls[-1], json.dumps({"error": f"service in {SERVICES}, metric in {list(METRICS)}"}))
        n = max(1, min(last_minutes, MINUTES))
        series = [round(x, 1) for x in self.sc.metrics[(service, metric)][-n:]]
        return self._out(*self.calls[-1], json.dumps({"service": service, "metric": metric, "minute_start": MINUTES - n, "values": series}))

    def search_logs(self, service: str, query: str = "") -> str:
        self._rec("search_logs", service=service, query=query)
        if service not in SERVICES:
            return self._out(*self.calls[-1], json.dumps({"error": f"unknown service {service}"}))
        rows = [r for r in self.sc.logs[service] if query.lower() in r[2].lower() and r[1] != "INFO"]
        return self._out(*self.calls[-1], json.dumps([{"min": t, "level": l, "msg": m} for t, l, m in rows[-12:]]))

    def get_recent_changes(self) -> str:
        self._rec("get_recent_changes")
        return self._out(*self.calls[-1], json.dumps([{"min": t, "service": s, "kind": k, "detail": d} for t, s, k, d in sorted(self.sc.changes)]))

    # ---- write tool, gated by human approval ----
    def run_remediation(self, action: str, service: str) -> str:
        self._rec("run_remediation", action=action, service=service)
        if action not in ACTIONS or service not in SERVICES:
            return self._out(*self.calls[-1], json.dumps({"error": f"action in {list(ACTIONS)}, service in {SERVICES}"}))
        approved = self._approve(action, service)
        self.remediations.append((action, service, approved))
        if not approved:
            return self._out(*self.calls[-1], json.dumps({"status": "rejected_by_approver", "reason": "blast radius too high for a service that is not degraded"}))
        ok = action == self.sc.remediation and service == self.sc.root
        return self._out(*self.calls[-1], json.dumps({"status": "executed", "result": "service recovered" if ok else "no improvement"}))

    def _approve(self, action, service) -> bool:
        """Simulated human-in-the-loop: destructive actions on a healthy service are refused.
        'Degraded' means actually affected by the incident, not merely alerting (silent roots don't alert)."""
        if action in DESTRUCTIVE:
            return depth_from(self.sc.root, service) is not None
        return True


TOOL_SPECS = [
    {"name": "list_alerts", "description": "List currently firing alerts.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_topology", "description": "Service dependency graph (service -> services it calls).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_metrics", "description": "Per-minute metric series. metric: error_rate|p99_ms|cpu|mem.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}, "metric": {"type": "string"}, "last_minutes": {"type": "integer"}}, "required": ["service", "metric"]}},
    {"name": "search_logs", "description": "Non-INFO log lines for a service, optional substring filter.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}, "query": {"type": "string"}}, "required": ["service"]}},
    {"name": "get_recent_changes", "description": "Recent deploys and config changes across services.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_remediation", "description": f"Apply a fix ({', '.join(ACTIONS)}). Requires approval; destructive actions on healthy services are refused. Only call once confident.",
     "input_schema": {"type": "object", "properties": {"action": {"type": "string"}, "service": {"type": "string"}}, "required": ["action", "service"]}},
]
