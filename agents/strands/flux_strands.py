import os
import sys

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.tools.mcp import MCPClient

# The server only needs these. Jobs get a user environment from flux-mcp.
SERVER_ENV = ("FLUX_URI", "PATH", "HOME")

# Core job lifecycle tools.
FLUX_TOOLS = [
    "flux_resource_list",
    "flux_validate_jobspec",
    "flux_count_jobspec_resources",
    "flux_submit_job",
    "flux_submit_jobspec",
    "flux_get_job_info",
    "flux_get_job_logs",
    "flux_cancel_job",
]

SYSTEM_PROMPT = (
    "You operate a Flux Framework instance owned by the user. "
    "Check resources before submitting. After submitting, check job info, "
    "and fetch logs with a delay so a long-running job does not block you."
)


def server_params():
    """Return the parameters to start flux-mcp-stdio from this Python environment."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "flux_mcp.server.stdio"],
        env={name: os.environ[name] for name in SERVER_ENV if name in os.environ},
    )


def flux_client(tools=FLUX_TOOLS):
    """Return a Strands MCP client for the Flux instance in FLUX_URI, limited to tools."""
    params = server_params()
    return MCPClient(lambda: stdio_client(params), tool_filters={"allowed": list(tools)})


def flux_agent(client, model=None):
    """Return a Strands agent using the tools of a started flux_client."""
    return Agent(
        model=model or os.environ.get("STRANDS_MODEL"),
        tools=client.list_tools_sync(),
        system_prompt=SYSTEM_PROMPT,
    )


def main():
    """Run one prompt from the arguments, or an interactive loop, against Flux."""
    client = flux_client()
    with client:
        agent = flux_agent(client)
        if len(sys.argv) > 1:
            agent(" ".join(sys.argv[1:]))
            return
        while True:
            try:
                prompt = input("\nflux> ")
            except EOFError:
                break
            if prompt.strip() in ("exit", "quit"):
                break
            if prompt.strip():
                agent(prompt)


if __name__ == "__main__":
    main()
