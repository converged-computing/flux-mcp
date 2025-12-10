import json

import pytest


@pytest.mark.asyncio
async def test_count_resources_canonical(client, valid_yaml_jobspec):
    """
    Tests that the hierarchical resources are flattened and counted correctly.
    e.g. 1 Node * 2 Sockets * 4 GPUs = 8 GPUs
    """
    # 1. Call the tool
    result = await client.call_tool("flux_count_jobspec_resources", {"content": valid_yaml_jobspec})

    # 2. Parse the result
    # FastMCP converts the dictionary return value to a JSON string in the text content
    counts = json.loads(result.content[0].text)
    print(counts)

    # 3. Assertions based on your specific requirements
    expected_counts = {
        "node": 1,
        "memory": 256,
        "socket": 2,  # 1 node * 2 sockets
        "gpu": 8,  # 1 node * 2 sockets * 4 GPUs
        "slot": 4,  # 1 node * 2 sockets * 2 slots
        "L3cache": 4,  # ... matches slots
        "core": 16,  # 4 L3 * 4 cores
        "pu": 16,  # 16 cores * 1 pu
    }

    print(f"\nReceived Counts: {counts}")

    for resource_type, expected_val in expected_counts.items():
        assert (
            counts.get(resource_type) == expected_val
        ), f"Mismatch for {resource_type}: expected {expected_val}, got {counts.get(resource_type)}"


@pytest.mark.asyncio
async def test_count_resources_invalid_input(client, invalid_yaml_jobspec):
    """
    Ensure it returns an empty dict (or handles it gracefully) when jobspec is invalid.
    """
    result = await client.call_tool(
        "flux_count_jobspec_resources", {"content": invalid_yaml_jobspec}
    )

    counts = json.loads(result.content[0].text)

    # Based on your provided code: "if not result['valid']: return {}"
    assert counts == {}
