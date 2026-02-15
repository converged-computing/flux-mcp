import json
from typing import Annotated, Any, Dict, Optional

import flux.resource

from flux_mcp.job.core import get_handle

# This should populate the outputSchema
ResourceStatus = Annotated[
    Dict[str, Any],
    "A detailed report of cluster resource availability. "
    "The 'up' key represents the total capacity currently online/active. "
    "The 'free' key represents capacity that is currently idle and available for immediate job scheduling. "
    "Both sections include counts for cores, gpus, and nodes, as well as specific hostnames and ranks.",
]


def flux_resource_list(
    uri: Annotated[
        Optional[str],
        "The Flux connection URI (e.g., 'local:///run/flux/local'). Defaults to the local instance.",
    ] = None,
) -> ResourceStatus:
    """
    Retrieves a detailed inventory of available and active resources within a Flux instance.

    This tool is essential for pre-flight checks before job submission to ensure the
    cluster has sufficient 'free' resources (cores, GPUs, nodes) to satisfy a
    job's requirements.

    Args:
        uri: Optional unique resource identifier for the Flux instance. If omitted,
             the function connects to the default local Flux handle.

    Returns:
        A dictionary containing two primary keys: 'free' and 'up'.
        Each key maps to a sub-dictionary containing:
            - 'cores' (int): Number of CPU cores.
            - 'gpus' (int): Number of GPU devices.
            - 'nodes' (int): Total number of distinct compute nodes.
            - 'hosts' (list[str]): List of hostnames involved.
            - 'ranks' (list[int]): Flux ranks associated with these resources.
            - 'properties' (dict): Arbitrary metadata/attributes assigned to the resources.
    """
    handle = get_handle(uri)
    listing = flux.resource.list.resource_list(handle).get()

    return {
        "free": {
            "cores": listing.free.ncores,
            "gpus": listing.free.ngpus,
            "nodes": listing.free.nnodes,
            "hosts": list(listing.free.nodelist),
            "ranks": list(listing.free.ranks),
            "properties": json.loads(listing.free.get_properties()),
        },
        "up": {
            "cores": listing.up.ncores,
            "gpus": listing.up.ngpus,
            "nodes": listing.up.nnodes,
            "hosts": list(listing.up.nodelist),
            "ranks": list(listing.up.ranks),
            "properties": json.loads(listing.up.get_properties()),
        },
    }
