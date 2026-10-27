# Agents

Use flux-mcp from an agent with a Flux instance you own. Each directory covers one agent.

- [Claude Code](claude)
- [Codex](codex)
- [Google ADK](adk)
- [AWS Strands](strands)

The agents start `flux-mcp-stdio`, which only connects to the instance in `FLUX_URI` and only if you own it. Jobs get the environment the agent gives them, or a small user environment, and never the environment of the agent.

## Devcontainer

The agents devcontainer in [.devcontainer/agents](../.devcontainer/agents) has Flux, Claude Code, Codex, opencode, Google ADK, AWS Strands, pytest and flux-mcp from this checkout, all in the Python environment on the `PATH`. It starts a Flux instance when the container starts and sets `FLUX_URI` for everything in the container, including the VS Code extensions. It also turns on a firewall that only lets the container reach GitHub, PyPI and the model APIs of the agents, see `init-firewall.sh` there for the list.

To use it, open the repository in VS Code and choose the agents devcontainer when you reopen it in a container. The devcontainer in this directory builds the same image for tools that take a path to a devcontainer.

flux-mcp is an editable install of the checkout, so changes to `flux_mcp` are live. Run `pip install -e .` again after you change `pyproject.toml`.

## Without the devcontainer

Get an allocation and install flux-mcp with the Python that the Flux bindings were built for. flux-mcp needs Python 3.10 or newer. Each agent README says what else to install.

```bash
flux alloc -N2
flux python -m venv ~/.flux-mcp
~/.flux-mcp/bin/pip install flux-mcp
```

## Tests

Each agent has tests that run in CI. The devcontainer has everything they need.

```bash
# in the root of flux-mcp
flux start --test-size=2 python -m pytest agents
```

Outside the devcontainer, they need flux-mcp from this checkout, the extra installs from the agent README, and pytest.

```bash
pip install -e . pytest pytest-timeout
flux start --test-size=2 python -m pytest agents/claude
```
