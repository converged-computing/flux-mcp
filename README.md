# flux-mcp

> 🌀 Agentic MCP tools for Flux Framework

[![PyPI version](https://badge.fury.io/py/flux-mcp.svg)](https://badge.fury.io/py/flux-mcp)

![img/flux-mcp-small.png](img/flux-mcp-small.png)

## Related Projects

- [fractale-mcp](https://github.com/compspec/fractale-mcp): (fractale) MCP orchestration (agents, databases, ui interfaces).
- [hpc-mcp](https://github.com/converged-computing/hpc-mcp): HPC tools for a larger set of HPC and converged computing use cases.

## Usage

These Flux MCP tools can be used via a standalone server, or combined with other tools.
Note that along with flux-python (comes packaged with Flux, or `pip install flux-python==<version>` you
can optionally install `flux-sched-py` for flux-sched functionality.

### Server

We provide examples for fastmcp and a vanilla mcp (stdio) setup. Neither requirements are added to the install directly, so it's up to the user (you) to install. Tests are performed with fastmcp.

#### fastmcp

You will need fastapi and fastmcp installed.

```bash
# fastmcp
pip install fastmcp fastapi
```

To install in the Development environment:

```bash
```

To start the demo server:

```bash
# Vanilla MCP (with cli)
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}' | python3 -m flux_mcp.server | jq

# Initialize and list tools
(echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "manual-test", "version": "1.0"}}}';
 echo '{"jsonrpc": "2.0", "method": "notifications/initialized"}';
 echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}') | python3 -m flux_mcp.server | jq

# FastMCP
python3 -m flux_mcp.server.fastmcp
```

### Testing

I will add tools to git as I write tests for them. To test, start the fastmcp server in one terminal:

```bash
python3 -m flux_mcp.server.fastmcp
```

To test flux-sched, ensure `libreapi_cli.so` is on the `LD_LIBRARY_PATH` of the server:

```bash
export LD_LIBRARY_PATH=/usr/lib/flux/
python3 -m flux_mcp.server.fastmcp
```

In another terminal, run the test. You'll need to `pip install pytest pytest-asyncio`

```bash
pytest -xs tests/test_flux_validate.py
pytest -xs tests/test_flux_counts.py
pytest -xs tests/test_flux_job_delegation.py
pytest -xs tests/test_flux_job_core.py
pytest -xs tests/test_transformers.py

# Requires libreapi_cli.so
pytest -xs tests/test_flux_sched.py

# or
pytest -xs tests/test_*.py
```

### Tools

Tools to add:

 - flux
   - flux-sched
     - [ ] grow
     - [ ] shrink
     - [x] create resource graph
     - [x] match allocate
     - [x] cancel
     - [x] partial-cancel
     - [ ] satisfy
   - flux-core
     - [x] submit jobs
     - [x] job info
     - [x] cancel job
     - [x] validator
       - [x] counter
       - [x] batch jobs
       - [x] canonical jobspec
       - [x] json jobspec
   - [ ] topology?
   - delegation
    - [x] local flux URI
    - [x] translation (the transformers?)

## TODO

- Add annotated descriptions to all functions for LLM.

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
