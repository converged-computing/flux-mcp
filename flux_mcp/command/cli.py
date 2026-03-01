import copy
import os
import subprocess
from typing import Annotated, Any, Dict, List, Optional

FluxCommandResult = Annotated[
    Dict[str, Any],
    "A structured result containing 'success' (bool), 'stdout' (str), 'stderr' (str), and 'exit_code' (int).",
]


# Flux exec and archive are not available in the Python sdk.
def run_flux_cli(args: List[str], uri: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Executes a Flux CLI command via subprocess.

    Args:
        args: List of command arguments (e.g., ['exec', '-r', '0', 'hostname']).
        uri: Optional Flux URI to target a specific instance.
    """
    cmd = ["flux"]
    environ = copy.deepcopy(dict(os.environ))
    if uri:
        environ["FLUX_URI"] = uri
    cmd.extend(args)

    return subprocess.run(cmd, env=environ, capture_output=True, text=True, check=False)
