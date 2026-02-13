import asyncio
import json

import pytest
import yaml
from fastmcp.exceptions import ToolError


@pytest.fixture
def valid_spec_dict():
    """A minimal jobspec that matches your 8-core single-node environment."""
    return {
        "version": 1,
        "resources": [
            {"label": "default", "type": "slot", "count": 1, "with": [{"type": "core", "count": 1}]}
        ],
        "tasks": [{"command": ["hostname"], "slot": "task", "count": {"per_slot": 1}}],
        "attributes": {"system": {"duration": 0}},
    }


@pytest.fixture
def yaml_spec(valid_spec_dict):
    return yaml.dump(valid_spec_dict)


@pytest.mark.asyncio
async def test_flux_resource_list(client):
    """Verifies inventory tool (flux_ prefix) sees your 1-node/8-core setup."""
    result = await client.call_tool("flux_resource_list", {})
    data = json.loads(result.content[0].text)
    assert data["free"]["nodes"] == 1
    assert data["free"]["cores"] == 8
    print(f"\nInventory Verified: {data['free']['cores']} cores free.")


@pytest.mark.asyncio
async def test_flux_sched_qmanager_stats(client):
    """Verifies queue manager status tool."""
    result = await client.call_tool("flux_sched_qmanager_stats", {})
    data = json.loads(result.content[0].text)
    assert isinstance(data, dict)
    print(f"Queue Stats Verified: {list(data.keys())}")


@pytest.mark.asyncio
async def test_flux_sched_resource_params(client):
    """Verifies scheduler module parameters."""
    result = await client.call_tool("flux_sched_resource_params", {})
    data = json.loads(result.content[0].text)
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_flux_sched_allocation_lifecycle(client, yaml_spec):
    """
    Tests:
    1. flux_sched_resource_allocate (Accepts YAML String)
    2. flux_sched_resource_status
    3. flux_sched_resource_cancel
    """
    # 1. Allocate
    result = await client.call_tool("flux_sched_resource_allocate", {"jobspec": yaml_spec})
    data = json.loads(result.content[0].text)
    assert "jobid" in data
    jobid = data["jobid"]

    # 2. Check Status
    status_result = await client.call_tool("flux_sched_resource_status", {})
    assert status_result is not None

    # 3. Cancel
    cancel_result = await client.call_tool("flux_sched_resource_cancel", {"jobid": jobid})
    assert cancel_result is not None
    print(f"Allocation Lifecycle Verified for JobID: {jobid}")


@pytest.mark.asyncio
async def test_flux_sched_reserve_variant(client, yaml_spec):
    """Tests: flux_sched_resource_allocate_orelse_reserve"""
    try:
        result = await client.call_tool(
            "flux_sched_resource_allocate_orelse_reserve", {"jobspec": yaml_spec}
        )
        data = json.loads(result.content[0].text)
        assert "jobid" in data
        # Immediate cleanup
        await client.call_tool("flux_sched_resource_cancel", {"jobid": data["jobid"]})
    except ToolError as e:
        if "Invalid argument" in str(e):
            pytest.xfail(
                "Scheduler returned Errno 22 - check if orelse_reserve command is supported in this fluxion version."
            )
        else:
            raise e


@pytest.mark.asyncio
async def test_flux_sched_resource_stats(client):
    """Tests: flux_sched_resource_stats (V and E counts)"""
    result = await client.call_tool("flux_sched_resource_stats", {})
    data = json.loads(result.content[0].text)
    assert "V" in data
    assert "E" in data
