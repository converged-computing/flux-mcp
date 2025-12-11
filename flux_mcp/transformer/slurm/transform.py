#!/usr/bin/env python3

import re
import shlex
from datetime import datetime, timedelta

import flux_mcp.utils as utils
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class SlurmScript(Script):
    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#SBATCH"


def seconds_to_slurm_time(seconds):
    """
    Converts an integer number of seconds into a Slurm-compatible time string.
    Format: [days-]hours:minutes:seconds
    """
    # This shouldn't happen, but we return 0 so we use the default.
    if not seconds or seconds <= 0:
        return None

    # 86400 seconds in a day
    days, seconds_rem = divmod(seconds, 86400)
    hours, seconds_rem = divmod(seconds_rem, 3600)
    minutes, seconds = divmod(seconds_rem, 60)

    # Format the output
    if days > 0:
        # D-HH:MM:SS
        return f"{days}-{hours:02d}:{minutes:02d}:{seconds:02d}"

    # HH:MM:SS
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def epoch_to_slurm_begin_time(epoch_seconds: int) -> str:
    """
    Converts a Unix epoch timestamp (integer seconds) into a Slurm-compatible
    begin time string.
    Format: YYYY-MM-DDTHH:MM:SS
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds < 0:
        raise ValueError("begin_time must be a positive integer (Unix epoch seconds).")

    return datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%dT%H:%M:%S")


def slurm_time_to_seconds(time_str):
    if not time_str:
        return None
    days = 0

    # Allow this to error - we can catch after
    if "-" in time_str:
        day_part, time_str = time_str.split("-", 1)
        days = int(day_part)

    h = 0
    m = 0
    s = 0
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = map(int, parts)
    elif len(parts) == 2:
        h, s = 0, 0
        m, s = map(int, parts)
    elif len(parts) == 1:
        h, s = 0, 0
        m = int(parts[0])
    return int(timedelta(days=days, hours=h, minutes=m, seconds=s).total_seconds())


def parse_slurm_command(command_lines, spec):
    """
    Pars a slurm command into parts.
    """
    # We use the last command line as the primary execution logic
    main_command = command_lines[-1]
    parts = shlex.split(main_command)

    # Unwrap common launchers
    if parts and parts[0] == "srun":
        parts = parts[1:]

    if parts and parts[0] in ("singularity", "apptainer") and parts[1] == "exec":
        spec.container_image = parts[2]
        # The rest is the command inside the container
        parts = parts[3:]

    # Handle input redirection
    if "<" in parts:
        try:
            idx = parts.index("<")
            spec.input_file = parts[idx + 1]
            # Remove '<' and the filename from the arguments
            parts.pop(idx)
            parts.pop(idx)
        except (ValueError, IndexError):
            pass
    return parts


def slurm_begin_time_to_epoch(time_str):
    """
    Converts a Slurm begin time string to Unix epoch seconds.
    """
    if not time_str:
        return None

    # Asking for now is akin to not setting (at least I think)
    if "now" in time_str.lower():
        return None

    # Attempt to parse the specific ISO-like format we generate.
    # Allow this to error.
    dt_object = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
    return int(dt_object.timestamp())


def priority_to_nice(priority):
    """
    Maps a semantic priority string ("high") to a Slurm nice value (-100).
    """
    # Higher nice value == LOWER priority
    mapping = {
        "low": 1000,
        "normal": 0,
        "high": -100,
        "urgent": -1000,
    }
    # Default to 'normal' (nice=0) if the string is None or not in the map
    return mapping.get(priority, 0)


def nice_to_priority(nice_value):
    """
    Maps a Slurm nice value (e.g., -100) back to a semantic string ("high").
    """
    if nice_value is None or nice_value == 0:
        return "normal"
    if nice_value > 0:
        return "low"

    # For negative values, we can create tiers
    if -1000 < nice_value < 0:
        return "high"

    # For nice_value <= -1000
    return "urgent"


class SlurmTransformer(TransformerBase):
    """
    A Slurm Transformer for converting a generic JobSpec into a Slurm batch script.

    This transformer maps the fields of the JobSpec to their corresponding #SBATCH
    directives and constructs a runnable script.
    """

    def convert(self, spec) -> str:
        """
        Convert a normalized jobspec to a Slurm batch script.
        """
        script = SlurmScript()
        if spec.job_name:
            script.add("job-name", spec.job_name)

        # Job Identity & Accounting
        script.add("account", spec.account)

        # I/O
        script.add("output", spec.output_file)
        script.add("error", spec.error_file)
        if spec.mail_user:
            script.add("mail-user", spec.mail_user)
            mail_type_str = ",".join(spec.mail_type) if spec.mail_type else "ALL"
            script.add("mail-type", mail_type_str)

        # Resource Requests
        script.add("nodes", spec.num_nodes)
        script.add("ntasks", spec.num_tasks)
        script.add("cpus-per-task", spec.cpus_per_task)
        if spec.gpus_per_task and spec.gpus_per_task > 0:
            if spec.gpu_type:
                script.add("gres", f"gpu:{spec.gpu_type}:{spec.gpus_per_task}")
            else:
                script.add("gpus-per-task", spec.gpus_per_task)
        elif spec.generic_resources:
            script.add("gres", spec.generic_resources)

        # Slurm's --mem-per-cpu I think is how to specify memory per task
        if spec.mem_per_task:
            if spec.num_tasks == 1:
                script.add("mem", spec.mem_per_task)
            else:
                script.add("mem-per-cpu", spec.mem_per_task)

        # Scheduling and Constraints
        script.add("time", seconds_to_slurm_time(spec.wall_time))

        # Disable partition for now - can't map to another cluster and get a match
        # script.add("partition", spec.queue)

        # The 'nice' value in Slurm influences the job's priority.
        # A higher value means lower priority. This is an imperfect mapping.
        # We also support qos and priority directly, but `nice` is a fallback.
        if spec.priority:
            if isinstance(spec.priority, str):
                # Assumes priority string is a QoS name
                script.add("qos", spec.priority)
            elif isinstance(spec.priority, int):
                # Assumes priority is a numeric `nice` value.
                nice_val = spec.priority
                if nice_val != 0:
                    script.add("nice", nice_val)

        if spec.exclusive_access:
            script.add_flag("exclusive")

        if spec.constraints:
            constraint_str = ",".join(spec.constraints)
            script.add("constraint", constraint_str)

        if spec.begin_time:
            script.add("begin", epoch_to_slurm_begin_time(spec.begin_time))
        script.add("chdir", spec.working_directory)

        if spec.requeue is False:
            script.add_flag("no-requeue")

        if spec.array_spec:
            script.add("array", spec.array_spec)

        if spec.nodelist:
            script.add("nodelist", spec.nodelist)

        if spec.exclude_nodes:
            script.add("exclude", spec.exclude_nodes)

        # Not sure how these would map.
        # if spec.licenses:
        #    script.add("licenses", spec.licenses)

        # Dependencies
        if spec.depends_on:
            if isinstance(spec.depends_on, list):
                # Assuming a dependency type of 'afterok' as a default
                dependency_str = ":".join(spec.depends_on)
                script.add(f"dependency", f"afterok:{dependency_str}")
            else:
                script.add(f"dependency", spec.depends_on)

        # I am just adding this for readability
        script.newline()

        # Environment Variables
        if spec.environment:
            for key, value in spec.environment.items():
                script.add_line(f"export {key}='{value}'")
            script.newline()

        # Execution logic
        container_exec = []

        # Handle containerization if an image is specified
        if spec.container_image:
            # Prepend with singularity/apptainer exec
            container_exec = ["singularity", "exec", spec.container_image]

        command_parts = container_exec + spec.script

        # Handle I/O redirection
        if spec.input_file:
            command_parts.append(f"< {spec.input_file}")
        for line in command_parts:
            script.add_line(line)
        script.newline()
        return script.render()

    def _parse(self, filename, return_unhandled=False):
        """
        Parses the content of a Slurm batch script into a JobSpec object.

        If return_unresolved is True, we instead return the arguments we could
        not parse.
        """
        spec = JobSpec()

        # Heuristic: The last non-comment/non-export line is the main command.
        command_lines = []

        # Directives not handled
        not_handled = set()

        # This regex is only used to identify a directive line
        sbatch_line_re = re.compile(r"^\s*#SBATCH")
        script_content = utils.read_file(filename)

        for line in script_content.splitlines():
            if not line.strip():
                continue

            # 1. Parse SBATCH directives or "other stuff" is just script
            if sbatch_line_re.match(line):

                # Isolate the directives part of the line
                args_str = line.split("#SBATCH", 1)[1].strip()

                # Get rid of trailing comments on the same line
                if "#" in args_str:
                    args_str = args_str.split("#", 1)[0].strip()

                # Use shlex to handle quoted arguments and spaces correctly
                directives = shlex.split(args_str)

                # Iterate through all directives found on the line
                i = 0
                while i < len(directives):
                    directive = directives[i]
                    key, value = None, None

                    if "=" in directive:
                        # Handles --key=value
                        key, value = directive.split("=", 1)
                        key = key.lstrip("-")
                        i += 1

                    elif directive.startswith("--"):
                        key = directive.lstrip("-")
                        if i + 1 < len(directives) and not directives[i + 1].startswith("-"):
                            value = directives[i + 1]
                            i += 2
                        else:
                            value = True
                            i += 1

                    # Logic for packed flags
                    elif directive.startswith("-") and len(directive) > 2:
                        # Handles packed short-form flags like -N16 or -t01:00:00
                        flag_char = directive[1]
                        # Check if this character is a known flag that takes a value
                        if flag_char in "Nntcpt":
                            key = flag_char
                            value = directive[2:]
                            i += 1

                        # Not a known packed flag, skip
                        else:
                            i += 1
                            continue

                    elif directive.startswith("-"):
                        key = directive.lstrip("-")
                        if i + 1 < len(directives) and not directives[i + 1].startswith("-"):
                            value = directives[i + 1]
                            i += 2
                        else:
                            value = True
                            i += 1
                    else:
                        i += 1
                        continue

                    # Let this error for nice for now...
                    if key == "nice":
                        spec.priority = nice_to_priority(int(value))
                    elif key in ("qos", "priority"):
                        spec.priority = value  # Store QoS name or priority string

                    # Map Slurm keys to JobSpec attributes
                    elif key in ("J", "job-name", "job"):
                        spec.job_name = value
                    elif key in ("A", "account"):
                        spec.account = value
                    elif key in ("o", "output", "out"):
                        spec.output_file = value
                    elif key in ("e", "error", "err"):
                        spec.error_file = value
                    elif key in ("N", "nodes"):
                        spec.num_nodes = int(value)
                    elif key in ("n", "ntasks", "tasks"):
                        spec.num_tasks = int(value)
                    elif key in ("c", "cpus-per-task"):
                        spec.cpus_per_task = int(value)
                    elif key == "gpus-per-task":
                        spec.gpus_per_task = int(value)
                    elif key == "gpus":
                        # Handles --gpus=a100:1 or --gpus=2
                        parts = value.split(":")
                        if len(parts) == 1 and parts[0].isdigit():
                            spec.gpus_per_task = int(parts[0])
                        elif len(parts) == 2:
                            spec.gpu_type = parts[0]
                            spec.gpus_per_task = int(parts[1])
                    elif key == "gres":
                        if "gpu" in value:
                            # Handles --gres=gpu:a100:2 or --gres=gpu:2
                            parts = value.split(":")
                            if len(parts) == 2:  # gpu:2
                                spec.gpus_per_task = int(parts[1])
                            elif len(parts) == 3:  # gpu:a100:2
                                spec.gpu_type = parts[1]
                                spec.gpus_per_task = int(parts[2])
                        else:
                            spec.generic_resources = value
                    elif key in ("mem-per-cpu", "mem"):
                        spec.mem_per_task = value
                    elif key in ("p", "q", "partition", "paritition", "part"):
                        spec.queue = value
                    elif key in ("exclusive", "exclusiv"):
                        spec.exclusive_access = True
                    elif key in ("D", "chdir", "workdir"):
                        spec.working_directory = value
                    elif key in ("t", "time"):
                        spec.wall_time = slurm_time_to_seconds(value)
                    elif key == "begin":
                        spec.begin_time = slurm_begin_time_to_epoch(value)
                    elif key in ("d", "dependency", "depend"):
                        dep_parts = value.split(":")
                        spec.depends_on = dep_parts[-1] if len(dep_parts) == 2 else dep_parts[1:]
                    elif key in ("a", "array"):
                        spec.array_spec = value
                    elif key == "mail-user":
                        spec.mail_user = value
                    elif key == "mail-type":
                        spec.mail_type = value.split(",")
                    elif key == "requeue":
                        spec.requeue = True
                    elif key == "no-requeue":
                        spec.requeue = False
                    elif key in ("w", "nodelist"):
                        spec.nodelist = value
                    elif key in ("x", "exclude"):
                        spec.exclude_nodes = value
                    elif key == "image":
                        spec.container_image = value
                    elif key in ("L", "licenses", "license"):
                        spec.licenses = value
                    elif key == "input":
                        spec.input_file = value
                    elif key in ("C", "constraint", "constrain", "constaring"):
                        if isinstance(value, list):
                            spec.constraints.extend(value)
                        else:
                            spec.constraints.append(value)

                    elif key == "ntasks-per-node":
                        # This is a constraint, not a direct resource request in the same way.
                        # For now, we can add it to the generic constraints list.
                        spec.constraints.append(f"ntasks-per-node={value}")
                    elif key == "ntasks-per-socket":
                        spec.constraints.append(f"ntasks-per-socket={value}")
                    elif key == "time-min":
                        # This is usually a partition/QoS setting, but we can note it.
                        not_handled.add(f"{key}={value}")
                    elif key == "signal":
                        not_handled.add(f"{key}={value}")
                    elif key == "propagate":
                        not_handled.add(f"{key}={value}")
                    else:
                        not_handled.add(key)
                continue

            # 3. Parse environment variables
            if line.lower().startswith("export "):
                env_match = re.match(r"export\s+([^=]+)=(.*)", line)
                if env_match:
                    env_key, env_val = env_match.groups()
                    # Strip quotes from value
                    spec.environment[env_key] = env_val.strip("'\"")

            # Do not add additional comments
            if line.startswith("#"):
                continue

            # 4. Assume any other non-empty line is part of the command
            command_lines.append(line)

        # 5. Deconstruct the main command line
        # Note this assumes we can include commands as a block
        # If we generate this to Kubernetes we need to create a configmap that is executed instead.
        if command_lines:
            spec.script = command_lines

        if return_unhandled:
            return not_handled
        return spec
