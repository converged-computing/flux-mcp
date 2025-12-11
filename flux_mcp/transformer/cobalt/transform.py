import re
import shlex
from datetime import datetime, timedelta

from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class CobaltScript(Script):
    """
    A helper class for Cobalt. Unused as Cobalt uses command-line flags.
    """

    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = ""  # No directive prefix


def priority_to_cobalt_priority(priority_str):
    """
    Cobalt does not typically expose a direct user-facing priority flag.
    This is handled by queue policies. This function is a no-op.
    """
    return None


def cobalt_priority_to_priority(cobalt_priority):
    """
    Cobalt does not have a parsable priority flag, so this always returns normal.
    """
    return "normal"


def seconds_to_cobalt_walltime(total_seconds):
    """
    Converts integer seconds to Cobalt's HH:MM:SS walltime format.
    Cobalt -t flag also accepts minutes directly, but HH:MM:SS is more explicit.
    """
    if not isinstance(total_seconds, int) or total_seconds <= 0:
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"


def cobalt_walltime_to_seconds(time_str):
    """
    Converts Cobalt HH:MM:SS walltime string back to integer seconds.
    """
    if not time_str:
        return None
    try:
        # Can be HH:MM:SS or just minutes
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return int(timedelta(hours=h, minutes=m, seconds=s).total_seconds())
        elif len(parts) == 1:
            return int(parts[0]) * 60
        return None
    except (ValueError, IndexError):
        return None


def epoch_to_cobalt_begin_time(epoch_seconds):
    """
    Converts Unix epoch to Cobalt's begin time format for the '--at' flag.
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds <= 0:
        return None
    # A common supported format is YYYY-MM-DDTHH:MM:SS
    return datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%dT%H:%M:%S")


def cobalt_begin_time_to_epoch(time_str):
    """
    Converts a Cobalt begin time string back to Unix epoch.
    """
    if not time_str:
        return None
    try:
        return int(datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S").timestamp())
    except (ValueError, IndexError):
        return None


def parse_cobalt_command(command_lines, spec):
    """
    Parses a command line from within a Cobalt script body.
    """
    if not command_lines:
        return []

    # Find the first non-empty, non-comment line, which is likely the main command
    main_command = ""
    for line in command_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            main_command = line
            break

    if not main_command:
        return []

    parts = shlex.split(main_command)

    # The common launcher on ALCF systems is 'aprun'
    if parts and parts[0] in ("aprun"):
        parts = parts[1:]

    if parts and parts[0] in ("singularity", "apptainer") and parts[1] == "exec":
        spec.container_image = parts[2]
        parts = parts[3:]

    return parts


class CobaltTransformer(TransformerBase):
    """
    Transforms a JobSpec to/from a Cobalt submission script.
    Note: Cobalt uses command-line flags to qsub, not in-script directives.
    This transformer generates a "runner" script that calls qsub.
    """

    def convert(self, spec):
        """
        Converts a JobSpec into a self-submitting Cobalt script string.
        """
        job_name = spec.job_name or JobNamer().generate()

        # Build the qsub command line
        qsub_cmd = ["qsub"]
        qsub_cmd.extend(["-A", spec.account] if spec.account else [])
        qsub_cmd.extend(["-q", spec.queue] if spec.queue else [])
        qsub_cmd.extend(["-n", str(spec.num_nodes)])

        # Cobalt uses --proccount for total MPI ranks
        if spec.num_tasks > 1:
            qsub_cmd.extend([f"--proccount", str(spec.num_tasks)])

        wt = seconds_to_cobalt_walltime(spec.wall_time)
        if wt:
            qsub_cmd.extend(["-t", wt])

        bt = epoch_to_cobalt_begin_time(spec.begin_time)
        if bt:
            qsub_cmd.extend(["--at", bt])

        # Dependencies are specified with a colon-separated list of job IDs
        if spec.depends_on:
            dep_str = (
                ":".join(spec.depends_on) if isinstance(spec.depends_on, list) else spec.depends_on
            )
            qsub_cmd.extend(["--dependencies", dep_str])

        # Node constraints and GPU type are handled by --attrs
        attrs = list(spec.constraints)
        if spec.gpu_type:
            attrs.append(f"gpu_type={spec.gpu_type}")
        if attrs:
            qsub_cmd.extend(["--attrs", ":".join(attrs)])

        # -O sets the prefix for output/error files, which is derived from the job name.
        qsub_cmd.extend(["-O", job_name])
        # If explicit files are given, they override the prefix.
        if spec.output_file:
            qsub_cmd.extend(["-o", spec.output_file])
        if spec.error_file:
            qsub_cmd.extend(["-e", spec.error_file])

        # Email notifications
        if spec.mail_user:
            qsub_cmd.extend(["-M", spec.mail_user])
            # Cobalt has a simple '--notify user' flag, equivalent to ALL in Slurm.
            if spec.mail_type:
                qsub_cmd.append("--notify user")

        if spec.environment:
            for k, v in spec.environment.items():
                qsub_cmd.extend(["--env", f"{k}={v}"])

        # Note: Cobalt exclusive access is often handled by queue policy or `--mode script`.
        # We omit a direct flag to avoid conflicting with system-specific setups.

        # Build the script that will be executed on the compute node
        exec_script_parts = ["#!/bin/bash", ""]

        # The common launcher for Cobalt is aprun
        aprun_cmd = ["aprun"]

        # Match aprun geometry to qsub submission
        # -n total processes, -N processes per node
        aprun_cmd.extend(["-n", str(spec.num_tasks)])
        aprun_cmd.extend(["-N", str(spec.cpus_per_task)])

        # If spec.script is defined, it takes precedence over executable/arguments
        if spec.script:
            exec_script_parts.extend(spec.script)
        else:
            aprun_cmd = spec.derive_command(aprun_cmd)
            exec_script_parts.append(" ".join(aprun_cmd))

        exec_script = "\n".join(exec_script_parts)

        # Combine into a self-submitting script using a "here document"
        runner_script = ["#!/bin/bash", " ".join(qsub_cmd) + " << EOF", exec_script, "EOF"]
        return "\n".join(runner_script)

    def _parse(self, content, return_unhandled=False):
        """
        Parses a self-submitting Cobalt script into a JobSpec.
        """
        spec = JobSpec()
        not_handled = set()

        # Find the qsub line and the script body
        qsub_line = ""
        script_body = []
        in_script_body = False

        qsub_re = re.compile(r"qsub\s+(.+?)<<\s*EOF")

        for line in content.splitlines():
            m = qsub_re.search(line)
            if m:
                qsub_line = m.group(1)
                in_script_body = True
                continue

            if in_script_body and line.strip() != "EOF":
                script_body.append(line)

        # Parse the qsub command line flags
        if qsub_line:
            args = shlex.split(qsub_line)
            i = 0
            while i < len(args):
                arg = args[i]

                # Logic to handle both `--key value` and `--key=value`
                key, value = None, None
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    i += 1
                else:
                    key = arg
                    # Check if next part is a value or another flag
                    if i + 1 < len(args) and not args[i + 1].startswith("-"):
                        value = args[i + 1]
                        i += 2
                    else:  # It's a boolean flag
                        value = True
                        i += 1

                key = key.lstrip("-")

                if key == "A":
                    spec.account = value
                elif key == "q":
                    spec.queue = value
                elif key == "n":
                    spec.num_nodes = int(value)
                elif key == "t":
                    spec.wall_time = cobalt_walltime_to_seconds(value)
                elif key == "proccount":
                    spec.num_tasks = int(value)
                elif key == "O":
                    # This sets the job name AND the output file prefix
                    spec.job_name = value
                    if not spec.output_file:
                        spec.output_file = f"{value}.output"
                    if not spec.error_file:
                        spec.error_file = f"{value}.error"
                elif key == "o":
                    spec.output_file = value
                elif key == "e":
                    spec.error_file = value
                elif key == "at":
                    spec.begin_time = cobalt_begin_time_to_epoch(value)
                elif key == "dependencies":
                    spec.depends_on = value.split(":")
                elif key == "attrs":
                    for attr in value.split(":"):
                        if attr.startswith("gpu_type="):
                            spec.gpu_type = attr.split("=", 1)[1]
                        else:
                            spec.constraints.append(attr)
                elif key == "M":
                    spec.mail_user = value
                elif key == "notify" and value == "user":
                    spec.mail_type = ["ALL"]  # Simple mapping
                elif key == "env":
                    env_key, env_val = value.split("=", 1)
                    spec.environment[env_key] = env_val
                else:
                    not_handled.add(key)

        # We again assume a block of text here.
        if script_body:
            spec.script = script_body

        # Parse the execution command from the script body
        parts = parse_cobalt_command(spec.script, spec)
        if parts:
            # Need to parse aprun args to get cpus_per_task
            temp_args = parts.copy()
            # This is a bit simplistic, but covers the common case
            try:
                if "-N" in temp_args:
                    idx = temp_args.index("-N")
                    spec.cpus_per_task = int(temp_args[idx + 1])
                    temp_args.pop(idx)
                    temp_args.pop(idx)
                # Also handle -n for total tasks if --proccount wasn't used
                if "-n" in temp_args and spec.num_tasks == 1:
                    idx = temp_args.index("-n")
                    spec.num_tasks = int(temp_args[idx + 1])
                    temp_args.pop(idx)
                    temp_args.pop(idx)
            except (ValueError, IndexError):
                pass  # Ignore if parsing aprun fails

            if temp_args:
                spec.executable = temp_args[0]
                spec.arguments = temp_args[1:]

        if return_unhandled:
            return not_handled
        return spec
