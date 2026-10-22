from sentinel.simulator import SERVICES, TOPOLOGY, callers_of, depth_from, generate


def test_deterministic():
    a, b = generate(3), generate(3)
    assert (a.root, a.fault, a.alerts) == (b.root, b.fault, b.alerts)


def test_topology_is_acyclic_and_closed():
    assert all(d in SERVICES for deps in TOPOLOGY.values() for d in deps)
    assert all(depth_from(s, s) == 0 for s in SERVICES)
    assert "gateway" in callers_of("auth")


def test_loud_incidents_alert_at_root():
    for sd in range(40):
        sc = generate(sd, silent=False)
        assert sc.root in {a["service"] for a in sc.alerts}, sd


def test_silent_root_does_not_alert():
    for sd in range(40):
        assert generate(sd, silent=True).root not in {a["service"] for a in generate(sd, silent=True).alerts}


def test_every_fault_type_is_generated():
    assert len({generate(sd).fault for sd in range(100)}) == 7
