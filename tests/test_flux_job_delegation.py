import json
import os

import flux
import flux.job
import pytest

# The client and valid_json_jobspec fixtures are automatically
# imported from tests/conftest.py


@pytest.mark.asyncio
async def test_delegation_to_local_instance(client, valid_json_jobspec):
    """
    Test the handle_delegation tool by pointing it back to the local FLUX_URI.
    We verify success by using the Flux Python SDK to check if the returned
    Job ID actually exists in the local queue.
    """
    # 1. Get the local Flux URI
    local_uri = os.environ.get("FLUX_URI")
    assert local_uri, "FLUX_URI environment variable must be set to run this test."

    # 3. Call the MCP Tool
    # We assume the tool is registered with the name "handle_delegation"
    result = await client.call_tool(
        "flux_handle_delegation",
        {"remote_uri": local_uri, "jobspec_str": valid_json_jobspec},
    )

    # 4. Parse the result
    # FastMCP wraps the return value in a text block.
    response_text = result.content[0].text
    print(response_text)

    # Handle cases where the tool might return a JSON dict or a raw value
    new_job_id = None
    try:
        # If the tool wraps it like {"job_id": 123}
        data = json.loads(response_text)
        print(data)
        new_job_id = data.get("job_id")
        print(f"\nDelegate Tool returned Job ID: {new_job_id}")
    except json.JSONDecodeError:
        print(f"\nDelegate Tool error serializing json")

    # 5. Verification: Check if job exists in Local Flux Instance
    assert new_job_id > 0, "Tool returned an invalid job ID (failure)"

    # Use the native Flux SDK to look up the job
    f = flux.Flux()
    job_info = flux.job.get_job(f, new_job_id)

    assert job_info is not None
    jobid = job_info["id"]
    jobid = flux.job.JobID(jobid)
    print(jobid)
    print(new_job_id)
    assert jobid == new_job_id

    # It's going to fail not enough resources, but that is OK. It was delegated!
    print(f"✅ Verified: Job {new_job_id} is present in the local Flux queue.")
    print(f"   State: {job_info['state']}")
