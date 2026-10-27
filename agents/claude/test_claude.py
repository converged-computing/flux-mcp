import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = str(Path(sys.executable).parent / "flux-mcp-stdio")


def env_for(home, **extra):
    """Return the environment for running in a temporary HOME."""
    # Claude Code keeps the user config in CLAUDE_CONFIG_DIR when that is set, which
    # would put the flux server into the real config instead of the temporary HOME.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
    return dict(env, HOME=str(home), **extra)


def claude(home, *args, **extra):
    """Run the claude CLI with a temporary HOME."""
    return subprocess.run(
        ["claude", *args], env=env_for(home, **extra), capture_output=True, text=True, timeout=120
    )


def flux_lines(output):
    """Return the lines about the flux server from claude mcp list."""
    return [line for line in output.splitlines() if line.startswith("flux:")]


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    """Return a temporary HOME with flux-mcp added to Claude Code as in the README."""
    path = tmp_path_factory.mktemp("home")
    proc = claude(path, "mcp", "add", "-s", "user", "flux", "--", SERVER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return path


def test_added_for_user(home):
    server = json.loads((home / ".claude.json").read_text())["mcpServers"]["flux"]
    assert server["command"] == SERVER


def test_health_check_connects(home):
    lines = flux_lines(claude(home, "mcp", "list").stdout)
    assert len(lines) == 1 and "Connected" in lines[0], lines


def test_health_check_fails_outside_allocation(home, tmp_path):
    output = claude(home, "mcp", "list", FLUX_URI=f"local://{tmp_path}/missing").stdout
    lines = flux_lines(output)
    assert len(lines) == 1 and "Failed" in lines[0], lines


def test_server_runs_jobs(home):
    server = json.loads((home / ".claude.json").read_text())["mcpServers"]["flux"]

    async def run():
        params = StdioServerParameters(command=server["command"], env=env_for(home))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("flux_submit_job", {"command": ["echo", "hi"]})
                job = json.loads(result.content[0].text)
                result = await session.call_tool("flux_get_job_logs", {"job_id": job["job_id"]})
                return json.loads(result.content[0].text)

    assert asyncio.run(run())["lines"] == ["hi\n"]
