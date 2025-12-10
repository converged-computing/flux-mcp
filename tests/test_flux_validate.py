import json
import os
import sys

import pytest

import flux_mcp.utils as utils

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
from helpers import load_jobspec


@pytest.mark.asyncio
async def test_tool_list(client):
    tools = await client.list_tools()
    tool_names = [t.name for t in tools]
    assert "flux_validate_jobspec" in tool_names


@pytest.mark.asyncio
async def test_validate_valid_yaml(client, valid_yaml_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_yaml_jobspec})

    data = json.loads(result.content[0].text)

    assert data["valid"] is True
    # Verify exact version from your fixture
    if "jobspec" in data:
        assert data["jobspec"]["version"] == 9999


@pytest.mark.asyncio
async def test_validate_invalid_yaml(client, invalid_yaml_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_yaml_jobspec})

    data = json.loads(result.content[0].text)

    assert data["valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_validate_valid_json(client, valid_json_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_json_jobspec})

    data = json.loads(result.content[0].text)
    assert data["valid"] is True
    if "jobspec" in data:
        assert data["jobspec"]["version"] == 1


@pytest.mark.asyncio
async def test_validate_invalid_json_syntax(client, invalid_json_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_json_jobspec})

    data = json.loads(result.content[0].text)
    print(data)
    assert data["valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_validate_valid_batch(client, valid_batch_script):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_batch_script})

    data = json.loads(result.content[0].text)
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_validate_invalid_batch(client, invalid_batch_script):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_batch_script})

    data = json.loads(result.content[0].text)

    assert data["valid"] is False
    assert any("noodles" in e for e in data["errors"])


@pytest.mark.asyncio
async def test_tool_list(client):
    """Verify our tool is registered and visible."""
    tools = await client.list_tools()
    tool_names = [t.name for t in tools]
    assert "flux_validate_jobspec" in tool_names


@pytest.mark.asyncio
async def test_validate_valid_yaml(client, valid_yaml_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_yaml_jobspec})

    data, jobspec = load_jobspec(result)
    assert data["valid"] is True
    assert jobspec["version"] == 9999


@pytest.mark.asyncio
async def test_validate_invalid_yaml(client, invalid_yaml_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_yaml_jobspec})

    data, _ = load_jobspec(result)
    assert data["valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_validate_valid_json(client, valid_json_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_json_jobspec})

    data, _ = load_jobspec(result)
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_validate_invalid_json(client, invalid_json_jobspec):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_json_jobspec})

    data, _ = load_jobspec(result)
    assert data["valid"] is False
    assert any("pars" in e.lower() or "json" in e.lower() for e in data["errors"])


@pytest.mark.asyncio
async def test_validate_valid_batch(client, valid_batch_script):
    result = await client.call_tool("flux_validate_jobspec", {"content": valid_batch_script})

    data = utils.load_jobspec(result.content[0].text)
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_validate_invalid_batch(client, invalid_batch_script):
    result = await client.call_tool("flux_validate_jobspec", {"content": invalid_batch_script})

    data, jobspec = load_jobspec(result)
    assert data["valid"] is False
    assert any("noodles" in e for e in data["errors"])
