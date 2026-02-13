from typing import Annotated, Any, Optional, Union

import flux.job

from flux_mcp.job.core import get_handle

# Queue Manager RPCs


def flux_sched_qmanager_stats(
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Retrieve stats for the Flux queue manager.

    Args:
        uri: Optional Flux URI.
    Returns:
        JSON structure of queues with depths, and jobs in different states.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-qmanager.stats-get").get()


# Fluxion Resource RPCs


def flux_sched_resource_allocate(
    jobspec: str, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Allocate the best matching resources for a given jobspec.

    Args:
        jobspec: A YAML string representing the job requirements.
        uri: Optional Flux URI.
    Returns:
        A dictionary containing 'jobid', 'status', 'at', 'overhead', and matched resource 'R'.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_allocate_with_satisfiability(
    jobspec: str, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Allocate best matching resources if found; otherwise, check jobspec's overall satisfiability.

    Args:
        jobspec: A YAML string representing the job requirements.
        uri: Optional Flux URI.
    Returns:
        Allocation details or satisfiability status.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate_with_satisfiability", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_allocate_orelse_reserve(
    jobspec: str, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Allocate best matching resources if found; otherwise, reserve them at the earliest time.

    Args:
        jobspec: A YAML string representing the job requirements.
        uri: Optional Flux URI.
    Returns:
        Allocation or reservation timing and resource 'R'.
    """
    handle = get_handle(uri)
    jobid = flux.job.JobID(handle.rpc("sched-fluxion-resource.next_jobid").get()["jobid"])
    payload = {"cmd": "allocate_orelse_reserve", "jobid": jobid, "jobspec": jobspec}
    return handle.rpc("sched-fluxion-resource.match", payload).get()


def flux_sched_resource_feasibility_check(
    jobspec_dict: dict, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Check if a jobspec is satisfiable without performing an allocation.

    Args:
        jobspec_dict: A dictionary representing the jobspec requirements.
        uri: Optional Flux URI.
    Returns:
        The response from the feasibility check.
    """
    handle = get_handle(uri)
    return handle.rpc("feasibility.check", {"jobspec": jobspec_dict}).get()


def flux_sched_resource_update(
    jobid: Union[int, str],
    res_json: str,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Update the resource database for a specific job with a new resource set (R).

    Args:
        jobid: The job identifier (string or integer).
        res_json: A JSON string representing the resource (R) to update.
        uri: Optional Flux URI.
    Returns:
        Dictionary with updated resource metadata.
    """
    handle = get_handle(uri)
    payload = {"jobid": flux.job.JobID(jobid), "R": res_json}
    return handle.rpc("sched-fluxion-resource.update", payload).get()


def flux_sched_resource_cancel(
    jobid: Union[int, str], uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Cancel an allocated or reserved job.

    Args:
        jobid: The job identifier (string or integer).
        uri: Optional Flux URI.
    Returns:
        Result of the cancellation RPC.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.cancel", {"jobid": flux.job.JobID(jobid)}).get()


def flux_sched_resource_partial_cancel(
    jobid: Union[int, str],
    rv1exec_json: str,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Partially cancel an allocated job using a specific resource subset.

    Args:
        jobid: The job identifier (string or integer).
        rv1exec_json: A JSON string representing the resources to release.
        uri: Optional Flux URI.
    Returns:
        Response from the partial-cancel RPC.
    """
    handle = get_handle(uri)
    payload = {"jobid": flux.job.JobID(jobid), "R": rv1exec_json}
    return handle.rpc("sched-fluxion-resource.partial-cancel", payload).get()


def flux_sched_resource_find(
    criteria: str,
    find_format: Optional[str] = None,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Find resources matching specific criteria (e.g., 'status=up').

    Args:
        criteria: Compound expression for matching.
        find_format: Optional writer format (e.g., 'json').
        uri: Optional Flux URI.
    Returns:
        Dictionary containing matched resources 'R'.
    """
    handle = get_handle(uri)
    payload = {"criteria": criteria}
    if find_format:
        payload["format"] = find_format
    return handle.rpc("sched-fluxion-resource.find", payload).get()


def flux_sched_resource_set_property(
    resource_path: str,
    key_val: str,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Set a property (key=value) for a specific resource vertex.

    Args:
        resource_path: The path to the vertex.
        key_val: The property string in 'key=value' format.
        uri: Optional Flux URI.
    Returns:
        Result of the set operation.
    """
    handle = get_handle(uri)
    payload = {"sp_resource_path": resource_path, "sp_keyval": key_val}
    return handle.rpc("sched-fluxion-resource.set_property", payload).get()


def flux_sched_resource_remove_property(
    resource_path: str, key: str, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Remove a property key for a specified resource vertex.

    Args:
        resource_path: The path to the vertex.
        key: The key to remove.
        uri: Optional Flux URI.
    Returns:
        Result of the removal operation.
    """
    handle = get_handle(uri)
    payload = {"resource_path": resource_path, "key": key}
    return handle.rpc("sched-fluxion-resource.remove_property", payload).get()


def flux_sched_resource_get_property(
    resource_path: str, key: str, uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Get the values for a specified resource and property key.

    Args:
        resource_path: The path to the vertex.
        key: The property key.
        uri: Optional Flux URI.
    Returns:
        Dictionary containing 'values'.
    """
    handle = get_handle(uri)
    payload = {"gp_resource_path": resource_path, "gp_key": key}
    return handle.rpc("sched-fluxion-resource.get_property", payload).get()


def flux_sched_resource_status(
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Retrieve status for resource vertices (up, down, allocated).

    Args:
        uri: Optional Flux URI.
    Returns:
        Matched resources for status criteria.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.status").get()


def flux_sched_resource_set_status(
    resource_path: str,
    status: str,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Manually set the status (up/down) of a resource vertex.

    Args:
        resource_path: The path to the vertex.
        status: Desired status ('up' or 'down').
        uri: Optional Flux URI.
    Returns:
        Result of the status change.
    """
    handle = get_handle(uri)
    payload = {"resource_path": resource_path, "status": status}
    return handle.rpc("sched-fluxion-resource.set_status", payload).get()


def flux_sched_resource_stats(
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Retrieve performance and graph statistics.

    Args:
        uri: Optional Flux URI.
    Returns:
        Dictionary of graph metrics and match timing.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.stats-get").get()


def flux_sched_resource_stats_clear(
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Clear performance statistics for the module.

    Args:
        uri: Optional Flux URI.
    Returns:
        Confirmation of clear operation.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.stats-clear").get()


def flux_sched_resource_params(
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Display current configuration parameters of the module.

    Args:
        uri: Optional Flux URI.
    Returns:
        Dictionary of module parameters.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.params").get()


def flux_sched_resource_ns_info(
    rank: int,
    type_name: str,
    identity: int,
    uri: Annotated[Optional[str], "unique resource identifier"] = None,
) -> dict:
    """
    Get the remapped (namespaced) ID given a raw ID seen by the reader.

    Args:
        rank: Execution target rank.
        type_name: Resource type (e.g., 'core', 'gpu').
        identity: Raw ID seen by the reader.
        uri: Optional Flux URI.
    Returns:
        Dictionary containing the remapped 'id'.
    """
    handle = get_handle(uri)
    payload = {"rank": rank, "type-name": type_name, "id": identity}
    return handle.rpc("sched-fluxion-resource.ns-info", payload).get()


def flux_sched_resource_info(
    jobid: Union[int, str], uri: Annotated[Optional[str], "unique resource identifier"] = None
) -> dict:
    """
    Retrieve allocation info and overhead for a specific job.

    Args:
        jobid: Job identifier (string or integer).
        uri: Optional Flux URI.
    Returns:
        Job resource status and timing data.
    """
    handle = get_handle(uri)
    return handle.rpc("sched-fluxion-resource.info", {"jobid": flux.job.JobID(jobid)}).get()
