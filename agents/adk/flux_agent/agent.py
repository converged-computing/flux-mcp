import os
import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

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
]

# Tools that ask the user for confirmation before running.
CONFIRM_TOOLS = ["flux_cancel_job"]

INSTRUCTION = (
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


def flux_toolset(tools=None, require_confirmation=False, timeout=30):
    """Return an ADK toolset for the Flux instance in FLUX_URI, limited to tools if given."""
    return McpToolset(
        connection_params=StdioConnectionParams(server_params=server_params(), timeout=timeout),
        tool_filter=tools,
        require_confirmation=require_confirmation,
    )


root_agent = LlmAgent(
    name="flux_agent",
    model=os.environ.get("ADK_MODEL", LlmAgent.DEFAULT_MODEL),
    instruction=INSTRUCTION,
    tools=[flux_toolset(FLUX_TOOLS), flux_toolset(CONFIRM_TOOLS, require_confirmation=True)],
)
