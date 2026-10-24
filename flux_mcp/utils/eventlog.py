import time


def next_event(watcher, deadline=None, name=None):
    """Return the next event (or next event named name), or None when the eventlog ends."""
    while True:
        if deadline is not None:
            watcher.wait_for(max(deadline - time.monotonic(), 0))
        event = watcher.get_event()
        if event is None or name is None or event.name == name:
            return event


def fatal_exception(handle, jobid):
    """Return the note of the job's fatal exception, or None."""
    import flux.job

    for event in flux.job.event_watch(handle, jobid):
        if event.name == "exception" and event.context.get("severity") == 0:
            return event.context.get("note") or event.context.get("type")
    return None
