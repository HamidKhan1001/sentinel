from types import SimpleNamespace as NS


class StubClient:
    """Replays scripted Claude responses so the LLM code paths are tested without an API key."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        return self.script.pop(0)


def tool_use(name, **args):
    block = NS(type="tool_use", id=f"t{name}", name=name, input=args)
    return NS(stop_reason="tool_use", content=[block], usage=NS(input_tokens=100, output_tokens=20))


def final(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)], usage=NS(input_tokens=100, output_tokens=20))
