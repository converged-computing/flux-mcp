import re
import shlex
from datetime import datetime, timedelta

from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class PBSScript(Script):
    """
    A helper class to build a PBS batch script line by line.
    """

    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#PBS"


def priority_to_pbs_priority(priority_str):
    """
    Maps a semantic string to a PBS priority value (-1024 to 1023).
    """
    # Higher value means HIGHER priority in PBS.
    return {
        "low": -500,
        "normal": 0,
        "high": 500,
        "urgent": 1000,
    }.get(priority_str, 0)


def pbs_priority_to_priority(pbs_priority):
    """
    Maps a PBS priority value back to a semantic string.
    """
    if pbs_priority is None:
        return "normal"
    if pbs_priority < 0:
        return "low"
    if pbs_priority == 0:
        return "normal"
    if 0 < pbs_priority < 1000:
        return "high"
    return "urgent"  # for pbs_priority >= 1000


def seconds_to_pbs(total_seconds):
    """
    Converts integer seconds to PBS HH:MM:SS walltime format.
    """
    if not isinstance(total_seconds, int) or total_seconds <= 0:
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"


def pbs_time_to_seconds(time_str):
    """
    Converts PBS HH:MM:SS walltime string back to integer seconds.
    """
    if not time_str:
        return None
    try:
        h, m, s = map(int, time_str.split(":"))
        return int(timedelta(hours=h, minutes=m, seconds=s).total_seconds())
    except (ValueError, IndexError):
        return None


def epoch_to_pbs_begin_time(epoch_seconds):
    """
    Converts Unix epoch to PBS packed date-time format for the '-a' flag.
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds <= 0:
        return None
    return datetime.fromtimestamp(epoch_seconds).strftime("%Y%m%d%H%M.%S")


def pbs_begin_time_to_epoch(time_str):
    """
    Converts a PBS packed date-time string back to Unix epoch.
    """
    if not time_str:
        return None
    try:
        # Handle with and without seconds
        fmt = "%Y%m%d%H%M.%S" if "." in time_str else "%Y%m%d%H%M"
        return int(datetime.strptime(time_str, fmt).timestamp())
    except (ValueError, IndexError):
        return None


def parse_pbs_command(command_lines, spec):
    """
    Parses a PBS command line into parts.
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

    if parts and parts[0] in ("mpiexec", "mpirun"):
        parts = parts[1:]

    if parts and parts[0] in ("singularity", "apptainer") and parts[1] == "exec":
        spec.container_image = parts[2]
        parts = parts[3:]

    return parts


class PBSTransformer(TransformerBase):
    """
    Transforms a JobSpec to/from a PBS (Portable Batch System) batch script.
    """

    def convert(self, spec):
        """
        Converts a JobSpec into a PBS submission script string.
        """
        script = PBSScript()

        script.add("N", spec.job_name or JobNamer().generate())
        script.add("A", spec.account)
        script.add("q", spec.queue)
        script.add("o", spec.output_file)
        script.add("e", spec.error_file)

        # Mail notifications
        if spec.mail_user:
            script.add("M", spec.mail_user)
            # -m sets the conditions: a=abort, b=begin, e=end
            mail_opts = "".join([m[0].lower() for m in spec.mail_type])
            if mail_opts:
                script.add("m", mail_opts)

        # Resource Selection (-l)
        select_parts = []
        if spec.num_nodes > 0:
            # Build the select statement parts
            node_spec = [f"select={spec.num_nodes}"]
            if spec.cpus_per_task > 1:
                node_spec.append(f"ncpus={spec.cpus_per_task}")
            if spec.gpus_per_task > 0:
                node_spec.append(f"ngpus={spec.gpus_per_task}")
            # I am not clear difference between gpus and accelerators
            # but this seems supported - would need to test
            if spec.gpu_type:
                node_spec.append(f"accelerator_type={spec.gpu_type}")
            # mpiprocs is often used to specify total tasks, which works well with our spec
            if spec.num_tasks > 1:
                node_spec.append(f"mpiprocs={spec.num_tasks}")

            select_parts.append(":".join(node_spec))

        # PBS memory format often includes units like gb or mb
        if spec.mem_per_task:
            # Standardize to lowercase and append 'b' for bytes.
            mem_val = spec.mem_per_task.lower()
            if not mem_val.endswith("b"):
                mem_val += "b"
            select_parts.append(f"mem={mem_val}")

        resource_str = ",".join(select_parts)

        wt = seconds_to_pbs(spec.wall_time)
        if wt:
            resource_str += f",walltime={wt}"

        # Task placement strategy
        if spec.num_nodes > 1:
            resource_str += f",place=scatter:excl" if spec.exclusive_access else ",place=scatter"

        script.add("l", resource_str)

        # Priority and scheduling
        pbs_prio = priority_to_pbs_priority(spec.priority)
        if pbs_prio != 0:
            script.add("p", pbs_prio)

        bt = epoch_to_pbs_begin_time(spec.begin_time)
        script.add("a", bt)

        # Requeue policy: -r n means not rerunnable
        if spec.requeue is False:
            script.add("r", "n")

        # Dependencies via -W depend=...
        if spec.depends_on:
            dep_list = spec.depends_on if isinstance(spec.depends_on, list) else [spec.depends_on]
            dep_str = ":".join([f"afterok:{job_id}" for job_id in dep_list])
            script.add("W", f"depend={dep_str}")

        # Environment & Execution
        if spec.environment:
            # PBS's -v option is for exporting variables from the submission shell.
            # To set arbitrary variables, it's safer to do it in the script body.
            script.newline()
            for key, value in spec.environment.items():
                script.add_line(f"export {key}='{value}'")

        script.newline()

        # If spec.script is defined, it takes precedence.
        if spec.script:
            script.add_lines(spec.script)
        else:
            # TODO: we probably want to keep this as a block of text, as it is.
            cmd_parts = ["mpiexec"]
            if spec.num_tasks > 1:
                cmd_parts.extend(["-n", str(spec.num_tasks)])

            if spec.container_image:
                cmd_parts.extend(["singularity", "exec", spec.container_image])

            if spec.executable:
                if isinstance(spec.executable, list):
                    cmd_parts += spec.executable
                else:
                    cmd_parts.append(spec.executable)

            if spec.arguments:
                cmd_parts.extend(spec.arguments)
            script.add_line(" ".join(cmd_parts))

        script.newline()
        return script.render()

    def _parse(self, content, return_unhandled=False):
        """
        Parses a PBS submission script string into a JobSpec.
        """
        spec = JobSpec()
        pbs_re = re.compile(r"#PBS\s+(-[\w]+)(?:\s+(.+))?")
        command_lines = []
        not_handled = set()

        for line in content.splitlines():
            if not line.strip():
                continue

            m = pbs_re.match(line)
            if m:
                key, val = m.groups()
                key = key.lstrip("-")
                if val:
                    val = val.split("#", 1)[0]  # Remove trailing comments

                val = val.strip().strip('"') if val else True

                if key == "N":
                    spec.job_name = val
                elif key == "A":
                    spec.account = val
                elif key == "q":
                    spec.queue = val
                elif key == "o":
                    spec.output_file = val
                elif key == "e":
                    spec.error_file = val
                elif key == "a":
                    spec.begin_time = pbs_begin_time_to_epoch(val)
                elif key == "p":
                    spec.priority = pbs_priority_to_priority(int(val))
                elif key == "M":
                    spec.mail_user = val
                elif key == "m":
                    if "a" in val:
                        spec.mail_type.append("ABORT")
                    if "b" in val:
                        spec.mail_type.append("BEGIN")
                    if "e" in val:
                        spec.mail_type.append("END")
                elif key == "r" and val == "n":
                    spec.requeue = False
                elif key == "W":
                    if "depend=" in val:
                        dep_str = val.split("depend=")[1]
                        spec.depends_on = [d.split(":")[-1] for d in dep_str.split(":")]
                elif key == "l":
                    # The -l line can contain multiple comma-separated values
                    parts = val.replace(" ", "").split(",")
                    for part in parts:
                        if "=" not in part:
                            continue
                        k, v = part.split("=", 1)
                        if k == "walltime":
                            spec.wall_time = pbs_time_to_seconds(v)
                        elif k == "select":
                            # select=N:ncpus=C:mpiprocs=T:gpu_type=a100...
                            select_parts = v.split(":")
                            spec.num_nodes = int(select_parts[0])
                            for sp in select_parts[1:]:
                                sk, sv = sp.split("=", 1)
                                if sk == "ncpus":
                                    spec.cpus_per_task = int(sv)
                                elif sk == "ngpus":
                                    spec.gpus_per_task = int(sv)
                                elif sk == "gpu_type":
                                    spec.gpu_type = sv
                                elif sk == "mem":
                                    spec.mem_per_task = sv.upper().replace("B", "")
                                elif sk == "mpiprocs":
                                    spec.num_tasks = int(sv)
                        elif k == "place":
                            if "excl" in v:
                                spec.exclusive_access = True
                else:
                    not_handled.add(key)
                continue

            if line.startswith("#"):
                continue
            command_lines.append(line)

        # We again assume a block of text here.
        if command_lines:
            spec.script = command_lines
            parts = parse_pbs_command(command_lines, spec)
            if parts:
                spec.executable = parts[0]
                spec.arguments = parts[1:]

        if return_unhandled:
            return not_handled
        return spec
