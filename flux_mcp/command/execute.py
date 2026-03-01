import json
import os
import subprocess
import time
from typing import Annotated, Any, Dict, List, Mapping, Optional, Union

import flux
import flux.job

import flux_mcp.utils as utils
from flux_mcp.command.cli import FluxCommandResult, run_flux_cli


def flux_exec_command(
    command: Annotated[List[str], "The command to run (e.g., ['ls', '-l'])."],
    ranks: Annotated[str, "The ranks to target (e.g., '0', 'all', '0-2')."] = "all",
    directory: Annotated[Optional[str], "The directory to execute the command in."] = None,
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> FluxCommandResult:
    """
    Runs a command across specific ranks in the Flux instance using 'flux exec'.
    """
    args = ["exec", "-r", ranks]

    if directory:
        args.extend(["-D", directory])  # -D is the 'flux exec' flag for working directory

    args.extend(command)

    try:
        result = run_flux_cli(args, uri)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": 1}
