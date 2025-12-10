import json
from typing import Optional, Union

import flux
import flux.job

import flux_mcp.utils as utils


def get_handle(uri: Optional[str] = None) -> flux.Flux:
    """Helper to get a Flux handle, optionally connecting to a remote URI."""
    if uri:
        return flux.Flux(uri)
    return flux.Flux()


def flux_submit_job(jobspec: str, uri: Optional[str] = None, submit_async: bool = True) -> str:
    """
    Submits a job to Flux.

    Args:
        jobspec: A valid JSON string or YAML string of the jobspec.
        uri: Optional Flux URI. If not provided, uses local instance.

    Returns:
        JSON string containing the new Job ID or error message.
    """
    try:
        # Ensure we got a json string
        jobspec = json.dumps(utils.load_jobspec(jobspec))
        h = get_handle(uri)

        # Submit the job
        if submit_async:
            future = flux.job.submit_async(h, jobspec)
            jobid = future.get_id()
        else:
            jobid = flux.job.submit(h, jobspec)

        # Return success with the integer ID
        return json.dumps({"success": True, "job_id": int(jobid), "uri": uri or "local"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def flux_cancel_job(job_id: Union[int, str], uri: Optional[str] = None) -> str:
    """
    Cancels a specific Flux job.

    Args:
        job_id: The ID of the job to cancel.
        uri: Optional Flux URI.
    """
    try:
        h = get_handle(uri)

        # Convert to proper integer ID
        job_id = flux.job.JobID(job_id)
        flux.job.cancel(h, job_id)

        return json.dumps(
            {"success": True, "message": f"Job {job_id} cancellation requested.", "job_id": job_id}
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def flux_get_job_info(job_id: Union[int, str], uri: Optional[str] = None) -> str:
    """
    Retrieves status and information about a specific job.

    Args:
        job_id: The ID of the job.
        uri: Optional Flux URI.
    """
    try:
        h = get_handle(uri)
        id_int = flux.job.JobID(job_id)
        info = flux.job.get_job(h, id_int)
        return json.dumps(info)

    except EnvironmentError:
        return json.dumps({"success": False, "error": f"Job {job_id} not found."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
