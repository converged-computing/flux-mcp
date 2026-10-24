import json

import flux
import flux.job
import pytest

from flux_mcp.utils import (
    ATTRIBUTES,
    SHELL_OPTION_MIN_VERSION,
    SHELL_OPTIONS,
    default_path,
    flux_version,
    is_settable_property,
    user_environment,
)


def accepts(option):
    """Return True if this Flux can apply a flux_submit_job option."""
    return (
        option in SHELL_OPTIONS
        or option in ATTRIBUTES
        or is_settable_property(flux.job.JobspecV1, option)
    )


async def call(client, tool, arguments):
    """Call a tool and return its JSON result."""
    result = await client.call_tool(tool, arguments)
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_default_environment_is_user_environment(client):
    job = await call(client, "flux_submit_job", {"command": ["env"]})
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    lines = "".join(logs["lines"]).splitlines()
    env = dict(line.split("=", 1) for line in lines if "=" in line)
    expected = user_environment()
    for name in ("HOME", "USER", "LOGNAME", "SHELL"):
        assert env[name] == expected[name]
    assert env["PATH"].startswith(default_path())


@pytest.mark.asyncio
async def test_explicit_environment(client):
    job = await call(
        client, "flux_submit_job", {"command": ["env"], "environment": {"ONLY_THIS": "1"}}
    )
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    text = "".join(logs["lines"])
    assert "ONLY_THIS=1" in text
    assert "HOME=" not in text


@pytest.mark.asyncio
async def test_rlimits_reach_the_job(client):
    job = await call(
        client,
        "flux_submit_job",
        {"command": ["bash", "-c", "ulimit -n"], "rlimits": {"nofile": 512}},
    )
    assert job["success"] is True, job["error"]
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    assert logs["lines"] == ["512\n"]


@pytest.mark.asyncio
async def test_env_expand_reaches_each_task(client):
    job = await call(
        client,
        "flux_submit_job",
        {
            "command": ["bash", "-c", "echo $X"],
            "num_tasks": 2,
            "env_expand": {"X": "r{{task.rank}}"},
        },
    )
    if flux_version(flux.Flux()) < SHELL_OPTION_MIN_VERSION["env-expand"]:
        assert job["success"] is False
        assert "env_expand" in job["error"]
        return
    assert job["success"] is True, job["error"]
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    assert sorted(logs["lines"]) == ["r0\n", "r1\n"]


@pytest.mark.asyncio
async def test_name_reaches_the_job(client):
    job = await call(client, "flux_submit_job", {"command": ["true"], "name": "agent-job"})
    assert job["success"] is True, job["error"]
    await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    info = await call(client, "flux_get_job_info", {"job_id": job["job_id"]})
    assert info["info"]["name"] == "agent-job"


@pytest.mark.asyncio
async def test_bank_reaches_the_jobspec(client):
    job = await call(client, "flux_submit_job", {"command": ["true"], "bank": "agent-bank"})
    assert job["success"] is True, job["error"]
    jobspec = flux.job.kvslookup.job_kvs_lookup(flux.Flux(), job["job_id"], decode=True)["jobspec"]
    assert jobspec["attributes"]["system"]["bank"] == "agent-bank"


@pytest.mark.asyncio
async def test_output_file_written_or_rejected(client, tmp_path):
    path = tmp_path / "out.txt"
    job = await call(
        client, "flux_submit_job", {"command": ["echo", "to-file"], "output": str(path)}
    )
    if not accepts("output"):
        assert job["success"] is False
        assert "output" in job["error"]
        return
    assert job["success"] is True, job["error"]
    flux.job.event_wait(flux.Flux(), job["job_id"], "clean")
    assert path.read_text() == "to-file\n"
