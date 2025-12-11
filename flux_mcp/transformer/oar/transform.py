import re
import shlex
from datetime import datetime, timedelta

from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class OARScript(Script):
    """
    A helper class to build an OAR (#OAR) batch script line by line.
    """

    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#OAR"


def priority_to_oar_priority(priority_str):
    """
    Maps a semantic string to an OAR priority value.
    """
    # Higher value means HIGHER priority in OAR.
    return {
        "low": 10,
        "normal": 50,
        "high": 100,
        "urgent": 200,
    }.get(priority_str, 50)


def oar_priority_to_priority(oar_priority):
    """
    Maps an OAR priority value back to a semantic string.
    """
    if oar_priority is None:
        return "normal"
    if oar_priority <= 10:
        return "low"
    if oar_priority <= 50:
        return "normal"
    if oar_priority <= 100:
        return "high"
    return "urgent"


def seconds_to_oar_walltime(total_seconds):
    """
    Converts integer seconds to OAR DD:HH:MM:SS walltime format.
    """
    if not isinstance(total_seconds, int) or total_seconds <= 0:
        return None
    d, r = divmod(total_seconds, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return (
        f"{int(d)}:{int(h):02d}:{int(m):02d}:{int(s):02d}"
        if d > 0
        else f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    )


def oar_walltime_to_seconds(time_str):
    """
    Converts OAR DD:HH:MM:SS walltime string back to integer seconds.
    """
    if not time_str:
        return None
    d, h, m, s = 0, 0, 0, 0
    parts = time_str.split(":")
    try:
        if len(parts) == 4:
            d, h, m, s = map(int, parts)
        elif len(parts) == 3:
            h, m, s = map(int, parts)
        elif len(parts) == 2:
            m, s = map(int, parts)
        else:
            return None
        return int(timedelta(days=d, hours=h, minutes=m, seconds=s).total_seconds())
    except ValueError:
        return None


def epoch_to_oar_begin_time(epoch_seconds):
    """
    Converts Unix epoch to OAR's begin time format: "YYYY-MM-DD HH:MM:SS".
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds <= 0:
        return None
    return f'"{datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%d %H:%M:%S")}"'


def oar_begin_time_to_epoch(time_str):
    """
    Converts an OAR begin time string back to Unix epoch.
    """
    if not time_str:
        return None
    try:
        return int(datetime.strptime(time_str.strip('"'), "%Y-%m-%d %H:%M:%S").timestamp())
    except (ValueError, IndexError):
        return None


def parse_oar_command(command_lines, spec):
    """
    Parses an OAR command line into parts.
    """
    if not command_lines:
        return []

    main_command = ""
    for line in command_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            main_command = line
            break

    if not main_command:
        return []

    parts = shlex.split(main_command)

    # Common OAR launchers include mpirun or using oarsh explicitly
    if parts and parts[0] in ("mpirun", "oarsh"):
        parts = parts[1:]

    if parts and parts[0] in ("singularity", "apptainer") and parts[1] == "exec":
        spec.container_image = parts[2]
        parts = parts[3:]

    return parts


# --- Main Transformer Class ---


class OARTransformer(TransformerBase):
    """
    Transforms a JobSpec to/from an OAR batch script.
    """

    def convert(self, spec):
        """
        Converts a JobSpec into an OAR submission script string.
        """
        script = OARScript()

        script.add("n", spec.job_name or JobNamer().generate())
        script.add("p", spec.account)  # OAR uses -p for project
        script.add("q", spec.queue)
        script.add("O", spec.output_file)
        script.add("E", spec.error_file)

        # Mail notifications
        if spec.mail_user:
            script.add("m", spec.mail_user)
            if spec.mail_type:
                # OAR uses a single flag for each type
                for mail_type in spec.mail_type:
                    if mail_type.lower() in ["begin", "b"]:
                        script.add_flag("b")
                    elif mail_type.lower() in ["end", "e"]:
                        script.add_flag("e")
                    elif mail_type.lower() in ["abort", "a"]:
                        script.add_flag("a")

        # --- Resource Selection (-l) ---
        # OAR's resource model is often hierarchical.
        # This logic creates a resource string like /nodes=N/cpu=C/core=T,walltime=W
        l_parts = []
        if spec.num_nodes > 0:
            l_parts.append(f"/nodes={spec.num_nodes}")

        # OAR distinguishes between logical CPUs (threads) and physical cores.
        # We map cpus_per_task to 'core' for clarity.
        if spec.cpus_per_task > 0:
            l_parts.append(f"/core={spec.cpus_per_task}")

        if spec.gpus_per_task > 0:
            # This requests nodes that *each* have at least this many GPUs.
            l_parts.append(f"/gpunum={spec.gpus_per_task}")

        # Add the specific GPU type as a resource property
        if spec.gpu_type:
            l_parts.append(f"/gpu_model='{spec.gpu_type}'")

        resource_str = "".join(l_parts)

        # Node constraints are added as properties to the resource string.
        if spec.constraints:
            constraint_str = " AND ".join(f"'{c}'" for c in spec.constraints)
            resource_str += f"/{constraint_str}"

        wt = seconds_to_oar_walltime(spec.wall_time)
        if wt:
            resource_str += f",walltime={wt}"

        if resource_str:
            script.add("l", f'"{resource_str}"')

        if spec.exclusive_access:
            script.add_flag("x")

        if spec.requeue is False:
            script.add("t", "idempotent")  # The closest concept to no-requeue

        # --- Priority and Scheduling ---
        oar_prio = priority_to_oar_priority(spec.priority)
        if oar_prio != 50:
            script.add("priority", oar_prio)

        bt = epoch_to_oar_begin_time(spec.begin_time)
        script.add("r", bt)

        # Dependencies
        if spec.depends_on:
            dep_str = "after:" + (
                ":".join(spec.depends_on) if isinstance(spec.depends_on, list) else spec.depends_on
            )
            script.add("after", dep_str)

        script.newline()

        # --- Environment & Execution ---
        if spec.environment:
            for key, value in spec.environment.items():
                script.add_line(f"export {key}='{value}'")
            script.newline()

        # If spec.script is defined, it takes precedence.
        if spec.script:
            script.add_lines(spec.script)
        else:
            cmd_parts = ["mpirun"]
            cmd_parts = spec.derive_command(cmd_parts)
            script.add_line(" ".join(cmd_parts))

        script.newline()

        return script.render()

    def _parse(self, content, return_unhandled=False):
        """
        Parses an OAR submission script string into a JobSpec.
        """
        spec = JobSpec()
        oar_re = re.compile(r"#OAR\s+(-[\w]+|--[\w-]+)(?:\s+(.+))?")
        command_lines = []
        not_handled = set()

        for line in content.splitlines():
            if not line.strip():
                continue

            m = oar_re.match(line)
            if m:
                key, val = m.groups()
                key = key.strip()
                if val:
                    val = val.split("#", 1)[0]  # Remove trailing comments
                val = val.strip().strip('"') if val else ""

                if key == "-n":
                    spec.job_name = val
                elif key == "-p":
                    spec.account = val
                elif key == "-q":
                    spec.queue = val
                elif key == "-O":
                    spec.output_file = val
                elif key == "-E":
                    spec.error_file = val
                elif key == "-r":
                    spec.begin_time = oar_begin_time_to_epoch(val)
                elif key == "--priority":
                    spec.priority = oar_priority_to_priority(int(val))
                elif key == "-x":
                    spec.exclusive_access = True
                elif key == "-t" and val == "idempotent":
                    spec.requeue = False
                elif key == "-after":
                    spec.depends_on = val.split("after:")[1].split(":")
                elif key == "-m":
                    spec.mail_user = val
                elif key in ["-a", "-b", "-e"]:
                    mail_map = {"-a": "ABORT", "-b": "BEGIN", "-e": "END"}
                    spec.mail_type.append(mail_map[key])
                elif key == "-l":
                    # Parse resource string like "/nodes=4/cpu=8/core=4/gpunum=1,walltime=01:00:00"
                    resource_part = val.split(",walltime=")[0]
                    if ",walltime=" in val:
                        spec.wall_time = oar_walltime_to_seconds(val.split(",walltime=")[1])

                    parts = re.split(r"/", resource_part)
                    for part in parts:
                        if not part:
                            continue
                        if "=" in part:
                            k, v = part.split("=", 1)
                            if k == "nodes":
                                spec.num_nodes = int(v)
                            # OAR has cpu, core, and thread. We'll map core to cpus_per_task.
                            elif k == "core":
                                spec.cpus_per_task = int(v)
                            elif k == "cpu":
                                # If core isn't set, use cpu as a fallback.
                                if spec.cpus_per_task == 1:
                                    spec.cpus_per_task = int(v)
                            elif k == "gpunum":
                                spec.gpus_per_task = int(v)
                            elif k == "gpu_model":
                                spec.gpu_type = v.strip("'")
                        else:
                            # Assume parts without '=' are constraints
                            spec.constraints.append(part.strip().strip("'"))
                else:
                    not_handled.add(key)
                continue

            if line.startswith("#"):
                continue
            command_lines.append(line)

        # We again assume a block of text here.
        if command_lines:
            spec.script = command_lines
            parts = parse_oar_command(command_lines, spec)
            if parts:
                spec.executable = parts[0]
                spec.arguments = parts[1:]

        if return_unhandled:
            return not_handled
        return spec
