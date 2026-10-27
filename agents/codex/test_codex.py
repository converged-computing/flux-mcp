import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SERVER = str(Path(sys.executable).parent / "flux-mcp-stdio")


def env_for(home):
    """Return the environment for running Codex in a temporary HOME."""
    env = {k: v for k, v in os.environ.items() if k != "CODEX_HOME"}
    return dict(env, HOME=str(home))


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    """Return a temporary HOME with the flux server in the Codex config, as in the README."""
    path = tmp_path_factory.mktemp("home")
    (path / ".codex").mkdir()
    (path / ".codex" / "config.toml").write_text(
        f'[mcp_servers.flux]\ncommand = "{SERVER}"\nenv_vars = ["FLUX_URI"]\n'
    )
    return path


def test_config_parses(home):
    flux = tomllib.loads((home / ".codex" / "config.toml").read_text())["mcp_servers"]["flux"]
    assert flux == {"command": SERVER, "env_vars": ["FLUX_URI"]}


def test_codex_reads_config(home):
    proc = subprocess.run(
        ["codex", "mcp", "get", "flux"], env=env_for(home), capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert SERVER in proc.stdout
    assert "FLUX_URI" in proc.stdout


def test_codex_passes_flux_uri_to_server(home, tmp_path):
    log = tmp_path / "env.txt"
    wrapper = tmp_path / "server.sh"
    wrapper.write_text(f"#!/bin/bash\nenv > {log}\nexec {SERVER}\n")
    wrapper.chmod(0o755)

    # Codex starts MCP servers before it checks authentication, so no API key is needed.
    command = ["codex", "-c", f'mcp_servers.flux.command="{wrapper}"']
    try:
        subprocess.run(
            command + ["exec", "--skip-git-repo-check", "hi"],
            env=env_for(home),
            cwd=tmp_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        pass
    assert log.is_file(), "codex did not start the flux server"
    env = dict(line.split("=", 1) for line in log.read_text().splitlines() if "=" in line)
    assert env["FLUX_URI"] == os.environ["FLUX_URI"]
