"""FastAPI service: run any agent on any seeded incident and get trace + postmortem + scenario data."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..agents import AGENTS, Usage
from ..config import settings
from ..environment import Env
from ..postmortem import build_postmortem
from ..simulator import METRICS, SERVICES, TOPOLOGY, generate

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Sentinel", version=__version__)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "llm_available": bool(settings.api_key),
            "agents": [n for n, (_, llm) in AGENTS.items() if not llm or settings.api_key]}


@app.get("/api/incidents/{seed}")
def incident(seed: int):
    sc = generate(seed)
    return {"seed": seed, "topology": TOPOLOGY, "alerts": sc.alerts,
            "metrics": {f"{s}:{m}": [round(x, 1) for x in sc.metrics[(s, m)]] for s in SERVICES for m in METRICS}}


@app.post("/api/incidents/{seed}/run")
def run(seed: int, agent: str = "graph", reveal: bool = False):
    if agent not in AGENTS:
        raise HTTPException(404, f"unknown agent; choose from {list(AGENTS)}")
    fn, needs_llm = AGENTS[agent]
    if needs_llm and not settings.api_key:
        raise HTTPException(400, "this agent needs ANTHROPIC_API_KEY")
    env, usage = Env(generate(seed)), Usage()
    report = fn(env, usage) if needs_llm else fn(env)
    rem = report.get("remediation") or {}
    if not env.remediations and rem:
        env.run_remediation(rem.get("action", ""), rem.get("service", ""))
    out = {"report": report, "trace": env.trace, "postmortem": build_postmortem(env, report),
           "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "cost_usd": round(usage.cost, 5)}}
    if reveal:  # ground truth, for demos and debugging
        sc = env.sc
        out["ground_truth"] = {"root": sc.root, "fault": sc.fault, "remediation": sc.remediation, "silent": sc.silent}
    return out
