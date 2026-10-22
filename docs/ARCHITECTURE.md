# Architecture and design decisions

## 1. Simulator (`sentinel/simulator/engine.py`)
A scenario is a seeded draw of `(fault, root service, silent?, decoy service)`. Each of 7 services gets
60 minutes of per-minute metrics (`error_rate`, `p99_ms`, `cpu`, `mem`) with Gaussian noise. At minute 35 the
fault's signature is added to the root, then propagated up the call graph with a decay of `0.55^depth` and a
delay of `depth` minutes, which is how real symptoms look at the edge of a system.

| Fault | Signature | Canonical fix |
|---|---|---|
| bad_deploy | error step + deploy event | rollback |
| db_pool | p99 + errors, db only | scale_pool |
| memory_leak | `mem` ramp, OOM logs | restart |
| cache_down | error step, `connection refused` | restart |
| bad_config | p99 up + config event | revert_config |
| disk_full | errors, db only | expand_disk |
| cert_expiry | error step, x509 logs | renew_cert |

**Difficulty knobs** (the reason naive logic fails): decoy healthy deploys, harmless WARN noise, alert timestamps
jittered so ordering does not leak the root, and *silent* roots with no alert and no error logs.

## 2. Environment (`sentinel/environment.py`)
One class, six tools. The same methods back the in-process agents, the Anthropic `tool_use` schemas
(`TOOL_SPECS`), and the MCP server, so there is a single source of truth for the tool contract.
Every call is recorded in `env.trace` with its result, which feeds the UI and the postmortem.

**Approval gate.** `run_remediation` models a human approver. Destructive actions (`restart`, `rollback`) on a
service not affected by the incident are refused. "Affected" uses the incident's true causal chain, not alerts,
because a correct diagnosis of a silent root would otherwise be blocked.

## 3. Agents (`sentinel/agents/`)
| Agent | Idea | Failure mode it exposes |
|---|---|---|
| naive | follow first alert | symptoms are not causes |
| rules | deepest alerting service + log regex | silent roots, missing logs |
| graph | anomaly detection on metrics → call-graph root → classify by shape + changes | tuned to the simulator |
| claude | single agent, shared `tool_loop` | needs the reasoning principles in its prompt |
| multi | 3 specialists with restricted tools → commander | coordination overhead vs accuracy |

## 4. Benchmark (`sentinel/bench/`)
Metrics: root-service accuracy, fault-type accuracy, **fixed** (the correct action approved on the correct
service), fixed-on-silent, unsafe actions per incident, tool calls, and token cost. Crashed episodes count as
failures. Results serialise to JSON and an SVG chart for the README.

## 5. Serving
- `server/api.py`: `GET /api/incidents/{seed}`, `POST /api/incidents/{seed}/run?agent=…&reveal=…`.
- `server/static/index.html`: topology heat map, agent trace, verdict vs ground truth, postmortem.
- `server/mcp_server.py`: the six tools plus an `incident://postmortem` resource over stdio.

## 6. Testing strategy
LLM code is tested with a scripted `StubClient` that replays tool-use and final messages, so the tool loop, JSON
parsing, usage accounting, and the multi-agent orchestration are verified in CI with no API key or network.
