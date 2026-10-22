import json

from sentinel.environment import Env
from sentinel.simulator import SERVICES, generate


def test_destructive_action_on_unaffected_service_is_refused():
    sc = generate(1)
    env = Env(sc)
    from sentinel.simulator import depth_from
    unaffected = next(s for s in SERVICES if depth_from(sc.root, s) is None)
    assert json.loads(env.run_remediation("restart", unaffected))["status"] == "rejected_by_approver"


def test_correct_fix_recovers():
    sc = generate(2)
    out = json.loads(Env(sc).run_remediation(sc.remediation, sc.root))
    assert out["result"] == "service recovered"


def test_wrong_fix_does_not_recover():
    sc = generate(2)
    wrong = "renew_cert" if sc.remediation != "renew_cert" else "expand_disk"
    assert json.loads(Env(sc).run_remediation(wrong, sc.root))["result"] == "no improvement"


def test_trace_records_results():
    env = Env(generate(0))
    env.list_alerts()
    env.get_metrics("db", "mem")
    assert [t["tool"] for t in env.trace] == ["list_alerts", "get_metrics"] and env.trace[1]["result"]


def test_bad_input_returns_error_not_exception():
    env = Env(generate(0))
    assert "error" in json.loads(env.get_metrics("nope", "cpu"))
    assert "error" in json.loads(env.run_remediation("nuke", "db"))
