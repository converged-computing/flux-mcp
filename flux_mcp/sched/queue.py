from typing import Annotated, Any, Dict, List, Optional, Union

import flux.job

from flux_mcp.job.core import get_handle

QManagerStats = Annotated[
    Dict[str, Any],
    "A structured report of the queue manager state, including queue depths and job counts "
    "categorized by state (e.g., pending, running).",
]

AllocationResult = Annotated[
    Dict[str, Any],
    "A dictionary containing the result of a resource match request. Expected keys: "
    "'jobid' (int), 'status' (int), 'at' (float timestamp of allocation), "
    "'overhead' (float time in seconds), and 'R' (the RFC 20 resource set string).",
]

FeasibilityResponse = Annotated[
    Dict[str, Any],
    "A report indicating if the requested resources are theoretically satisfiable within "
    "the current cluster configuration, without performing an actual allocation.",
]

ResourceInfo = Annotated[
    Dict[str, Any],
    "Metadata regarding a specific resource vertex or job allocation, typically including "
    "timing data, status, or properties.",
]

GenericRPCResponse = Annotated[
    Dict[str, Any], "The raw response dictionary from the Flux RPC call."
]


def flux_sched_qmanager_stats(
    uri: Annotated[
        Optional[str],
        "The Flux connection URI (e.g., 'local:///run/flux/local'). Defaults to the local instance.",
    ] = None,
) -> QManagerStats:
    """
    Retrieves real-time statistics from the Flux Queue Manager.

    This includes counts of jobs in various states across different queues, which is
    useful for monitoring scheduler load and identifying bottlenecked queues.

    Args:
        uri: Optional unique resource identifier for the Flux instance.

    Returns:
        A dictionary mapping queue names to statistics like depth and job state tallies.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-qmanager.stats-get").get()


def flux_sched_resource_allocate(
    jobspec: Annotated[str, "A YAML string representing the job's resource requirements (RFC 25)."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> AllocationResult:
    """
    Attempts to allocate the best matching resources for a given jobspec immediately.

    Args:
        jobspec: The job requirements in YAML/JSON format.
        uri: Optional Flux URI.

    Returns:
        Allocation details including the matched resource set 'R'.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_allocate_with_satisfiability(
    jobspec: Annotated[str, "A YAML string representing the job's resource requirements (RFC 25)."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> AllocationResult:
    """
    Attempts to allocate resources; if no immediate match is found, performs a satisfiability check.

    This is useful to distinguish between a cluster that is currently full vs. a
    jobspec that can never be satisfied by the current cluster hardware.

    Args:
        jobspec: The job requirements.
        uri: Optional Flux URI.

    Returns:
        Allocation details or a status indicating overall satisfiability.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate_with_satisfiability", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_allocate_orelse_reserve(
    jobspec: Annotated[str, "A YAML string representing the job's resource requirements (RFC 25)."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> AllocationResult:
    """
    Attempts immediate allocation; if unavailable, finds the earliest possible reservation time.

    Args:
        jobspec: The job requirements.
        uri: Optional Flux URI.

    Returns:
        Either immediate allocation details or future reservation timing and resources.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate_orelse_reserve", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_feasibility_check(
    jobspec_dict: Annotated[Dict[str, Any], "A dictionary representing the jobspec requirements."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> FeasibilityResponse:
    """
    Performs a theoretical check to see if a jobspec could ever run on the cluster.

    This does not consume resources or create a reservation. It is used to validate
    if the cluster configuration supports the request (e.g., checking if 8 GPUs are
    even available in the graph).

    Args:
        jobspec_dict: Job requirements as a dictionary.
        uri: Optional Flux URI.

    Returns:
        A response indicating success or failure of the feasibility check.
    """
    handle = get_handle(uri)
    return handle.rpc("feasibility.check", {"jobspec": jobspec_dict}).get()


def flux_sched_resource_update(
    jobid: Annotated[Union[int, str], "The job identifier."],
    res_json: Annotated[str, "A JSON string representing the updated resource set (R)."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Updates the resource database for a specific job with a new resource set (R).

    Used when an allocation needs to be modified or refined after the initial match.

    Args:
        jobid: The identifier of the target job.
        res_json: The new resource (R) definition.
        uri: Optional Flux URI.

    Returns:
        Confirmation metadata of the update.
    """
    handle = get_handle(uri)
    payload = {"jobid": flux.job.JobID(jobid), "R": res_json}
    return handle.rpc("sched-fluxion-resource.update", payload).get()


def flux_sched_resource_cancel(
    jobid: Annotated[Union[int, str], "The job identifier to release resources for."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Cancels an allocated or reserved job and returns its resources to the free pool.

    Args:
        jobid: The identifier of the job.
        uri: Optional Flux URI.

    Returns:
        The result of the cancellation request.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.cancel", {"jobid": flux.job.JobID(jobid)}).get()


def flux_sched_resource_partial_cancel(
    jobid: Annotated[Union[int, str], "The job identifier."],
    rv1exec_json: Annotated[
        str, "A JSON string representing the specific resource subset to release."
    ],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Releases only a portion of a job's allocated resources.

    Useful for jobs that scale down during execution.

    Args:
        jobid: The identifier of the job.
        rv1exec_json: The specific resource subset to release.
        uri: Optional Flux URI.

    Returns:
        The result of the partial-cancel operation.
    """
    handle = get_handle(uri)
    payload = {"jobid": flux.job.JobID(jobid), "R": rv1exec_json}
    return handle.rpc("sched-fluxion-resource.partial-cancel", payload).get()


def flux_sched_resource_find(
    criteria: Annotated[str, "A compound expression for matching, e.g., 'status=up'."],
    find_format: Annotated[Optional[str], "The output format, e.g., 'json'."] = None,
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Searches the resource graph for vertices matching specific criteria.

    Args:
        criteria: The query string.
        find_format: Optional data format for the response.
        uri: Optional Flux URI.

    Returns:
        A dictionary containing the matched resource nodes.
    """
    handle = get_handle(uri)
    payload = {"criteria": criteria}
    if find_format:
        payload["format"] = find_format
    return handle.rpc("sched-fluxion-resource.find", payload).get()


def flux_sched_resource_set_property(
    resource_path: Annotated[str, "The path to the resource vertex, e.g., 'node0.core0'."],
    key_val: Annotated[str, "The property string in 'key=value' format."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Attaches a metadata property (key=value) to a specific resource in the graph.

    Args:
        resource_path: Target vertex path.
        key_val: The property to set.
        uri: Optional Flux URI.

    Returns:
        The result of the set operation.
    """
    handle = get_handle(uri)
    payload = {"sp_resource_path": resource_path, "sp_keyval": key_val}
    return handle.rpc("sched-fluxion-resource.set_property", payload).get()


def flux_sched_resource_remove_property(
    resource_path: Annotated[str, "The path to the resource vertex."],
    key: Annotated[str, "The property key to remove."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Removes a specific metadata property from a resource vertex.

    Args:
        resource_path: Target vertex path.
        key: The key to delete.
        uri: Optional Flux URI.

    Returns:
        The result of the removal.
    """
    handle = get_handle(uri)
    payload = {"resource_path": resource_path, "key": key}
    return handle.rpc("sched-fluxion-resource.remove_property", payload).get()


def flux_sched_resource_get_property(
    resource_path: Annotated[str, "The path to the resource vertex."],
    key: Annotated[str, "The property key to retrieve."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Retrieves the value of a specific property for a given resource vertex.

    Args:
        resource_path: Target vertex path.
        key: The property key.
        uri: Optional Flux URI.

    Returns:
        A dictionary containing the property values.
    """
    handle = get_handle(uri)
    payload = {"gp_resource_path": resource_path, "gp_key": key}
    return handle.rpc("sched-fluxion-resource.get_property", payload).get()


def flux_sched_resource_status(
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Retrieves the high-level status (up, down, allocated) for all resource vertices.

    Returns:
        A report of resource nodes grouped by their current status.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.status").get()


def flux_sched_resource_set_status(
    resource_path: Annotated[str, "The path to the resource vertex."],
    status: Annotated[str, "The desired status string: 'up' or 'down'."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Manually overrides the operational status of a resource vertex.

    This can be used to drain nodes ('down') or return them to service ('up').

    Args:
        resource_path: Target vertex path.
        status: The new status.
        uri: Optional Flux URI.

    Returns:
        The result of the status update.
    """
    handle = get_handle(uri)
    payload = {"resource_path": resource_path, "status": status}
    return handle.rpc("sched-fluxion-resource.set_status", payload).get()


def flux_sched_resource_stats(
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Retrieves internal performance metrics from the Fluxion resource module.

    Includes graph traversal statistics and scheduler matching latencies.

    Returns:
        A dictionary of performance metrics.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.stats-get").get()


def flux_sched_resource_stats_clear(
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Resets the internal performance counters for the resource module.

    Returns:
        Confirmation of the reset operation.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.stats-clear").get()


def flux_sched_resource_params(
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Retrieves the current runtime configuration parameters for Fluxion.

    Returns:
        A dictionary of the scheduler's internal settings.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.params").get()


def flux_sched_resource_ns_info(
    rank: Annotated[int, "The target rank."],
    type_name: Annotated[str, "The resource type name, e.g., 'core'."],
    identity: Annotated[int, "The raw resource ID."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> GenericRPCResponse:
    """
    Translates a raw resource ID into its namespaced (remapped) equivalent for a specific rank.

    Args:
        rank: The rank context for translation.
        type_name: Type of resource.
        identity: The original ID.
        uri: Optional Flux URI.

    Returns:
        A dictionary containing the remapped ID.
    """
    handle = get_handle(uri)
    payload = {"rank": rank, "type-name": type_name, "id": identity}
    return handle.rpc("sched-fluxion-resource.ns-info", payload).get()


def flux_sched_resource_info(
    jobid: Annotated[Union[int, str], "The job identifier."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> ResourceInfo:
    """
    Retrieves detailed allocation information and scheduling overhead for a specific job.

    Args:
        jobid: The identifier of the job.
        uri: Optional Flux URI.

    Returns:
        Timing data and resource status specific to the job's lifecycle in the scheduler.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.info", {"jobid": flux.job.JobID(jobid)}).get()
