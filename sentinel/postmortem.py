"""Blameless postmortem generation from an incident's tool trace and the agent's report."""
import json

from .environment import Env
from .simulator import FAULTS, ONSET


def build_postmortem(env: Env, report: dict) -> str:
    sc = env.sc
    root = report.get("root_cause_service", "unknown")
    fault = report.get("fault_type", "unknown")
    rem = report.get("remediation") or {}
    status = next((json.loads(t["result"]).get("status") for t in reversed(env.trace)
                   if t["tool"] == "run_remediation"), "not attempted")
    steps = "\n".join(f"{i}. `{t['tool']}({', '.join(f'{k}={v!r}' for k, v in t['args'].items())})`"
                      for i, t in enumerate(env.trace, 1))
    evidence = [json.loads(t["result"]) for t in env.trace if t["tool"] == "get_recent_changes"]
    causal = [c for batch in evidence for c in batch if c["service"] == root and "healthy" not in c["detail"]]
    return f"""# Incident postmortem (seed {sc.seed})

**Severity:** SEV-2 · **Detected:** minute {ONSET} · **Status:** {status}

## Summary
Customer-facing errors and latency rose from minute {ONSET}. The root cause was **{fault}** on
`{root}`, which cascaded up the call graph to its callers. Remediation: `{rem.get('action')}` on
`{rem.get('service')}`.

## Impact
Services in the dependency chain of `{root}` showed elevated error rate and/or p99 latency.

## Root cause
Fault class `{fault}` (canonical fix: `{FAULTS.get(fault, ('?',))[0]}`).
{('Causal change: ' + causal[0]['detail'] + f" at minute {causal[0]['min']}.") if causal else 'No causal change event found; diagnosis rests on metric shape and dependency analysis.'}

## Investigation timeline
{steps}

## What went well / what to improve
- Alerting fired on downstream symptoms{' only; the root service was silent and had no alert, so add alerting on it.' if sc.silent else ' and at the root service.'}
- Decoy change on `{sc.decoy_service}` was correctly ignored: {'yes' if root != sc.decoy_service else 'n/a'}.
- Add a runbook entry for `{fault}` and an automated pre-deploy check where applicable.

## Action items
- [ ] Add a metric-anomaly alert (not just error-rate) on `{root}`
- [ ] Review the approval policy for `{rem.get('action')}`
- [ ] Add this scenario to the regression benchmark
"""
