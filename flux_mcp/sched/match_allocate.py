import json

import flux_mcp.sched.graph as graph


def flux_sched_match_allocate(jobspec_json: str, orelse_reserve: bool = False) -> str:
    """
    Attempts to match (allocate) resources for a jobspec against the loaded graph.
    """
    try:
        cli = graph.get_resource_client()

        # Match returns a tuple: (jobid, reserved, R, at, ov)
        jobid, reserved, R, at, ov = cli.match(jobspec_json, orelse_reserve=orelse_reserve)

        if jobid == 0:
            return json.dumps({"success": False, "error": "Scheduling failed (Job ID 0 returned)"})

        return json.dumps(
            {
                "success": True,
                "jobid": jobid,
                "reserved": reserved,
                "R": R,
                "assigned_at": at,
                "overhead": ov,
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
