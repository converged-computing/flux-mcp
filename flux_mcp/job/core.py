import json
import os
import time
from typing import Annotated, Any, Dict, List, Mapping, Optional, Union

import flux
import flux.job

import flux_mcp.utils as utils

# Define custom types for MCP schema clarity
JobSubmissionResult = Annotated[
    Dict[str, Any],
    "A dictionary containing 'success' (bool), 'error' (str or None), 'job_id' (int or None), and 'uri' (str). A failed submission does not have a job_id and will likely have a string error.",
]
JobActionResponse = Annotated[
    Dict[str, Any],
    "A structured response containing 'success' (bool), a descriptive 'message' (str), and the 'job_id' and an 'error' if the action was not successful.",
]

JobInfoResult = Annotated[
    Dict[str, Any],
    "A structured report containing: "
    "- 'success' (bool): True if the job was found. "
    "- 'error' (str): Error message if search failed. "
    "- 'info' (dict): The job metadata, containing: "
    "    - 'id' (int): The integer Job ID. "
    "    - 'state' (str): Current execution state (e.g., DEPEND, PRIORITY, SCHED, RUN, CLEANUP, INACTIVE). "
    "    - 'status' (str): Human-readable status (e.g., DEPEND, PRIORITY, SCHED, RUN, CLEANUP, COMPLETED, FAILED, CANCELED, or TIMEOUT). "
    "    - 'result' (str): The final result string. "
    "    - 'returncode' (int): The process exit code (0 for success). "
    "    - 'runtime' (float): Total time elapsed in seconds. "
    "    - 'nnodes'/'ntasks' (int): Resource counts. "
    "    - 'nodelist' (str): Hostnames assigned to the job.",
]

LogLinesResult = Annotated[
    Dict[str, Any],
    "A dictionary containing 'success' (bool), 'error' (str or None), and 'lines' (list of strings or None).",
]


def get_handle(uri: Optional[str] = None) -> flux.Flux:
    """Helper to get a Flux handle, optionally connecting to a remote URI."""
    if uri:
        return flux.Flux(uri)
    return flux.Flux()


def flux_submit_job(
    command: List[str],
    uri: Optional[str] = None,
    num_tasks: int = 1,
    cores_per_task: int = 1,
    gpus_per_task: Optional[int] = None,
    num_nodes: Optional[int] = None,
    exclusive: bool = False,
    duration: Optional[Union[int, float, str]] = None,
    environment: Optional[Mapping[str, str]] = None,
    env_expand: Optional[Mapping[str, str]] = None,
    cwd: Optional[str] = None,
    rlimits: Optional[Mapping[str, int]] = None,
    name: Optional[str] = None,
    input: Optional[Union[str, os.PathLike]] = None,
    output: Optional[Union[str, os.PathLike]] = None,
    error: Optional[Union[str, os.PathLike]] = None,
    label_io: bool = False,
    unbuffered: bool = False,
    queue: Optional[str] = None,
    bank: Optional[str] = None,
) -> JobSubmissionResult:
    """
    Creates a Jobspec from a command and submits it to Flux.

    Args:
        command: Command to execute (iterable of strings).
        uri: Optional Flux URI. If not provided, uses local instance.
        submit_async: Whether to submit the job asynchronously.
        num_tasks: Number of tasks to create.
        cores_per_task: Number of cores to allocate per task.
        gpus_per_task: Number of GPUs to allocate per task.
        num_nodes: Distribute allocated tasks across N individual nodes.
        exclusive: Always allocate nodes exclusively.
        duration: Time limit in Flux Standard Duration (str), seconds (int/float), or timedelta.
        environment: Mapping of environment variables for the job.
        env_expand: Mapping of environment variables containing mustache templates.
        cwd: Set the current working directory for the job.
        rlimits: Mapping of process resource limits (e.g. {"nofile": 12000}).
        name: Set a custom job name.
        input: Path to a file for job input.
        output: Path to a file for job output (stdout).
        error: Path to a file for job error (stderr).
        label_io: Label output with the source task IDs.
        unbuffered: Disable output buffering.
        queue: Set the queue for the job.
        bank: Set the bank for the job.

    Returns:
        Dictionary containing the success status and Job ID or error message.
    """
    try:
        # Generate the Jobspec from the provided arguments
        jobspec = flux.job.JobspecV1.from_command(
            command=command,
            num_tasks=num_tasks,
            cores_per_task=cores_per_task,
            gpus_per_task=gpus_per_task,
            num_nodes=num_nodes,
            exclusive=exclusive,
        )
        h = get_handle(uri)

        # Note that newer flux (as of 8 months ago) supports these are arguments above
        if environment is not None:
            jobspec.environment = environment
        if duration is not None:
            jobspec.duration = duration
        if cwd is not None:
            jobspec.cwd = cwd
        if env_expand is not None:
            jobspec.env_expand = env_expand
        if rlimits is not None:
            jobspec.rlimits = rliits
        if input is not None:
            jobspec.input = input
        if output is not None:
            jobspec.output = output
        if error is not None:
            jobspec.error = error
        if queue is not None:
            jobspec.queue = queue
        if bank is not None:
            jobspec.bank = bank
        if unbuffered is not None:
            jobspec.unbuffered = unbuffered
        if label_io is not None:
            jobspec.label_io = label_io
        if name is not None:
            jobspec.name = name

        jobid = flux.job.submit(h, jobspec)
        return {"success": True, "error": None, "job_id": int(jobid), "uri": uri or "local"}

    except Exception as e:
        return {"success": False, "error": str(e), "job_id": None, "uri": uri or "local"}


def flux_submit_jobspec(
    jobspec: str, uri: Optional[str] = None, submit_async: bool = True
) -> JobSubmissionResult:
    """
    Submits a job to Flux. An example jobspec requires attributes, tasks, resources, version
    and at least one referenced slot.

    Args:
        jobspec: A valid JSON string or YAML string of the jobspec.
        uri: Optional Flux URI. If not provided, uses local instance.

    Returns:
        Dictionary containing the new Job ID or error message.
    """
    try:
        # Ensure we got a json string
        jobspec = utils.load_jobspec(jobspec)
        h = get_handle(uri)

        # Submit the job
        if submit_async:
            future = flux.job.submit_async(h, json.dumps(jobspec))
            jobid = future.get_id()
        else:
            jobid = flux.job.submit(h, json.dumps(jobspec))

        # Return success with the integer ID
        return {"success": True, "job_id": int(jobid), "uri": uri or "local"}

    except Exception as e:
        return {"success": False, "job_id": None, "error": str(e), "uri": uri or "local"}


def flux_cancel_job(job_id: Union[int, str], uri: Optional[str] = None) -> JobActionResponse:
    """
    Cancels a specific Flux job.

    Args:
        job_id: The ID of the job to cancel.
        uri: Optional Flux URI.
    """
    try:
        h = get_handle(uri)

        # Convert to proper integer ID
        jid = flux.job.JobID(job_id)
        flux.job.cancel(h, jid)

        return {
            "success": True,
            "message": f"Job {job_id} cancellation requested.",
            "job_id": int(jid),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "message": "Cancellation had an error."}


def flux_get_job_info(job_id: Union[int, str], uri: Optional[str] = None) -> JobInfoResult:
    """
    Retrieves status and information about a specific job.

    Args:
        job_id: The ID of the job.
        uri: Optional Flux URI.
    """
    try:
        h = get_handle(uri)
        id_int = flux.job.JobID(job_id)
        info = dict(flux.job.get_job(h, id_int))
        return {"success": True, "error": None, "info": info}

    except EnvironmentError as e:
        return {"success": False, "error": f"Job {job_id} not found.", "info": None}
    except Exception as e:
        return {"success": False, "error": str(e), "info": None}


def flux_get_job_logs(
    job_id: Union[int, str], uri: Optional[str] = None, delay: Optional[int] = None
) -> LogLinesResult:
    """
    Retrieves the output logs (stdout/stderr) associated with a specific Flux job.

    This function monitors the job's event log for output events. It can either
    wait until the job finishes or stop after a specified delay.

    Args:
        job_id: The unique identifier of the job (integer or f58 string).
        uri: Optional Flux handle URI. If omitted, connects to the local instance.
        delay: The maximum time in seconds to spend collecting logs. If None,
               the function blocks until the job event stream is closed.

    Returns:
        A dictionary containing:
            - 'success' (bool): True if the log retrieval was initiated without error.
            - 'error' (str or None): A descriptive error message if retrieval failed.
            - 'lines' (list[str] or None): A list of strings, where each string is
               a chunk of output data captured from the job's 'guest.output' stream.
    """
    lines = []
    start = time.time()
    try:
        h = get_handle(uri)
        job_id_obj = flux.job.JobID(job_id)
        # Event watch on the output stream
        for line in flux.job.event_watch(h, job_id_obj, "guest.output"):
            if "data" in line.context:
                lines.append(line.context["data"])

            now = time.time()
            if delay is not None and (now - start) > delay:
                break
    except Exception as e:
        return {"success": False, "error": str(e), "lines": None}
    return {"success": True, "error": None, "lines": lines}
