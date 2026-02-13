import json
from typing import Annotated

import flux.resource

from flux_mcp.job.core import get_handle


def flux_resource_list(uri: Annotated[str, "unique resource identifier"] = None):
    """
    List Flux resources for a cluster based on a URI of interest
    Args:
        uri: Optional Flux URI. If not provided, uses local instance.
    Returns:
        JSON string containing resources free/up associated with the uri.
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
