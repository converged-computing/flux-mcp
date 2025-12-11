import json

import flux_mcp.sched.graph as graph


def flux_sched_cancel_job(jobid: int) -> str:
    """
    Cancels a job and releases its resources back to the graph.
    """
    try:
        cli = graph.get_resource_client()
        cli.cancel(jobid)
        return json.dumps(
            {"success": True, "message": f"Job {jobid} canceled and resources released."}
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def flux_sched_partial_cancel(jobid: int, resource_subset: str) -> str:
    """
    Releases a specific subset of resources from a running job.

    Args:
        jobid: The job ID.
        resource_subset: An R-spec string or RV1 JSON string defining resources to drop.
    """
    try:
        cli = graph.get_resource_client()
        is_fully_removed = cli.partial_cancel(jobid, resource_subset)

        return json.dumps(
            {
                "success": True,
                "jobid": jobid,
                "fully_removed": is_fully_removed,
                "message": "Job removed entirely" if is_fully_removed else "Job resources shrunk",
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
