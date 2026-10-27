# Claude Code

Add flux-mcp as the `flux` server for your user. The devcontainer has Claude Code.

```bash
claude mcp add -s user flux -- "$(command -v flux-mcp-stdio)"
```

Outside the devcontainer, install Claude Code first. The installer puts `claude` in `~/.local/bin`, so add that to your `PATH` if needed, and give the full path of the server instead, for example `~/.flux-mcp/bin/flux-mcp-stdio`.

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

## Usage

Start Claude Code inside an allocation. It passes `FLUX_URI` to the server, so the same setup works in every allocation. Run `claude mcp list` to check the connection.

Claude Code asks before it runs a flux tool. You can change that with permission rules such as `mcp__flux__*` in your Claude Code settings.

## VS Code

The Claude Code extension has its own copy of Claude Code, but the `claude mcp add` command above needs the standalone install. The terminal and the chat panel share the same MCP config, so the `flux` server shows up in chat panel conversations you start after that. Type `/mcp` in the chat panel to check it.

The chat panel gets its environment from VS Code, so `FLUX_URI` has to be set there. The devcontainer does that. Without it, start VS Code with `code .` from a shell inside the allocation, or set `FLUX_URI` in the `environmentVariables` setting of the extension and update it for each new allocation.

## Browser

To use Claude Code from a browser, start a Remote Control session inside the allocation. Claude Code and the `flux` server keep running there, and you open the session at claude.ai/code or in the Claude mobile app. Add `--name` to find it in the session list. The devcontainer firewall already allows claude.ai.

```bash
claude remote-control --name flux
```

## Tests

The tests add the server in a temporary home directory and use the Claude Code health check. They do not call a model. They ignore `CLAUDE_CONFIG_DIR`, so they never touch your own Claude Code config.

```bash
flux start --test-size=2 python -m pytest agents/claude
```

They were written against Claude Code 2.1.296. If a newer version fails one of the connection checks, look at the output of `claude mcp list` first.
