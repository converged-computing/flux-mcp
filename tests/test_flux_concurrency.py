import asyncio
import json
import time

import pytest
from fastmcp import Client

SERVER = "http://localhost:8089/mcp"


@pytest.mark.asyncio
async def test_blocking_call_does_not_stall_other_clients(client):
    result = await client.call_tool("flux_submit_job", {"command": ["sleep", "5"]})
    job_id = json.loads(result.content[0].text)["job_id"]

    async def wait_for_logs():
        await client.call_tool("flux_get_job_logs", {"job_id": job_id})

    async def quick_call():
        await asyncio.sleep(1)
        # Time the connection too, since a stalled server also stalls the handshake.
        start = time.monotonic()
        async with Client(SERVER) as other:
            await other.call_tool("flux_resource_list", {})
        return time.monotonic() - start

    _, waited = await asyncio.gather(wait_for_logs(), quick_call())
    assert waited < 2
