import asyncio
import json

import flux
import flux.job
import pytest
import yaml


@pytest.fixture
def simple_jobspec_dict():
    """
    Base dictionary for a simple 1 node, 1 core job.
    Structure: Node (1) -> Slot (1) [Labeled 'task'] -> Core (1)
    """
    return {
        "version": 1,
        "resources": [
            {
                "type": "node",
                "count": 1,
                "with": [
                    {
                        "type": "slot",
                        "count": 1,
                        "label": "task",
                        "with": [{"type": "core", "count": 1}],
                    }
                ],
            }
        ],
        "tasks": [{"command": ["/bin/true"], "slot": "task", "count": {"per_slot": 1}}],
        "attributes": {"system": {"duration": 0}},
    }


@pytest.fixture
def simple_json_jobspec(simple_jobspec_dict):
    return json.dumps(simple_jobspec_dict)


@pytest.fixture
def simple_yaml_jobspec(simple_jobspec_dict):
    return yaml.dump(simple_jobspec_dict)


@pytest.mark.asyncio
async def test_submit_sync_json(client, simple_json_jobspec):
    """
    Test 1: Synchronous submission using JSON.
    """
    result = await client.call_tool(
        "flux_submit_job", {"jobspec": simple_json_jobspec, "submit_async": False}
    )

    data = json.loads(result.content[0].text)
    print(f"\nSync Submit Result: {data}")

    assert data["success"] is True
    assert "job_id" in data
    job_id = data["job_id"]
    assert isinstance(job_id, int)


@pytest.mark.asyncio
async def test_submit_async_json(client, simple_json_jobspec):
    """
    Test 2: Asynchronous submission using JSON.
    """
    result = await client.call_tool(
        "flux_submit_job", {"jobspec": simple_json_jobspec, "submit_async": True}
    )

    data = json.loads(result.content[0].text)
    print(f"\nAsync Submit Result: {data}")
    assert data["success"] is True


@pytest.mark.asyncio
async def test_submit_yaml(client, simple_yaml_jobspec):
    """
    Test 3: Submission using YAML.
    NOTE: This will fail if the server tool does not implement yaml.safe_load.
    """
    result = await client.call_tool(
        "flux_submit_job", {"jobspec": simple_yaml_jobspec, "submit_async": False}
    )

    data = json.loads(result.content[0].text)
    print(f"\nYAML Submit Result: {data}")

    # If tool supports YAML, this should be True.
    # If not, this asserts failure to highlight missing feature.
    if data["success"] is False:
        assert "Jobspec must be valid JSON" in data["error"] or "JSON" in data["error"]
        pytest.xfail("Tool implementation does not support YAML yet.")

    assert data["success"] is True


@pytest.mark.asyncio
async def test_submit_and_get_info_workflow(client, simple_json_jobspec):
    """
    Integration Test:
    1. Call 'flux_submit_job' to create a job.
    2. Extract the returned Job ID.
    3. Call 'flux_get_job_info' with that ID.
    4. Verify the info matches the submitted job.
    """
    print("\n[Step 1] Submitting Job...")

    # 1. Submit
    submit_result = await client.call_tool(
        "flux_submit_job", {"jobspec": simple_json_jobspec, "submit_async": False}
    )

    submit_data = json.loads(submit_result.content[0].text)

    # Fail fast if submit didn't work
    assert submit_data["success"] is True, f"Submit failed: {submit_data.get('error')}"

    job_id = submit_data["job_id"]
    print(f" -> Job Submitted successfully. ID: {job_id}")
    print(f"[Step 2] Fetching Info for Job {job_id}...")

    # This should first be running
    info_result = await client.call_tool("flux_get_job_info", {"job_id": job_id})

    info_data = json.loads(info_result.content[0].text)
    print(f" -> Info Received: {info_data}")

    # Check if the tool returned an error object
    if "success" in info_data and info_data["success"] is False:
        pytest.fail(f"flux_get_job_info failed: {info_data.get('error')}")
    fetched_id = info_data.get("id")

    assert fetched_id is not None, "Response from get_job_info did not contain an 'id' field"
    assert int(fetched_id) == int(
        job_id
    ), f"ID Mismatch! Submitted {job_id}, got info for {fetched_id}"
    if "state" in info_data:
        print(f" -> Job State: {info_data['state']}")
        assert info_data["state"] in ["PRIORITY", "SCHED", "RUN", "INACTIVE", "CLEANUP"]


@pytest.mark.asyncio
async def test_submit_cancel_workflow(client):
    """
    Integration Test:
    1. Submit a long-running 'sleep' job.
    2. Verify it is active via 'flux_get_job_info'.
    3. Cancel the job via 'flux_cancel_job'.
    4. Verify it transitions to an inactive/cancelled state.
    """
    print("\n[Step 1] Submitting Sleep Job...")

    # 1. Define a sleep job (runs for 60s so it doesn't finish immediately)
    sleep_jobspec = {
        "version": 1,
        "resources": [
            {
                "type": "node",
                "count": 1,
                "with": [
                    {
                        "type": "slot",
                        "count": 1,
                        "label": "default",
                        "with": [{"type": "core", "count": 1}],
                    }
                ],
            }
        ],
        "tasks": [{"command": ["sleep", "60"], "slot": "default", "count": {"per_slot": 1}}],
        "attributes": {"system": {"duration": 0}},
    }

    # Submit
    submit_result = await client.call_tool(
        "flux_submit_job", {"jobspec": json.dumps(sleep_jobspec), "submit_async": True}
    )
    submit_data = json.loads(submit_result.content[0].text)
    assert submit_data["success"] is True
    job_id = submit_data["job_id"]
    print(f" -> Job {job_id} submitted.")

    # 2. Verify it is Active (PRIORITY, SCHED, or RUN)
    print(f"[Step 2] Verifying Job {job_id} is active...")
    info_result = await client.call_tool("flux_get_job_info", {"job_id": job_id})
    info_data = json.loads(info_result.content[0].text)

    # Active states in Flux
    active_states = ["PRIORITY", "SCHED", "RUN"]
    assert (
        info_data["state"] in active_states
    ), f"Job should be active, but state is {info_data.get('state')}"

    # 3. Cancel the Job
    print(f"[Step 3] Cancelling Job {job_id}...")
    cancel_result = await client.call_tool("flux_cancel_job", {"job_id": job_id})
    cancel_data = json.loads(cancel_result.content[0].text)

    assert cancel_data["success"] is True
    print(f" -> Cancel requested: {cancel_data['message']}")

    # 4. Verify Status is Cancelled
    # Cancellation is async; we poll briefly for the state change.
    print(f"[Step 4] Verifying state transition to INACTIVE/Cancelled...")

    final_state = None
    for _ in range(5):  # Try for up to 5 seconds
        await asyncio.sleep(1.0)

        check_result = await client.call_tool("flux_get_job_info", {"job_id": job_id})
        check_data = json.loads(check_result.content[0].text)
        final_state = check_data["state"]

        # Flux jobs transition to INACTIVE when cancelled (or finished)
        if final_state == "INACTIVE":
            # Optional: If your tool returns exception info, check it.
            if "exception" in check_data:
                print(f" -> Job Exception: {check_data['exception']}")
            break

    assert (
        final_state == "INACTIVE"
    ), f"Job failed to transition to INACTIVE. Stuck in {final_state}"
    print(" -> Job successfully transitioned to INACTIVE.")
