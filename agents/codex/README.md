# Codex

The devcontainer has Codex. Outside it, install Node 22 or newer and Codex.

```bash
npm install -g @openai/codex
```

Add flux-mcp to `~/.codex/config.toml` as the `flux` server. Use the full path that `command -v flux-mcp-stdio` prints. The `env_vars` line makes Codex pass `FLUX_URI` to the server. `codex mcp add` has no option for it, only `--env` for fixed values.

```toml
[mcp_servers.flux]
command = "/opt/flux-mcp/bin/flux-mcp-stdio"
env_vars = ["FLUX_URI"]
```

## Usage

Start Codex inside an allocation. The same config works in every allocation. Run `codex mcp get flux` to see the server.

## VS Code

The Codex extension for VS Code, Cursor and Windsurf is `openai.chatgpt`. It reads the same `~/.codex/config.toml` as the CLI, so the `flux` server shows up in the chat panel once you add it above. In a remote window such as the devcontainer or Remote-SSH, the extension runs on the remote side, so install it there and use the config in that home directory. The devcontainer does not install it. The settings menu in the Codex panel has MCP settings to check the server.

The chat panel gets its environment from VS Code, so `FLUX_URI` has to be set there. The devcontainer does that. Without it, start VS Code with `code .` from a shell inside the allocation, or put the URI of the allocation in the config and update it for each new allocation. The `env` table wins over `env_vars`, so remove it to go back to taking `FLUX_URI` from the environment.

```toml
[mcp_servers.flux.env]
FLUX_URI = "local:///tmp/flux-abc123/local"
```

## Desktop app

The ChatGPT desktop app for macOS and Windows has Codex, but it runs Codex on your computer, which is not inside your allocation. Use a remote connection instead. In the app, open Settings > Connections and add an SSH host from your `~/.ssh/config`. The app starts Codex on that host through your login shell, so `codex` has to be on the `PATH` there and signed in, and the `flux` server runs on that host with the config in that home directory. Make the host entry reach a node of your allocation, with `ProxyJump` through the login node if needed, since the server has to run where it can open the instance socket. A login shell has no `FLUX_URI`, so set it in the config as in the VS Code section.

## Phone and other computers

To use Codex from the ChatGPT app on a phone, or from the desktop app on another computer, start remote control inside the allocation. Codex and the `flux` server keep running there with the `FLUX_URI` of the allocation. Codex has to be signed in with ChatGPT first. On a node without a browser, use `codex login --device-auth`. Pairing is not available until the sign-in completes. Then enter the code that `pair` prints under Remote in the mobile app, or under Settings > Connections in the desktop app, and stop remote control when you are done. Remote control is experimental in Codex 0.164.

```bash
codex remote-control start
codex remote-control pair
codex remote-control stop
```

## Codex cloud

Tasks on chatgpt.com run in containers at OpenAI that cannot reach your Flux instance, so the `flux` server is not available there.

## Tests

The tests write the config in a temporary home directory. They check that Codex starts the server with `FLUX_URI`, which it does before it checks for an API key, so they need network access but no key.

```bash
flux start --test-size=2 python -m pytest agents/codex
```
