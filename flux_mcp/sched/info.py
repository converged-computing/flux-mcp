import json
from typing import Annotated, Any, Dict

import flux_mcp.sched.graph as graph

# Define custom type for MCP schema clarity
SchedulerJobInfo = Annotated[
    Dict[str, Any],
    "A structured report of a job's status within the scheduler's resource graph, "
    "including allocation timestamps and scheduling performance metrics.",
]


def flux_sched_job_info(
    jobid: Annotated[int, "The unique integer identifier of the job to query."],
) -> SchedulerJobInfo:
    """
    Retrieves the internal scheduler state and performance metrics for a specific job ID.

    This function queries the Fluxion resource client to understand how a job is
    represented in the resource graph. It provides technical details about the
    matching process, such as whether the job is currently allocated or just
    reserved, and how much computational effort was required to find the match.

    Args:
        jobid: The integer ID of the job existing in the scheduler state.

    Returns:
        A dictionary containing:
            - 'success' (bool): True if the job was found and info retrieved.
            - 'jobid' (int): The identifier of the job. None if an error occurred.
            - 'mode' (int, optional): The internal scheduling mode used for the match.
            - 'is_reserved' (bool, optional): True if the job holds a future reservation, False if it is a current allocation.
            - 'assigned_at' (float, optional): The unix timestamp indicating when the match occurred.
            - 'overhead' (float, optional): The time in seconds taken by the scheduler to compute the resource match.
            - 'error' (str, optional): A descriptive error message if the query failed.
    """
    try:
        cli = graph.get_resource_client()

        # info returns: (mode, is_reserved, at, ov)
        mode, is_reserved, at, ov = cli.info(jobid)

        return {
            "success": True,
            "jobid": jobid,
            "mode": mode,
            "is_reserved": is_reserved,
            "assigned_at": at,
            "overhead": ov,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "jobid": None}
