import json

import flux_mcp.sched.graph as graph


def flux_sched_job_info(jobid: int) -> str:
    """
    Retrieves internal scheduler state for a specific job ID.
    """
    try:
        cli = graph.get_resource_client()

        # info returns: (mode, is_reserved, at, ov)
        mode, is_reserved, at, ov = cli.info(jobid)

        return json.dumps(
            {
                "success": True,
                "jobid": jobid,
                "mode": mode,
                "is_reserved": is_reserved,
                "assigned_at": at,
                "overhead": ov,
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
