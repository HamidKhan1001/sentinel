"""MCP server exposing a live incident as tools. Point any MCP client (Claude Desktop, Claude Code,
Inspector) at it:  python -m sentinel mcp --seed 7"""
import os

from mcp.server.fastmcp import FastMCP

from ..environment import Env
from ..simulator import generate


def build(seed: int) -> FastMCP:
    env = Env(generate(seed))
    mcp = FastMCP(f"sentinel-incident-{seed}")

    @mcp.tool()
    def list_alerts() -> str:
        """List currently firing alerts."""
        return env.list_alerts()

    @mcp.tool()
    def get_topology() -> str:
        """Service dependency graph (service -> services it calls)."""
        return env.get_topology()

    @mcp.tool()
    def get_metrics(service: str, metric: str, last_minutes: int = 30) -> str:
        """Per-minute metric series. metric is one of error_rate, p99_ms, cpu, mem."""
        return env.get_metrics(service, metric, last_minutes)

    @mcp.tool()
    def search_logs(service: str, query: str = "") -> str:
        """Non-INFO log lines for a service, with optional substring filter."""
        return env.search_logs(service, query)

    @mcp.tool()
    def get_recent_changes() -> str:
        """Recent deploys and config changes across all services."""
        return env.get_recent_changes()

    @mcp.tool()
    def run_remediation(action: str, service: str) -> str:
        """Apply rollback|restart|scale_pool|revert_config|expand_disk|renew_cert. Approval-gated."""
        return env.run_remediation(action, service)

    @mcp.resource("incident://postmortem")
    def postmortem() -> str:
        from ..postmortem import build_postmortem
        return build_postmortem(env, {})

    return mcp


def main(seed: int | None = None):
    build(seed if seed is not None else int(os.getenv("SENTINEL_SEED", "0"))).run()
