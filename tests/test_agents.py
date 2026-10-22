import json

from conftest import StubClient, final, tool_use

from sentinel.agents import Usage, graph_agent, llm_agent, multi_agent
from sentinel.agents.llm import parse_json_tail
from sentinel.bench import run_agent
from sentinel.environment import Env
from sentinel.simulator import generate


def test_graph_agent_solves_silent_and_loud():
    r = run_agent("graph", range(60))
    assert r.pct("fixed") == 100 and r.pct("fixed", silent=True) == 100


def test_ordering_naive_rules_graph():
    p = {n: run_agent(n, range(60)).pct("fixed") for n in ("naive", "rules", "graph")}
    assert p["naive"] < p["rules"] < p["graph"]


def test_rules_agent_fails_all_silent_incidents():
    assert run_agent("rules", range(60)).pct("fixed", silent=True) == 0


def test_parse_json_tail_ignores_prose_and_bad_braces():
    assert parse_json_tail('thinking {not json} ... {"a": 1}') == {"a": 1}
    assert parse_json_tail("nothing here") == {}


def test_llm_agent_tool_loop_with_stub():
    sc = generate(5)
    report = {"root_cause_service": sc.root, "fault_type": sc.fault,
              "remediation": {"action": sc.remediation, "service": sc.root}}
    client = StubClient([tool_use("get_recent_changes"),
                         tool_use("run_remediation", action=sc.remediation, service=sc.root),
                         final("done\n" + json.dumps(report))])
    env, usage = Env(sc), Usage()
    out = llm_agent(env, usage, client)
    assert out == report and [t["tool"] for t in env.trace] == ["get_recent_changes", "run_remediation"]
    assert usage.input_tokens == 300 and usage.cost > 0


def test_multi_agent_runs_three_specialists_then_commander():
    sc = generate(5)
    report = {"root_cause_service": sc.root, "fault_type": sc.fault, "remediation": {"action": sc.remediation, "service": sc.root}}
    client = StubClient([final('{"m":1}'), final('{"l":1}'), final('{"c":1}'),
                         tool_use("run_remediation", action=sc.remediation, service=sc.root),
                         final(json.dumps(report))])
    env = Env(sc)
    assert multi_agent(env, Usage(), client) == report and client.calls == 5


def test_graph_agent_report_schema():
    r = graph_agent(Env(generate(9)))
    assert set(r) == {"root_cause_service", "fault_type", "remediation"}
