import json
import time

import flux
import flux.job
import pytest


async def call(client, tool, arguments):
    """Call a tool and return its JSON result."""
    result = await client.call_tool(tool, arguments)
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_logs_immediately_after_submit(client):
    job = await call(client, "flux_submit_job", {"command": ["bash", "-c", "sleep 1; echo ready"]})
    assert job["success"] is True

    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    assert logs["success"] is True, logs["error"]
    assert logs["complete"] is True
    assert logs["lines"] == ["ready\n"]


@pytest.mark.asyncio
async def test_logs_delay_is_a_time_limit(client):
    job = await call(
        client, "flux_submit_job", {"command": ["bash", "-c", "echo started; sleep 60"]}
    )

    start = time.monotonic()
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"], "delay": 3})
    elapsed = time.monotonic() - start
    await call(client, "flux_cancel_job", {"job_id": job["job_id"]})

    assert logs["success"] is True
    assert logs["complete"] is False
    assert logs["lines"] == ["started\n"]
    assert elapsed < 10


@pytest.mark.asyncio
async def test_logs_fast_job_immediately_after_submit(client):
    job = await call(client, "flux_submit_job", {"command": ["echo", "fast"]})
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    assert logs["lines"] == ["fast\n"]
    assert logs["complete"] is True


@pytest.mark.asyncio
async def test_logs_for_job_that_never_runs(client):
    job = await call(client, "flux_submit_job", {"command": ["true"], "num_tasks": 999})
    logs = await call(client, "flux_get_job_logs", {"job_id": job["job_id"]})
    assert logs["success"] is False
    assert "never started" in logs["error"]
    assert logs["complete"] is True


@pytest.mark.asyncio
async def test_logs_for_held_job_respect_delay(client):
    h = flux.Flux()
    jobid = flux.job.submit(h, flux.job.JobspecV1.from_command(["true"]), urgency=0)

    start = time.monotonic()
    logs = await call(client, "flux_get_job_logs", {"job_id": int(jobid), "delay": 2})
    assert time.monotonic() - start < 10
    assert logs["success"] is True
    assert logs["complete"] is False
    assert logs["lines"] == []

    flux.job.cancel(h, jobid)
    logs = await call(client, "flux_get_job_logs", {"job_id": int(jobid)})
    assert "never started" in logs["error"]


@pytest.mark.asyncio
async def test_logs_for_unknown_job(client):
    logs = await call(client, "flux_get_job_logs", {"job_id": 123456789, "delay": 2})
    assert logs["success"] is False
    assert "not found" in logs["error"]
