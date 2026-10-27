# AWS Strands

A Strands agent for the Flux instance in `FLUX_URI`. The devcontainer has Strands in the same environment as flux-mcp, so `python` below is on the `PATH` there. Outside the devcontainer, make that environment with `flux python` so it matches the Flux bindings.

```bash
flux python -m venv ~/.flux-strands
~/.flux-strands/bin/pip install flux-mcp "strands-agents>=1.60"
```

## Usage

Set up model access as you would for any Strands agent. By default that is Amazon Bedrock with your AWS credentials, and `STRANDS_MODEL` picks a different Bedrock model. Run the agent inside an allocation with one prompt, or on its own to chat.

```bash
export STRANDS_MODEL=us.anthropic.claude-sonnet-4-6
export AWS_DEFAULT_REGION=us-east-1
~/.flux-strands/bin/python agents/strands/flux_strands.py "how many nodes are free?"
~/.flux-strands/bin/python agents/strands/flux_strands.py
```

The agent starts the flux-mcp server itself and gives it only `FLUX_URI`, `PATH` and `HOME`. It can list resources, check and count jobspecs, submit and cancel jobs, and read their info and logs. To build your own agent, use `flux_client` and `flux_agent` from `flux_strands.py`.

## Tests

The tests call the tools through Strands and do not need a model.

```bash
flux start --test-size=2 ~/.flux-strands/bin/python -m pytest agents/strands
```
