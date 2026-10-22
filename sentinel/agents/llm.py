"""Claude tool-use agents. `tool_loop` is the shared engine; `llm_agent` is the single-agent baseline."""
import json
from dataclasses import dataclass

from ..config import settings
from ..environment import TOOL_SPECS, Env
from ..simulator import FAULTS

REPORT_SCHEMA = ('{"root_cause_service": str, "fault_type": one of %s, '
                 '"remediation": {"action": str, "service": str}}' % list(FAULTS))

SYSTEM = f"""You are Sentinel, an on-call SRE agent. Investigate the incident with the tools, \
then find the root cause. Principles: symptoms propagate UP the call graph, so the culprit is the \
deepest degraded dependency, not the loudest alert; root services may be silent (no alert, no error \
logs), so inspect dependency metrics and use metric shape (mem ramp = leak, p99 spike = pool/config, \
error step = deploy/cert/disk/cache) and recent changes; ignore decoy healthy deploys. Only after you \
are confident, call run_remediation ONCE, then finish with a JSON object on the last line: {REPORT_SCHEMA}"""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost(self) -> float:
        return (self.input_tokens * settings.price_in + self.output_tokens * settings.price_out) / 1e6


def make_client():
    import anthropic
    if not settings.api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=settings.api_key)


def parse_json_tail(text: str) -> dict:
    """Last valid JSON object in the text (models often add prose around it)."""
    dec, found, i = json.JSONDecoder(), {}, 0
    while (i := text.find("{", i)) != -1:
        try:
            obj, end = dec.raw_decode(text[i:])
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            found = obj
        i += end  # skip nested objects
    return found


def tool_loop(client, system: str, prompt: str, tools: list[dict], dispatch: dict,
              usage: Usage, max_steps: int | None = None) -> str:
    """Run Claude until it stops calling tools; returns the final text."""
    msgs = [{"role": "user", "content": prompt}]
    for _ in range(max_steps or settings.max_steps):
        r = client.messages.create(model=settings.model, max_tokens=1500, system=system,
                                   tools=tools, messages=msgs)
        usage.input_tokens += r.usage.input_tokens
        usage.output_tokens += r.usage.output_tokens
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")
        msgs.append({"role": "assistant", "content": r.content})
        outs = []
        for b in r.content:
            if b.type == "tool_use":
                fn = dispatch.get(b.name)
                outs.append({"type": "tool_result", "tool_use_id": b.id,
                             "content": fn(**b.input) if fn else json.dumps({"error": "unknown tool"})})
        msgs.append({"role": "user", "content": outs})
    return ""


def llm_agent(env: Env, usage: Usage | None = None, client=None) -> dict:
    usage = usage if usage is not None else Usage()
    client = client or make_client()
    dispatch = {t["name"]: getattr(env, t["name"]) for t in TOOL_SPECS}
    text = tool_loop(client, SYSTEM, "PagerDuty: customer-facing errors and latency are elevated. "
                     "Investigate and resolve.", TOOL_SPECS, dispatch, usage)
    return parse_json_tail(text)
