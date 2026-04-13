import asyncio
import uuid
from logging import getLogger
from typing import Any, Awaitable, Callable, Dict, List, Optional

import flux
import flux.job

from .core import get_handle

LOGGER = getLogger(__name__)

# Events we ignore to reduce noise and redundancy
SKIP_EVENTS = [
    "submit",
    "validate",
    "depend",
    "priority",
    "annotations",
    "alloc",
    "release",
    "free",
    "finish",
]


class FluxJobWrapper:
    """
    Wraps a Flux Journal event and provides state-machine friendly properties.
    """

    def __init__(self, event_dict, handle):
        self.event = event_dict
        self.handle = handle

        # Resolve IDs and Jobspec
        if "kvs" in self.event:
            self.jobspec = self.event["kvs"]["jobspec"]
            self.fluxid = self.event["id"]
        else:
            self.fluxid = self.event.get("id") or self.event.get("jobid")
            # Fallback to KVS fetch if jobspec isn't in the event
            self.jobspec = flux.job.job_kvs(self.handle, self.fluxid).get("jobspec")

    @property
    def job_name(self) -> str:
        """
        The job name (e.g. 'lammps-run-1')
        """
        return self.jobspec.get("attributes", {}).get("user", {}).get("jobname")

    @property
    def app_name(self) -> str:
        """
        The application/step name (e.g. 'generate' or 'simulate')
        """
        return self.jobspec.get("attributes", {}).get("user", {}).get("app")

    @property
    def current_state(self) -> Dict[str, Any]:
        """
        Fetch current live state from Flux
        """
        return flux.job.get_job(self.handle, self.fluxid)

    def to_dict(self) -> Dict[str, Any]:
        """
        Simplified dictionary for MCP notification delivery
        """
        state = self.current_state
        return {
            "flux_id": self.fluxid,
            "job_name": self.job_name,
            "app_name": self.app_name,
            "event_name": self.event.get("name"),
            "status": state.get("status"),
            "return_code": state.get("returncode"),
            "is_completed": state.get("status") in ["COMPLETED", "FAILED"],
            "is_failed": state.get("status") == "FAILED"
            or (state.get("returncode", 0) != 0 if state.get("status") == "COMPLETED" else False),
        }


class FluxEvents:
    """
    Modular Flux Event Provider for MCP Server.
    Uses JournalConsumer to stream job lifecycle events.
    """

    name = "flux"

    def __init__(self):
        self.handle = get_handle()
        self._active_watches: Dict[str, asyncio.Task] = {}

    def get_metadata(self) -> Dict[str, Any]:
        """
        Discovery metadata for the Agent.
        """
        return {
            "name": "flux_events",
            "description": "Watch for Flux job lifecycle events (start, run, clean, etc.)",
            "parameters": {
                "job_name": "string (optional: filter by state machine job name)",
                "app_name": "string (optional: filter by app/step name)",
            },
        }

    async def subscribe(
        self, params: Dict[str, Any], callback: Callable[[str, Dict[str, Any]], Awaitable[None]]
    ) -> str:
        """
        Subscribe to events. Required for mcp-server.
        """
        sub_id = f"flux_{uuid.uuid4().hex[:8]}"

        # Start the background polling task
        task = asyncio.create_task(self._watch_loop(sub_id, params, callback))
        self._active_watches[sub_id] = task

        return sub_id

    async def unsubscribe(self, sub_id: str) -> bool:
        """
        Unsubscribe from events.
        """
        task = self._active_watches.pop(sub_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        return False

    async def _watch_loop(self, sub_id: str, params: Dict[str, Any], callback: Callable):
        """
        Polling loop using flux.job.JournalConsumer.
        """
        # Filter parameters from the agent
        target_job = params.get("job_name")
        target_app = params.get("app_name")

        # Initialize the Flux Consumer
        consumer = flux.job.JournalConsumer(self.handle)
        consumer.start()

        try:
            while True:
                # Use to_thread because consumer.poll is a blocking C-call
                event = await asyncio.to_thread(consumer.poll, timeout=1.0)

                if not event:
                    continue

                if event["name"] in SKIP_EVENTS:
                    continue

                # Wrap event in FluxJob logic
                try:
                    job = FluxJobWrapper(event, self.handle)
                except Exception as e:
                    LOGGER.debug(f"Could not wrap flux event {event.get('id')}: {e}")
                    continue

                # Apply filters requested by the agent
                if target_job and job.job_name != target_job:
                    continue
                if target_app and job.app_name != target_app:
                    continue

                # Send data back to MCP client
                await callback(sub_id, job.to_dict())

        # If canceled, we probably want a clean exit here (pass)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            LOGGER.error(f"Flux event stream error: {e}")
            await callback(sub_id, {"error": str(e), "status": "failed"})
