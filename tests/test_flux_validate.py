import ast
import json

import pytest
import pytest_asyncio
from fastmcp import Client

import flux_mcp.utils as utils


@pytest.fixture
def valid_yaml_jobspec():
    """
    This is a valid canonical jobspec.
    """
    return """
version: 9999
resources:
  - type: node
    count: 1
    with:
      - type: memory
        count: 256
      - type: socket
        count: 2
        with:
          - type: gpu
            count: 4
          - type: slot
            count: 2
            label: default
            with:
              - type: L3cache
                count: 1
                with:
                  - type: core
                    count: 4
                    with:
                      - type: pu
                        count: 1

# a comment
attributes:
  system:
    duration: "3600"
tasks:
  - command: [ "app" ]
    slot: default
    count:
      per_slot: 1
    """


@pytest.fixture
def invalid_yaml_jobspec():
    return """
version: 9999
resources:
    - type: node
      count: 1
      with:
        - type: memory
          count: 256
        - type: socket
          count: 2
          with:
            - type: gpu
              count: 4
            - type: slot
              count: 2
              with:
                - type: L3cache
                  count: 1
                  with:
                    - type: core
                      count: 4
                      with:
                        - type: pu
                          count: 1

# a comment
attributes:
  system:
    duration: 3600
tasks:
  - command: [ "app" ]
    slot: default
    count:
      per_slot: 1
    """


@pytest.fixture
def valid_json_jobspec():
    return json.dumps(
        {
            "resources": [
                {
                    "type": "slot",
                    "count": 1,
                    "label": "default",
                    "with": [
                        {
                            "type": "node",
                            "count": 1,
                            "exclusive": True,
                            "with": [
                                {
                                    "type": "slot",
                                    "count": 1,
                                    "with": [{"type": "core", "count": 1}],
                                    "label": "task",
                                }
                            ],
                        },
                        {"type": "ssd", "count": 20480, "exclusive": True},
                    ],
                }
            ],
            "tasks": [{"command": ["hostname"], "slot": "task", "count": {"per_slot": 1}}],
            "attributes": {"system": {"duration": 0, "environment": {}, "shell": {}}},
            "version": 1,
        }
    )


@pytest.fixture
def invalid_json_jobspec():
    # Invalid: Malformed JSON syntax (missing closing brace)
    return '{"version": 1, "resources": {"cpu": 1}'


# ------------------------------------------------------------------
# Batch File Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def valid_batch_script():
    return """#!/bin/bash
#FLUX: -N 2
#FLUX: -n 8
#FLUX: --output=job.out
echo "Running standard job"
"""


@pytest.fixture
def invalid_batch_script():
    return """#!/bin/bash
#FLUX: -N2
#FLUX: --noodles=2
hostname
"""


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


@pytest_asyncio.fixture
async def client():
    """
    Creates a Client connected to the Flux MCP tools.
    """
    server = "http://localhost:8089/mcp"
    async with Client(server) as c:
        yield c


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


def load_jobspec(result):
    # The tool returns a JSON string, so we parse it
    data = json.loads(result.content[0].text)
    jobspec = data.get("jobspec")
    if isinstance(jobspec, str):
        try:
            jobspec = json.loads(jobspec)
        except json.JSONDecodeError:
            jobspec = ast.literal_eval(jobspec)

    return data, jobspec


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
