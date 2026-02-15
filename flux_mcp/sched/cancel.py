import json
from typing import Annotated, Any, Dict

import flux_mcp.sched.graph as graph

JobReleaseResult = Annotated[
    Dict[str, Any],
    "A result dictionary indicating if the job was successfully canceled and its "
    "associated resources were released back into the scheduler's resource graph.",
]

PartialReleaseResult = Annotated[
    Dict[str, Any],
    "A dictionary containing the status of a partial resource release, including "
    "whether the job was fully removed or just reduced in size.",
]


def flux_sched_cancel_job(
    jobid: Annotated[int, "The unique integer identifier of the job to cancel."],
) -> JobReleaseResult:
    """
    Cancels a job within the scheduler and releases its allocated resources back to the graph.

    This function interacts directly with the Fluxion resource client. It is used to
    inform the scheduler that a job has terminated or been aborted, ensuring the
    resources it held are marked as 'free' for future matches.

    Args:
        jobid: The integer ID of the job whose resources should be released.

    Returns:
        A dictionary containing:
            - 'success' (bool): True if the cancellation and release were successful.
            - 'message' (str): A description of the operation result.
            - 'error' (str, optional): An error message if the operation failed.
    """
    try:
        cli = graph.get_resource_client()
        cli.cancel(jobid)
        return {"success": True, "message": f"Job {jobid} canceled and resources released."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def flux_sched_partial_cancel(
    jobid: Annotated[int, "The unique integer identifier of the job."],
    resource_subset: Annotated[
        str,
        "An R-spec string or RV1 JSON string defining the specific subset of resources to be released.",
    ],
) -> PartialReleaseResult:
    """
    Releases a specific subset of resources from a running or allocated job.

    This is used for elastic jobs that can scale down. If the subset provided
    matches all resources currently held by the job, the job is removed entirely
    from the graph.

    Args:
        jobid: The integer ID of the job.
        resource_subset: A string representing the resource set (R) to drop from the job.

    Returns:
        A dictionary containing:
            - 'success' (bool): True if the partial release was successful.
            - 'jobid' (int): The identifier of the job processed.
            - 'fully_removed' (bool): True if no resources remain for this job, False if it is still active with a reduced set.
            - 'message' (str): A descriptive status message.
            - 'error' (str, optional): An error message if the operation failed.
    """
    try:
        cli = graph.get_resource_client()
        is_fully_removed = cli.partial_cancel(jobid, resource_subset)

        return {
            "success": True,
            "jobid": jobid,
            "fully_removed": is_fully_removed,
            "message": "Job removed entirely" if is_fully_removed else "Job resources shrunk",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "full_removed": None,
            "message": "There was an error with partial cancel",
        }
