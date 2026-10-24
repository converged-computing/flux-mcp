import asyncio
import json
import os
import subprocess
import sys
import time

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import flux_mcp.server.stdio as stdio

COMMAND = [sys.executable, "-m", "flux_mcp.server.stdio"]


def run_stdio(env):
    """Run the stdio entrypoint with closed stdin and return the completed process."""
    return subprocess.run(
        COMMAND, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60
    )


def session(env, fn):
    """Run fn(session) in an MCP stdio session with the stdio entrypoint."""

    async def main():
        params = StdioServerParameters(command=COMMAND[0], args=COMMAND[1:], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                return await fn(s)

    return asyncio.run(main())


def job_environment(env):
    """Return the variable names a job submitted through the entrypoint sees."""

    async def run(s):
        result = await s.call_tool("flux_submit_job", {"command": ["env"]})
        job = json.loads(result.content[0].text)
        result = await s.call_tool("flux_get_job_logs", {"job_id": job["job_id"]})
        return json.loads(result.content[0].text)["lines"]

    lines = "".join(session(env, run)).splitlines()
    return {line.split("=", 1)[0] for line in lines if "=" in line}


@pytest.fixture
def shadowed_flux(tmp_path):
    """Return a PYTHONPATH entry whose flux package fails to import."""
    package = tmp_path / "flux"
    package.mkdir()
    (package / "__init__.py").write_text("raise ImportError('shadowed for test')\n")
    return str(tmp_path)


def test_refuses_without_flux_uri():
    proc = run_stdio({k: v for k, v in os.environ.items() if k != "FLUX_URI"})
    assert proc.returncode == 1
    assert "FLUX_URI not set" in proc.stderr


def test_refuses_unreachable_uri(tmp_path):
    proc = run_stdio(dict(os.environ, FLUX_URI=f"local://{tmp_path}/missing"))
    assert proc.returncode == 1
    assert "cannot reach Flux" in proc.stderr


def test_refuses_instance_owned_by_someone_else(monkeypatch, capsys):
    other = os.getuid() + 1
    monkeypatch.setattr(stdio.os, "getuid", lambda: other)
    with pytest.raises(SystemExit) as exit:
        stdio.check_instance()
    assert exit.value.code == 1
    assert "is owned by uid" in capsys.readouterr().err


def test_accepts_own_instance():
    stdio.check_instance()


def test_reexecs_under_flux_env(shadowed_flux):
    env = dict(os.environ, PYTHONPATH=shadowed_flux)

    async def tools(s):
        return {t.name for t in (await s.list_tools()).tools}

    assert "flux_submit_job" in session(env, tools)


def test_does_not_reexec_twice(shadowed_flux):
    env = dict(os.environ, PYTHONPATH=shadowed_flux, **{stdio.REEXEC: "1"})
    proc = run_stdio(env)
    assert proc.returncode == 1
    assert "even under 'flux env'" in proc.stderr


def test_refuses_without_flux_on_path(shadowed_flux):
    env = dict(os.environ, PYTHONPATH=shadowed_flux, PATH="/nonexistent")
    proc = run_stdio(env)
    assert proc.returncode == 1
    assert "flux not on PATH" in proc.stderr


def test_scrub_removes_default_credentials(monkeypatch):
    monkeypatch.delenv("FLUX_MCP_UNSET", raising=False)
    for name in stdio.DEFAULT_UNSET:
        monkeypatch.setenv(name, "secret")
    monkeypatch.setenv("KEEP_ME", "1")
    stdio.scrub_environment()
    assert not set(stdio.DEFAULT_UNSET) & set(os.environ)
    assert os.environ["KEEP_ME"] == "1"


def test_scrub_list_can_be_replaced(monkeypatch):
    monkeypatch.setenv("FLUX_MCP_UNSET", "KEEP_ME")
    monkeypatch.setenv("KEEP_ME", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    stdio.scrub_environment()
    assert "KEEP_ME" not in os.environ
    assert os.environ["ANTHROPIC_API_KEY"] == "secret"


def test_jobs_inherit_environment_without_credentials():
    env = dict(os.environ, MY_MODULE_VAR="1", ANTHROPIC_API_KEY="x", AWS_SECRET_ACCESS_KEY="y")
    names = job_environment(env)
    assert {"MY_MODULE_VAR", "PATH"} <= names
    assert not names & {"ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", stdio.REEXEC}


def test_jobs_without_credentials_after_reexec(shadowed_flux):
    env = dict(os.environ, PYTHONPATH=shadowed_flux, OPENAI_API_KEY="x")
    names = job_environment(env)
    assert not names & {"OPENAI_API_KEY", stdio.REEXEC}


def test_parallel_calls_do_not_block():
    async def run(s):
        result = await s.call_tool("flux_submit_job", {"command": ["sleep", "5"]})
        job_id = json.loads(result.content[0].text)["job_id"]

        async def quick_call():
            await asyncio.sleep(1)
            start = time.monotonic()
            await s.call_tool("flux_resource_list", {})
            return time.monotonic() - start

        logs = s.call_tool("flux_get_job_logs", {"job_id": job_id})
        _, waited = await asyncio.gather(logs, quick_call())
        return waited

    assert session(dict(os.environ), run) < 2
