"""Benchmark harness: run agents over seeded incidents and score against ground truth."""
import statistics
from dataclasses import dataclass, field

from ..agents import AGENTS, Usage
from ..environment import Env
from ..simulator import generate


def score(env: Env, report: dict) -> dict:
    sc = env.sc
    fixed = any(a == sc.remediation and s == sc.root and ok for a, s, ok in env.remediations)
    return {
        "seed": sc.seed, "fault": sc.fault, "silent": sc.silent,
        "rca_service": report.get("root_cause_service") == sc.root,
        "rca_fault": report.get("fault_type") == sc.fault,
        "fixed": fixed,
        "unsafe": sum(1 for a, s, ok in env.remediations if not ok or s != sc.root),
        "tools": len(env.calls),
    }


@dataclass
class Result:
    name: str
    rows: list = field(default_factory=list)
    cost: float = 0.0

    def pct(self, key, silent=None) -> float:
        rows = [r for r in self.rows if silent is None or r["silent"] == silent]
        return 100 * sum(r[key] for r in rows) / max(1, len(rows))

    def summary(self) -> dict:
        return {"agent": self.name, "n": len(self.rows),
                "root_service": round(self.pct("rca_service"), 1),
                "fault_type": round(self.pct("rca_fault"), 1),
                "fixed": round(self.pct("fixed"), 1),
                "fixed_loud": round(self.pct("fixed", silent=False), 1),
                "fixed_silent": round(self.pct("fixed", silent=True), 1),
                "unsafe_per_incident": round(statistics.mean(r["unsafe"] for r in self.rows), 2),
                "tools_per_incident": round(statistics.mean(r["tools"] for r in self.rows), 1),
                "cost_usd": round(self.cost, 4)}


def run_agent(name: str, seeds, client=None) -> Result:
    fn, needs_llm = AGENTS[name]
    res = Result(name)
    for sd in seeds:
        env, usage = Env(generate(sd)), Usage()
        try:
            report = fn(env, usage, client) if needs_llm else fn(env)
        except Exception:  # a crashed episode counts as a failure
            report = {}
        rem = report.get("remediation") or {}
        if not env.remediations and rem:
            env.run_remediation(rem.get("action", ""), rem.get("service", ""))
        res.rows.append(score(env, report))
        res.cost += usage.cost
    return res
