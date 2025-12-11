import re
import shlex
from datetime import timedelta

import flux_mcp.utils as utils
from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class MoabScript(Script):
    """
    A helper class to build a Moab (#MSUB) batch script line by line.
    """

    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#MSUB"

    def add(self, flag, value=None):
        """
        Add a Moab directive, e.g., #MSUB -N my-job.
        Format is #MSUB -<flag> <value>
        """
        if value is None:
            return
        self.script_lines.append(f"{self.directive} -{flag} {str(value)}")


def seconds_to_moab_walltime(seconds):
    """
    Converts an integer number of seconds into Moab's HH:MM:SS walltime format.
    """
    # This shouldn't happen, but we return 0 so we use the default.
    if not seconds or seconds <= 0:
        return None

    # Moab walltime does not typically include days.
    hours, seconds_rem = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds_rem, 60)

    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


def epoch_to_moab_begin_time(epoch_seconds: int) -> str:
    """
    Converts a Unix epoch timestamp into Moab's required epoch integer string
    for the '-S' (starttime) flag.
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds < 0:
        raise ValueError("begin_time must be a positive integer (Unix epoch seconds).")

    return str(epoch_seconds)


def moab_walltime_to_seconds(time_str):
    if not time_str:
        return None

    h = 0
    m = 0
    s = 0
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = map(int, parts)
    elif len(parts) == 2:
        m, s = map(int, parts)
    elif len(parts) == 1:
        m = int(parts[0])
    return int(timedelta(hours=h, minutes=m, seconds=s).total_seconds())


def parse_moab_command(command_lines, spec):
    """
    Parses a moab command into parts.
    """
    # We use the last command line as the primary execution logic
    main_command = command_lines[-1]
    parts = shlex.split(main_command)

    # Unwrap common launchers like mpiexec
    if parts and parts[0] in ("mpiexec", "mpirun"):
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


def moab_begin_time_to_epoch(time_str):
    """
    Converts a Moab begin time string (epoch) to an integer.
    """
    if not time_str:
        return None
    try:
        return int(time_str)
    except ValueError:
        return None


def priority_to_moab_priority(priority):
    """
    Maps a semantic priority string ("high") to a Moab priority value (-1024 to 1023).
    """
    # Higher value means HIGHER priority in Moab.
    mapping = {
        "low": -500,
        "normal": 0,
        "high": 500,
        "urgent": 1000,
    }
    # Default to 'normal' (0) if the string is None or not in the map
    return mapping.get(priority, 0)


def moab_priority_to_priority(moab_priority):
    """
    Maps a Moab priority value back to a semantic string ("high").
    """
    if moab_priority is None or moab_priority == 0:
        return "normal"
    if moab_priority < 0:
        return "low"
    if 0 < moab_priority < 1000:
        return "high"
    return "urgent"  # for priority >= 1000


class MoabTransformer(TransformerBase):
    """
    A Moab Transformer for converting a generic JobSpec into a Moab batch script.

    This transformer maps the fields of the JobSpec to their corresponding #MSUB
    directives and constructs a runnable script.
    """

    def convert(self, spec) -> str:
        """
        Convert a normalized jobspec to a Moab batch script.
        """
        script = MoabScript()

        # If we don't have a job name, generate one
        job_name = spec.job_name or JobNamer().generate()
        script.add("N", job_name)

        # Job Identity & Accounting
        script.add("A", spec.account)

        # I/O
        script.add("o", spec.output_file)
        script.add("e", spec.error_file)
        if spec.mail_user:
            script.add("M", spec.mail_user)

        # Resource Requests
        resource_parts = []
        node_spec = []
        if spec.num_nodes:
            node_spec.append(f"nodes={spec.num_nodes}")
        if spec.cpus_per_task:
            node_spec.append(f"ppn={spec.cpus_per_task}")
        if spec.gpus_per_task > 0:
            node_spec.append(f"gpus={spec.gpus_per_task}")
        if spec.gpu_type:
            # Add gpu type as a feature request
            node_spec.append(spec.gpu_type)

        if node_spec:
            resource_parts.append(":".join(node_spec))

        if spec.generic_resources:
            resource_parts.append(f"gres={spec.generic_resources}")

        if spec.mem_per_task:
            resource_parts.append(f"mem={spec.mem_per_task}")

        if spec.exclusive_access:
            resource_parts.append("naccesspolicy=singlejob")

        wt = seconds_to_moab_walltime(spec.wall_time)
        if wt:
            resource_parts.append(f"walltime={wt}")

        if resource_parts:
            script.add("l", " ".join(resource_parts))

        script.add("q", spec.queue)

        moab_prio = priority_to_moab_priority(spec.priority)
        if moab_prio != 0:
            script.add("p", moab_prio)

        if spec.requeue is not None:
            script.add("r", "y" if spec.requeue else "n")

        if spec.begin_time:
            script.add("S", epoch_to_moab_begin_time(spec.begin_time))

        script.add("d", spec.working_directory)

        if spec.depends_on:
            if isinstance(spec.depends_on, list):
                script.add("l", f"depend=afterok:{':'.join(spec.depends_on)}")
            else:
                script.add("l", f"depend={spec.depends_on}")

        # Moab uses -v for environment variables, which is more robust than export
        if spec.environment:
            for key, value in spec.environment.items():
                script.add("v", f"{key}={value}")

        script.newline()

        # Execution logic
        container_exec = []
        if spec.container_image:
            container_exec = ["singularity", "exec", spec.container_image]

        command_parts = container_exec + spec.script

        if spec.input_file:
            command_parts.append(f"< {spec.input_file}")
        for line in command_parts:
            script.add_line(line)
        script.newline()
        return script.render()

    def _parse(self, filename, return_unhandled=False):
        """
        Parses the content of a Moab batch script into a JobSpec object.
        """
        spec = JobSpec()
        command_lines = []
        not_handled = set()
        # Weird -l directives
        l_directives = []

        msub_re = re.compile(r"#MSUB\s+-(\w+)(?:\s+(.+))?")
        script_content = utils.read_file(filename)

        for line in script_content.splitlines():
            if not line.strip():
                continue

            match = msub_re.match(line)
            if match:
                key, value = match.groups()
                # Strip comments and whitespace
                value = value.split("#", 1)[0].strip() if value else ""

                if key == "N":
                    spec.job_name = value
                elif key == "A":
                    spec.account = value
                elif key == "o":
                    spec.output_file = value
                elif key == "e":
                    spec.error_file = value
                elif key == "m" or key == "M":
                    spec.mail_user = value
                elif key == "q":
                    spec.queue = value
                elif key == "d":
                    spec.working_directory = value
                elif key == "S":
                    spec.begin_time = moab_begin_time_to_epoch(value)
                elif key == "p":
                    spec.priority = moab_priority_to_priority(int(value))
                elif key == "r":
                    spec.requeue = value.lower() == "y"
                elif key == "j":  # join stdout/stderr
                    if spec.output_file:
                        spec.error_file = spec.output_file
                    elif spec.error_file:
                        spec.output_file = spec.error_file
                elif key == "v":
                    if "=" in value:
                        env_key, env_val = value.split("=", 1)
                        spec.environment[env_key] = env_val
                elif key == "l":
                    # Collect all resource (-l) directives to parse them together
                    l_directives.append(value)
                else:
                    not_handled.add(key)
                continue

            # This handles environment variables set outside of #MSUB -v
            if line.lower().startswith("export "):
                env_match = re.match(r"export\s+([^=]+)=(.*)", line)
                if env_match:
                    env_key, env_val = env_match.groups()
                    spec.environment[env_key] = env_val.strip("'\"")

            if line.startswith("#"):
                continue

            command_lines.append(line)

        # Post parsing for all collected -l directives ---
        full_l_string = " ".join(l_directives)

        # Use shlex to handle spaces and colons within resource specs
        for part in shlex.split(full_l_string):

            # Split combined node:ppn requests first
            if ":" in part:
                node_features = []
                for subpart in part.split(":"):
                    if "=" not in subpart:
                        # This is a feature request, like "gtx1080"
                        node_features.append(subpart)
                        continue

                    k, v = subpart.split("=", 1)
                    if k == "nodes":
                        spec.num_nodes = int(v)
                    elif k == "ppn":
                        spec.cpus_per_task = int(v)
                    elif k == "gpus":
                        spec.gpus_per_task = int(v)

                # Heuristic: If we found GPUs and other features, assume the first
                # other feature is the gpu_type.
                if spec.gpus_per_task > 0 and node_features:
                    spec.gpu_type = node_features[0]

            elif "=" in part:
                k, v = part.split("=", 1)
                if k == "walltime":
                    spec.wall_time = moab_walltime_to_seconds(v)
                elif k == "nodes":
                    spec.num_nodes = int(v)
                elif k == "ppn":
                    spec.cpus_per_task = int(v)
                elif k == "procs":
                    spec.num_tasks = int(v)
                elif k == "mem":
                    spec.mem_per_task = v
                elif k == "gres":
                    spec.generic_resources = v
                elif k == "depend":
                    spec.depends_on = v
                elif k == "naccesspolicy" and v == "singlejob":
                    spec.exclusive_access = True
                elif k == "qos" and not spec.queue:
                    spec.queue = v  # Use qos if queue isn't set
                else:
                    not_handled.add(f"l:{k}")

        if command_lines:
            spec.script = command_lines

        if return_unhandled:
            return not_handled
        return spec
