import functools
import inspect
import threading

import anyio.to_thread

# flux-sched tools share one resource graph (flux_mcp.sched.graph), so they stay
# serialized, as they were when every tool ran on the event loop.
SERIALIZED_PREFIX = "flux_mcp.sched"
_serialized = threading.Lock()


def _locked(call):
    """Run call while holding the serialized-tools lock."""
    with _serialized:
        return call()


def run_in_thread(func):
    """Wrap a blocking tool so it runs in a worker thread instead of the event loop."""
    if inspect.iscoroutinefunction(func):
        return func
    serialize = func.__module__.startswith(SERIALIZED_PREFIX)

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        call = functools.partial(func, *args, **kwargs)
        if serialize:
            call = functools.partial(_locked, call)
        return await anyio.to_thread.run_sync(call)

    return wrapper
