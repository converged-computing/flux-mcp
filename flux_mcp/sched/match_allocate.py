import json
from typing import Annotated, Any, Dict

import flux_mcp.sched.graph as graph

MatchAllocationResult = Annotated[
    Dict[str, Any],
    "A structured result of the scheduling match process. Contains the assigned 'jobid', "
    "the RFC 20 resource set 'R' if successful, and performance metrics like 'overhead'.",
]


def flux_sched_match_allocate(
    jobspec_json: Annotated[
        str, "A JSON string representing the RFC 25 Jobspec containing the resource requirements."
    ],
    orelse_reserve: Annotated[
        bool,
        "If True, the scheduler will create a future reservation if immediate resources are unavailable.",
    ] = False,
) -> MatchAllocationResult:
    """
    Attempts to find and allocate a matching set of resources for a jobspec against the current resource graph.

    This function is the primary entry point for the Fluxion matching logic. It searches the
    internal graph for a subgraph that satisfies the constraints defined in the jobspec.
    If a match is found, the resources are marked as allocated (or reserved) in the graph.

    Args:
        jobspec_json: The technical requirements of the job (nodes, cores, etc.) in JSON format.
        orelse_reserve: Behavioral flag; when True, prevents a 'failure' if the cluster is full
            by instead returning the earliest possible future time slot.

    Returns:
        A dictionary containing:
            - 'success' (bool): True if a match or reservation was successfully computed.
            - 'jobid' (int): The unique identifier assigned to this allocation in the scheduler.
            - 'reserved' (bool, optional): True if the result is a future reservation, False if it is immediate.
            - 'R' (str, optional): The RFC 20 Resource Set string representing the specific matched resources.
            - 'assigned_at' (float, optional): Unix timestamp indicating when the match was processed.
            - 'overhead' (float, optional): Time in seconds the scheduler spent computing this specific match.
            - 'error' (str, optional): A description of why the match failed (e.g., unsatisfiable).
    """
    try:
        cli = graph.get_resource_client()

        # Match returns a tuple: (jobid, reserved, R, at, ov)
        jobid, reserved, R, at, ov = cli.match(jobspec_json, orelse_reserve=orelse_reserve)

        if jobid == 0:
            return {
                "success": False,
                "error": "Scheduling failed (Job ID 0 returned: likely no resources available)",
            }

        return {
            "success": True,
            "jobid": jobid,
            "reserved": reserved,
            "R": R,
            "assigned_at": at,
            "overhead": ov,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "jobid": None}
