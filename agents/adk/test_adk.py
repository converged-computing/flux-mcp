import asyncio
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from google.adk.agents import LlmAgent

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import flux_agent.agent as agent  # noqa: E402


def with_tools(toolset, fn):
    """Run fn with the tools of the toolset by name, then close the toolset."""

    async def run():
        try:
            return await fn({tool.name: tool for tool in await toolset.get_tools()})
        finally:
            await toolset.close()

    return asyncio.run(run())


async def call(tool, **args):
    """Run an ADK MCP tool and return its JSON result."""
    result = await tool.run_async(args=args, tool_context=None)
    return json.loads(result["content"][0]["text"])


async def names(tools):
    """Return the sorted tool names."""
    return sorted(tools)


def test_server_gets_only_server_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "secret")
    monkeypatch.setenv("MY_MODULE_VAR", "1")
    env = agent.server_params().env
    assert set(env) <= set(agent.SERVER_ENV)
    assert env["FLUX_URI"] == os.environ["FLUX_URI"]


def test_toolsets():
    assert with_tools(agent.flux_toolset(agent.FLUX_TOOLS), names) == sorted(agent.FLUX_TOOLS)
    confirm = agent.flux_toolset(agent.CONFIRM_TOOLS, require_confirmation=True)
    assert confirm.require_confirmation is True
    assert with_tools(confirm, names) == agent.CONFIRM_TOOLS


def test_submit_logs_info():
    async def run(tools):
        job = await call(tools["flux_submit_job"], command=["echo", "from-adk"], num_tasks=2)
        logs = await call(tools["flux_get_job_logs"], job_id=job["job_id"])
        info = await call(tools["flux_get_job_info"], job_id=job["job_id"])
        return job, logs, info

    job, logs, info = with_tools(agent.flux_toolset(agent.FLUX_TOOLS), run)
    assert job["success"], job["error"]
    assert logs["lines"] == ["from-adk\n", "from-adk\n"]
    assert info["info"]["status"] == "COMPLETED"


def test_jobs_get_user_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "secret")

    async def run(tools):
        job = await call(tools["flux_submit_job"], command=["env"])
        return await call(tools["flux_get_job_logs"], job_id=job["job_id"])

    lines = "".join(with_tools(agent.flux_toolset(agent.FLUX_TOOLS), run)["lines"]).splitlines()
    env = {line.split("=", 1)[0] for line in lines if "=" in line}
    assert {"HOME", "USER", "PATH"} <= env
    assert "GOOGLE_API_KEY" not in env


def test_root_agent_and_model(monkeypatch):
    root = agent.root_agent
    assert [toolset.tool_filter for toolset in root.tools] == [
        agent.FLUX_TOOLS,
        agent.CONFIRM_TOOLS,
    ]
    assert [toolset.require_confirmation for toolset in root.tools] == [False, True]
    monkeypatch.delenv("ADK_MODEL", raising=False)
    assert importlib.reload(agent).root_agent.model == LlmAgent.DEFAULT_MODEL
    monkeypatch.setenv("ADK_MODEL", "gemini-test-model")
    assert importlib.reload(agent).root_agent.model == "gemini-test-model"


def test_adk_run_loads_the_agent():
    adk = str(Path(sys.executable).parent / "adk")
    proc = subprocess.run(
        [adk, "run", str(HERE / "flux_agent")],
        input="exit\n",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "Running agent flux_agent" in proc.stdout, proc.stdout + proc.stderr
