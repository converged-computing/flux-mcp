import json

import pytest
import pytest_asyncio
from fastmcp import Client


@pytest_asyncio.fixture
async def client():
    """
    Creates a Client connected to the Flux MCP tools.
    """
    server = "http://localhost:8089/mcp"
    async with Client(server) as c:
        yield c


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
