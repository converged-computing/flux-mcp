import sys
from typing import Annotated, Any, Dict, Optional

sys.modules["yaml.cyaml"] = None

import json

import flux
import flux.job

DelegationResult = Annotated[
    Dict[str, Any],
    "A dictionary containing the 'job_id' (int) or None, the submission 'status' (str), and the 'uri' (str) of the target Flux instance.",
]


def flux_handle_delegation(
    remote_uri: str, jobspec_str: str, jobid: Optional[int] = None
) -> DelegationResult:
    """
    Performs a remote job submission to delegate work to a different Flux instance.
    This function prepares the jobspec by removing local dependencies and delegation
    metadata to avoid circular delegation, then submits it to the remote URI.

    Args:
        remote_uri: The Flux URI of the remote cluster/instance.
        jobspec_str: The JSON-encoded jobspec string.
        jobid: A local identifier of the job being delegated (optional)

    Returns:
        A structured dictionary containing the remote job details on success,
        or an error status with job_id None on failure.
    """
    try:
        remote_h = flux.Flux(remote_uri)
        if jobid:
            print(f"Delegate: Starting remote submission for job {jobid} to {remote_uri}")
        else:
            print(f"Delegate: Starting remote submission for job to {remote_uri}")

        jobspec = json.loads(jobspec_str)
        if (
            "attributes" in jobspec
            and "system" in jobspec["attributes"]
            and "dependencies" in jobspec["attributes"]["system"]
        ):
            del jobspec["attributes"]["system"]["dependencies"]

        # This would do it infinitely...
        if (
            "attributes" in jobspec
            and "system" in jobspec["attributes"]
            and "delegate" in jobspec["attributes"]["system"]
        ):
            del jobspec["attributes"]["system"]["delegate"]

        encoded_jobspec = json.dumps(jobspec)

        # Use the one helper function that has been proven to work reliably.
        remote_jobid = flux.job.submit(remote_h, encoded_jobspec)
        print(f"Delegate: Job {jobid} submitted. Remote jobid is {remote_jobid}")

        return {"job_id": remote_jobid, "status": "submit", "uri": remote_uri or "local"}

    except Exception as e:
        print(f"Delegate: Failed to delegate job: {e}")
        return {"job_id": None, "status": f"error: {str(e)}", "uri": remote_uri or "local"}
