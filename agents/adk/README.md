# Google ADK

An ADK agent for the Flux instance in `FLUX_URI`. The devcontainer has ADK in the same environment as flux-mcp, so `adk` and `python` below are on the `PATH` there. Outside the devcontainer, make that environment with `flux python` so it matches the Flux bindings.

```bash
flux python -m venv ~/.flux-adk
~/.flux-adk/bin/pip install flux-mcp "google-adk>=2.12"
```

## Usage

Set up a model as you would for any ADK agent, for example with `GOOGLE_API_KEY` for Gemini. Then run the agent inside an allocation. Set `ADK_MODEL` to use a different model.

```bash
~/.flux-adk/bin/adk run agents/adk/flux_agent
```

To use the ADK web UI instead, give it the directory that holds the agent. Then open http://localhost:8000 and pick `flux_agent`. Add `--port` to use a different port.

```bash
~/.flux-adk/bin/adk web agents/adk
```

The agent starts the flux-mcp server itself and gives it only `FLUX_URI`, `PATH` and `HOME`. It can list resources, check and count jobspecs, submit jobs, and read their info and logs. It can also cancel jobs, and ADK asks you first. To build your own agent, use `flux_toolset` from `flux_agent/agent.py`.

## Tests

The tests call the tools through ADK and do not need a model.

```bash
flux start --test-size=2 ~/.flux-adk/bin/python -m pytest agents/adk
```
