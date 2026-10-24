import os
import shutil
import subprocess
from typing import Annotated, Any, Dict, List, Optional

import flux_mcp.utils as utils

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
    cmd = [shutil.which("flux") or "flux"]

    # flux exec passes its environment to the remote commands, so give it the
    # user environment rather than the server's.
    environ = utils.user_environment()
    if uri or os.environ.get("FLUX_URI"):
        environ["FLUX_URI"] = uri or os.environ["FLUX_URI"]
    cmd.extend(args)

    return subprocess.run(cmd, env=environ, capture_output=True, text=True, check=False)
