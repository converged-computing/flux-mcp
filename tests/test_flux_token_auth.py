import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from flux_mcp.server.fastmcp.middleware import TokenAuthMiddleware

TOKEN = "test-token"

# The same app setup as flux_mcp.server.fastmcp.__main__, on a chosen port.
SERVER = """
import sys
from flux_mcp.server.fastmcp.__main__ import register_with
from flux_mcp.server.fastmcp.app import init_mcp
mcp = init_mcp()
register_with(mcp)
mcp.run(transport="http", host="127.0.0.1", port=int(sys.argv[1]))
"""


def free_port():
    """Return a TCP port that is free on localhost."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def token_server():
    """Start an HTTP server that requires TOKEN and return its URL."""
    port = free_port()
    env = dict(os.environ, FLUX_MCP_TOKEN=TOKEN)
    proc = subprocess.Popen(
        [sys.executable, "-c", SERVER, str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"token server exited: {proc.stderr.read()}")
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("token server did not start")
    yield f"http://127.0.0.1:{port}/mcp"
    proc.kill()
    proc.wait()


def list_tools(url, headers):
    """Return the tool names the server lists with these headers."""

    async def run():
        async with Client(StreamableHttpTransport(url=url, headers=headers)) as client:
            return [tool.name for tool in await client.list_tools()]

    return asyncio.run(run())


@pytest.mark.parametrize(
    "header",
    [f"Bearer {TOKEN}", f"bearer {TOKEN}", TOKEN, f"Bearer:{TOKEN}", f"Basic:{TOKEN}"],
    ids=["bearer", "bearer-lowercase", "bare", "bearer-colon", "basic-colon"],
)
def test_accepts_token(token_server, header):
    assert "flux_submit_job" in list_tools(token_server, {"Authorization": header})


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Bearer {TOKEN}x"}],
    ids=["missing", "wrong", "suffix"],
)
def test_rejects_without_token(token_server, headers):
    with pytest.raises(Exception):
        list_tools(token_server, headers)


@pytest.mark.parametrize(
    "value,token",
    [
        (f"Bearer {TOKEN}", TOKEN),
        (f"  Bearer   {TOKEN}  ", TOKEN),
        (TOKEN, TOKEN),
        (f"BEARER:{TOKEN}", TOKEN),
        ("Bearer", "Bearer"),
        (f"Token {TOKEN}", f"Token {TOKEN}"),
    ],
)
def test_parse_token(value, token):
    assert TokenAuthMiddleware.parse_token(value) == token
