import json
import os
import subprocess
import time
from typing import Annotated, Any, Dict, List, Mapping, Optional, Union

import flux
import flux.job

import flux_mcp.utils as utils
from flux_mcp.command.cli import FluxCommandResult, run_flux_cli


def flux_archive_create(
    paths: Annotated[List[str], "A list of files or directories to archive into the KVS."],
    archive_name: Annotated[
        str, "The identifier for the archive (e.g., 'logs', 'results')."
    ] = "main",
    directory: Annotated[
        Optional[str], "Change to this directory before reading paths (equivalent to -C)."
    ] = None,
    preserve: Annotated[bool, "If True, preserve the archive data over Flux restarts."] = False,
    overwrite: Annotated[bool, "If True, overwrite an existing archive of the same name."] = False,
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> FluxCommandResult:
    """
    Creates a KVS file archive for persistent storage of job files or metadata.

    Use this tool to 'snapshot' important files (like configuration, logs, or small results)
    into the Flux Key-Value Store. This makes the data available even if the original
    files are moved or the filesystem is temporary.

    Args:
        paths: List of relative or absolute file/directory paths to include.
        archive_name: Target name for the KVS entry.
        directory: Optional base directory. If provided, all relative 'paths' will be resolved from here.
        preserve: Enables data preservation across instance restarts.
        overwrite: Forces overwriting if the archive name already exists.
        uri: Optional Flux handle URI.

    Returns:
        A dictionary containing the success status and the raw output from the Flux CLI.
    """
    args = ["archive", "create"]

    if archive_name:
        args.extend(["--name", archive_name])

    if directory:
        # Security/Sanity Check: Ensure the directory exists
        abs_dir = Path(directory).resolve()
        if not abs_dir.exists():
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Context directory '{directory}' not found.",
                "exit_code": 1,
            }
        args.extend(["-C", str(abs_dir)])

    if preserve:
        args.append("--preserve")

    if overwrite:
        args.append("--overwrite")

    args.extend(paths)

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


def flux_archive_remove(
    archive_name: Annotated[str, "The name of the KVS archive to delete."],
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> FluxCommandResult:
    """
    Deletes a specific file archive from the Flux KVS.

    Args:
        archive_name: The identifier of the archive to be destroyed.
        uri: Optional Flux handle URI.
    """
    try:
        result = run_flux_cli(["archive", "remove", archive_name], uri)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": 1}


def flux_archive_list(
    uri: Annotated[Optional[str], "The Flux connection URI."] = None,
) -> FluxCommandResult:
    """
    Lists all file archives currently stored in the Flux KVS.
    """
    try:
        result = run_flux_cli(["archive", "list"], uri)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": 1}
