import asyncio
import inspect
import threading
import time

import pytest
from fastmcp.tools import Tool
from mcp.server.mcpserver import MCPServer

from flux_mcp.registry import TOOLS
from flux_mcp.server.threads import SERIALIZED_PREFIX, run_in_thread


def sleeper(seconds: float = 0.5) -> str:
    """Sleep and return the worker thread name."""
    time.sleep(seconds)
    return threading.current_thread().name


def tracked(counter):
    """Return a blocking tool that records how many copies run at once."""

    def tool() -> int:
        """Record concurrency."""
        with counter["lock"]:
            counter["now"] += 1
            counter["max"] = max(counter["max"], counter["now"])
        time.sleep(0.2)
        with counter["lock"]:
            counter["now"] -= 1
        return counter["max"]

    return tool


def new_counter():
    """Return a concurrency counter."""
    return {"lock": threading.Lock(), "now": 0, "max": 0}


@pytest.mark.asyncio
async def test_blocking_tools_run_concurrently():
    wrapped = run_in_thread(sleeper)
    start = time.monotonic()
    names = await asyncio.gather(wrapped(0.5), wrapped(0.5), wrapped(0.5))
    assert time.monotonic() - start < 1.2
    assert threading.main_thread().name not in names


@pytest.mark.asyncio
async def test_other_tools_overlap():
    counter = new_counter()
    tool = tracked(counter)
    tool.__module__ = "flux_mcp.job.test"
    wrapped = run_in_thread(tool)
    await asyncio.gather(*(wrapped() for _ in range(3)))
    assert counter["max"] > 1


@pytest.mark.asyncio
async def test_sched_tools_serialized():
    counter = new_counter()
    tool = tracked(counter)
    tool.__module__ = f"{SERIALIZED_PREFIX}.test"
    wrapped = run_in_thread(tool)
    await asyncio.gather(*(wrapped() for _ in range(3)))
    assert counter["max"] == 1


@pytest.mark.asyncio
async def test_exceptions_propagate():
    def broken() -> None:
        """Raise."""
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await run_in_thread(broken)()


@pytest.mark.asyncio
async def test_async_tools_unchanged():
    async def already_async() -> int:
        """Return a value."""
        return 1

    assert run_in_thread(already_async) is already_async


def test_metadata_preserved():
    wrapped = run_in_thread(sleeper)
    assert inspect.iscoroutinefunction(wrapped)
    assert inspect.signature(wrapped) == inspect.signature(sleeper)
    assert wrapped.__name__ == sleeper.__name__
    assert wrapped.__doc__ == sleeper.__doc__


@pytest.mark.parametrize("func", TOOLS, ids=lambda f: f.__name__)
def test_fastmcp_schema_unchanged(func):
    plain = Tool.from_function(func)
    wrapped = Tool.from_function(run_in_thread(func))
    assert wrapped.name == plain.name
    assert wrapped.description == plain.description
    assert wrapped.parameters == plain.parameters
    assert wrapped.output_schema == plain.output_schema


@pytest.mark.asyncio
async def test_mcpserver_schemas_unchanged():
    plain, wrapped = MCPServer(name="plain"), MCPServer(name="wrapped")
    for func in TOOLS:
        plain.add_tool(func)
        wrapped.add_tool(run_in_thread(func))
    dump = lambda tools: {t.name: t.model_dump() for t in tools}
    assert dump(await wrapped.list_tools()) == dump(await plain.list_tools())
