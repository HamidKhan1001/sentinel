"""Fault-injection simulator of a microservice stack.

Generates minute-resolution metrics, logs, change events and alerts for a seeded
incident, plus ground truth for scoring. Faults propagate up the call graph,
and scenarios include decoy deploys, noisy logs and 'silent' root causes.
"""
import random
from dataclasses import dataclass, field

TOPOLOGY = {
    "gateway": ["auth", "orders"], "orders": ["payments", "inventory", "cache"],
    "payments": ["db"], "inventory": ["db"], "auth": ["db", "cache"],
    "db": [], "cache": [],
}
SERVICES = list(TOPOLOGY)
METRICS = ("error_rate", "p99_ms", "cpu", "mem")
MINUTES, ONSET = 60, 35

# fault -> (correct remediation, log signature, metric signature at root)
FAULTS = {
    "bad_deploy":     ("rollback",     "NullPointerException in handler (build {v})", {"error_rate": 25}),
    "db_pool":        ("scale_pool",   "connection pool exhausted (active=100/100)",  {"p99_ms": 2500, "error_rate": 12}),
    "memory_leak":    ("restart",      "java.lang.OutOfMemoryError: heap space",      {"mem": "ramp"}),
    "cache_down":     ("restart",      "connection refused 127.0.0.1:6379",           {"error_rate": 30}),
    "bad_config":     ("revert_config","timeout_ms=50 applied from config push",      {"p99_ms": 900, "error_rate": 8}),
    "disk_full":      ("expand_disk",  "write failed: no space left on device",       {"error_rate": 20}),
    "cert_expiry":    ("renew_cert",   "x509: certificate has expired",               {"error_rate": 35}),
}
# which services can plausibly host which fault
HOSTS = {
    "bad_deploy": ["auth", "orders", "payments", "inventory"], "db_pool": ["db"],
    "memory_leak": ["orders", "payments", "inventory", "auth"], "cache_down": ["cache"],
    "bad_config": ["orders", "payments", "auth"], "disk_full": ["db"],
    "cert_expiry": ["gateway", "payments", "auth"],
}
BASE = {"error_rate": 0.4, "p99_ms": 120.0, "cpu": 35.0, "mem": 50.0}


def callers_of(svc):
    return [s for s, deps in TOPOLOGY.items() if svc in deps]


def depth_from(root, svc, seen=None):
    """Hops from svc down to root along dependencies, or None if unreachable."""
    if svc == root:
        return 0
    best = None
    for d in TOPOLOGY[svc]:
        r = depth_from(root, d)
        if r is not None and (best is None or r + 1 < best):
            best = r + 1
    return best


@dataclass
class Scenario:
    seed: int
    fault: str
    root: str
    remediation: str
    silent: bool
    decoy_service: str
    metrics: dict = field(default_factory=dict)   # (svc, metric) -> list[float]
    logs: dict = field(default_factory=dict)      # svc -> list[(minute, level, msg)]
    changes: list = field(default_factory=list)   # (minute, service, kind, detail)
    alerts: list = field(default_factory=list)


def generate(seed: int, silent: bool | None = None) -> Scenario:
    rng = random.Random(seed)
    fault = rng.choice(list(FAULTS))
    root = rng.choice(HOSTS[fault])
    fix, sig, effect = FAULTS[fault]
    silent = rng.random() < 0.35 if silent is None else silent
    decoy = rng.choice([s for s in SERVICES if s != root])
    sc = Scenario(seed, fault, root, fix, silent, decoy)

    for s in SERVICES:
        for m in METRICS:
            sc.metrics[(s, m)] = [max(0.0, rng.gauss(BASE[m], BASE[m] * 0.08)) for _ in range(MINUTES)]
        sc.logs[s] = [(t, "INFO", rng.choice(["request ok", "health check ok", "cache hit", "gc pause 12ms"]))
                      for t in range(0, MINUTES, 4)]
        if rng.random() < 0.5:  # noisy but harmless warnings
            sc.logs[s].append((rng.randrange(10, 30), "WARN", "slow query 310ms (non-critical)"))

    # root-cause effects, then propagation upstream with decay and delay
    for s in SERVICES:
        d = depth_from(root, s)
        if d is None:
            continue
        decay, delay = 0.55 ** d, d
        for m, v in effect.items():
            for t in range(ONSET + delay, MINUTES):
                if v == "ramp":
                    if d == 0:
                        sc.metrics[(s, "mem")][t] = min(99.0, 50 + (t - ONSET) * 2.2)
                else:
                    sc.metrics[(s, m)][t] += v * decay
        if d == 0 and fault == "memory_leak":
            for t in range(ONSET, MINUTES):
                sc.metrics[(s, "error_rate")][t] += 4 + (t - ONSET) * 0.5
        if d > 0:
            for t in range(ONSET + delay, MINUTES, 2):
                sc.logs[s].append((t, "ERROR", f"upstream call to {_next_hop(s, root)} failed or timed out"))
    if not silent:
        for t in range(ONSET, MINUTES, 3):
            sc.logs[root].append((t, "ERROR", sig.format(v="2.3.1")))

    # change events: real cause (if any) plus a decoy that did not cause the issue
    if fault == "bad_deploy":
        sc.changes.append((ONSET - 2, root, "deploy", "release 2.3.1 rolled out"))
    elif fault == "bad_config":
        sc.changes.append((ONSET - 1, root, "config", "timeout_ms: 2000 -> 50"))
    sc.changes.append((rng.randrange(5, 25), decoy, "deploy", "release 1.9.0 rolled out (healthy)"))

    for s in SERVICES:
        if silent and s == root:   # unmonitored / alert-suppressed root cause
            continue
        since = ONSET + rng.randrange(0, 4)   # no ordering signal leaks the root
        if max(sc.metrics[(s, "error_rate")][-5:]) > 3:
            sc.alerts.append({"service": s, "alert": "HighErrorRate", "since_min": since})
        if max(sc.metrics[(s, "p99_ms")][-5:]) > 400:
            sc.alerts.append({"service": s, "alert": "HighLatency", "since_min": since})
    return sc


def _next_hop(svc, root):
    for d in TOPOLOGY[svc]:
        if depth_from(root, d) is not None:
            return d
    return root
