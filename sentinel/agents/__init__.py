from .baselines import naive_agent, rules_agent
from .graph import graph_agent
from .llm import Usage, llm_agent
from .multi import multi_agent

# name -> (callable, needs_llm)
AGENTS = {
    "naive": (naive_agent, False),
    "rules": (rules_agent, False),
    "graph": (graph_agent, False),
    "claude": (llm_agent, True),
    "multi": (multi_agent, True),
}

__all__ = ["AGENTS", "Usage", "naive_agent", "rules_agent", "graph_agent", "llm_agent", "multi_agent"]
