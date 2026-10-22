"""`python -m sentinel <command>`: bench | investigate | serve | mcp"""
import argparse
import json
import sys

from .agents import AGENTS, Usage
from .bench import run_agent
from .config import settings
from .environment import Env
from .postmortem import build_postmortem
from .simulator import generate


def _agents(names):
    names = names or [n for n, (_, llm) in AGENTS.items() if not llm]
    missing = [n for n in names if AGENTS[n][1] and not settings.api_key]
    if missing:
        sys.exit(f"agents {missing} need ANTHROPIC_API_KEY")
    return names


def cmd_bench(a):
    results = [run_agent(n, range(a.n)) for n in _agents(a.agents)]
    print(f"{a.n} seeded incidents · 7 fault types · decoys · ~35% silent root causes\n")
    print(f"{'agent':7}{'svc%':>7}{'fault%':>8}{'fixed%':>8}{'silent%':>9}{'unsafe':>8}{'tools':>7}{'cost':>9}")
    for r in results:
        s = r.summary()
        print(f"{s['agent']:7}{s['root_service']:7.1f}{s['fault_type']:8.1f}{s['fixed']:8.1f}"
              f"{s['fixed_silent']:9.1f}{s['unsafe_per_incident']:8.2f}{s['tools_per_incident']:7.1f}{s['cost_usd']:9.3f}")
    if a.json:
        json.dump([r.summary() for r in results], open(a.json, "w"), indent=2)
    if a.svg:
        from .bench.chart import render
        open(a.svg, "w").write(render([r.summary() for r in results]))


def cmd_investigate(a):
    fn, llm = AGENTS[_agents([a.agent])[0]]
    env, usage = Env(generate(a.seed)), Usage()
    report = fn(env, usage) if llm else fn(env)
    rem = report.get("remediation") or {}
    if not env.remediations and rem:
        env.run_remediation(rem.get("action", ""), rem.get("service", ""))
    print(build_postmortem(env, report))
    print(f"ground truth: {env.sc.root} / {env.sc.fault} (silent={env.sc.silent})")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sentinel")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--n", type=int, default=100)
    b.add_argument("--agents", nargs="*", choices=list(AGENTS))
    b.add_argument("--json")
    b.add_argument("--svg")
    b.set_defaults(fn=cmd_bench)
    i = sub.add_parser("investigate")
    i.add_argument("--seed", type=int, default=7)
    i.add_argument("--agent", default="graph", choices=list(AGENTS))
    i.set_defaults(fn=cmd_investigate)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=lambda a: __import__("uvicorn").run("sentinel.server.api:app", host="0.0.0.0", port=a.port))
    m = sub.add_parser("mcp")
    m.add_argument("--seed", type=int, default=0)
    m.set_defaults(fn=lambda a: __import__("sentinel.server.mcp_server", fromlist=["main"]).main(a.seed))
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
