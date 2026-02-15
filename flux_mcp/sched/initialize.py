import json
from typing import Annotated, Any, Dict, Optional

import flux_mcp.sched.graph as graph

# Define custom type for MCP schema clarity
GraphInitResult = Annotated[
    Dict[str, Any],
    "A structured result containing 'success' (bool), a descriptive 'message' (str), "
    "and an 'error' (str) field if the operation failed.",
]


def flux_sched_init_graph(
    graph_json: Annotated[
        str,
        "A JSON string representing the JGF (JSON Graph Format) resource graph defining the cluster architecture.",
    ],
    options_json: Annotated[
        Optional[str],
        "Optional JSON string for loader configuration. Typically includes 'load_format', 'prune_filters', and 'policy'.",
    ] = None,
) -> GraphInitResult:
    """
    Initializes or resets the Fluxion scheduler's internal resource graph.

    This function forces the creation of a new resource client and populates it
    with the provided graph definition. This is a critical setup step for
    schedulers that manage custom or simulated resource topologies.

    Args:
        graph_json: The JGF data defining nodes, cores, and their relationships.
        options_json: Advanced configuration for the loader. If not provided,
            defaults to a standard JGF loader with core pruning and containment
            subsystems.

    Returns:
        A dictionary indicating if the graph was successfully loaded into
        the scheduler memory.
    """
    try:
        # An init is going to force a new graph
        cli = graph.get_resource_client(force_new=True)

        # Choose default options if not provided
        if not options_json:
            options_json = json.dumps(
                {
                    "load_format": "jgf",
                    "prune_filters": "ALL:core",
                    "subsystems": "containment",
                    "policy": "high",
                }
            )

        cli.initialize(graph_json, options_json)

        return {"success": True, "message": "Resource Graph initialized successfully."}

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "There was an error initializing the graph",
        }
