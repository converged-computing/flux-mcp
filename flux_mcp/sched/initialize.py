import json
from typing import Optional

import flux_mcp.sched.graph as graph


def flux_sched_init_graph(graph_json: str, options_json: Optional[str] = None) -> str:
    """
    Initializes the scheduler resource graph.

    Args:
        graph_json: A JSON string representing the JGF resource graph.
        options_json: Optional JSON string for loader options (load_format, etc).
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

        return json.dumps({"success": True, "message": "Resource Graph initialized successfully."})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
