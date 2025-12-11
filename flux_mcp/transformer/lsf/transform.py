import re
import shlex
from datetime import datetime, timedelta

from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.transformer.common import JobSpec


class LSFScript(Script):
    """
    A helper class to build an LSF (#BSUB) batch script line by line.
    """

    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#BSUB"


def priority_to_lsf_priority(priority_str):
    """
    Maps a semantic string to an LSF priority value (1-65535).
    """
    return {
        "low": 10,
        "normal": 50,
        "high": 100,
        "urgent": 200,
    }.get(priority_str, 50)


def lsf_priority_to_priority(lsf_priority):
    """
    Maps an LSF priority value back to a semantic string.
    """
    if lsf_priority is None:
        return "normal"
    if lsf_priority <= 10:
        return "low"
    if lsf_priority <= 50:
        return "normal"
    if lsf_priority <= 100:
        return "high"
    return "urgent"


def seconds_to_lsf_walltime(total_seconds):
    """
    Converts integer seconds to LSF HH:MM walltime format.
    """
    if not isinstance(total_seconds, int) or total_seconds <= 0:
        return None
    # LSF's -W flag expects minutes or HH:MM
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}"


def lsf_walltime_to_seconds(time_str):
    """
    Converts LSF HH:MM walltime string back to integer seconds.
    """
    if not time_str:
        return None
    try:
        # LSF can also be just minutes.
        if ":" in time_str:
            h, m = map(int, time_str.split(":"))
            return int(timedelta(hours=h, minutes=m).total_seconds())
        return int(time_str) * 60
    except (ValueError, IndexError):
        return None


def epoch_to_lsf_begin_time(epoch_seconds):
    """
    Converts Unix epoch to LSF's begin time format for the '-b' flag.
    """
    if not isinstance(epoch_seconds, int) or epoch_seconds <= 0:
        return None
    return datetime.fromtimestamp(epoch_seconds).strftime("%Y:%m:%d:%H:%M")


def lsf_begin_time_to_epoch(time_str):
    """
    Converts an LSF begin time string back to Unix epoch.
    """
    if not time_str:
        return None
    try:
        return int(datetime.strptime(time_str, "%Y:%m:%d:%H:%M").timestamp())
    except (ValueError, IndexError):
        return None


def parse_lsf_command(command_lines, spec):
    """
    Parses an LSF command line into parts.
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

    # Common LSF launchers include jsrun (Spectrum MPI) or mpirun
    if parts and parts[0] in ("jsrun", "mpirun"):
        parts = parts[1:]

    if parts and parts[0] in ("singularity", "apptainer") and parts[1] == "exec":
        spec.container_image = parts[2]
        parts = parts[3:]

    return parts


# --- Main Transformer Class ---


class LSFTransformer(TransformerBase):
    """
    Transforms a JobSpec to/from an LSF (#BSUB) batch script.
    """

    def convert(self, spec):
        """
        Converts a JobSpec into an LSF submission script string.
        """
        script = LSFScript()

        script.add("J", spec.job_name or JobNamer().generate())
        script.add("P", spec.account)
        script.add("q", spec.queue)
        script.add("o", spec.output_file)
        script.add("e", spec.error_file)

        # Mail notifications
        if spec.mail_user:
            script.add("u", spec.mail_user)
            if "BEGIN" in [m.upper() for m in spec.mail_type]:
                script.add_flag("B")
            if "END" in [m.upper() for m in spec.mail_type]:
                script.add_flag("N")

        # --- Resource Specification ---
        # LSF is typically task-centric with the -n flag for total tasks.
        if spec.num_tasks > 0:
            script.add("n", spec.num_tasks)

        wt = seconds_to_lsf_walltime(spec.wall_time)
        script.add("W", wt)

        # Build the complex -R "select[...] span[...] rusage[...]" string
        r_parts = []

        # Handle select criteria, including GPU type
        select_criteria = list(spec.constraints)

        # I'm not sure this would actually work
        if spec.gpu_type:
            select_criteria.append(spec.gpu_type)
        if select_criteria:
            r_parts.append(f'select[{":".join(select_criteria)}]')

        if spec.num_nodes > 1 and spec.num_tasks > 0:
            tasks_per_node = spec.num_tasks // spec.num_nodes
            if tasks_per_node > 0:
                r_parts.append(f"span[ptile={tasks_per_node}]")

        rusage_parts = []
        if spec.mem_per_task:
            # LSF typically expects memory in MB
            mem_mb = int(re.sub(r"[^0-9]", "", spec.mem_per_task))
            if "G" in spec.mem_per_task.upper():
                mem_mb *= 1024
            rusage_parts.append(f"mem={mem_mb}")

        if spec.gpus_per_task > 0:
            # ngpus_excl_p = GPUs per process (task) in exclusive mode.
            rusage_parts.append(f"ngpus_excl_p={spec.gpus_per_task}")

        if rusage_parts:
            r_parts.append(f'rusage[{":".join(rusage_parts)}]')

        if r_parts:
            script.add("R", f'"{" ".join(r_parts)}"')

        if spec.exclusive_access:
            script.add_flag("x")

        if spec.requeue:
            script.add_flag("r")  # -r makes the job rerunnable

        # --- Priority and Scheduling ---
        lsf_prio = priority_to_lsf_priority(spec.priority)
        if lsf_prio != 50:  # Don't add if it's the default
            script.add("sp", lsf_prio)

        bt = epoch_to_lsf_begin_time(spec.begin_time)
        script.add("b", bt)

        # Dependencies
        if spec.depends_on:
            dep_str = (
                " && ".join([f"ended({job_id})" for job_id in spec.depends_on])
                if isinstance(spec.depends_on, list)
                else f"ended({spec.depends_on})"
            )
            script.add("w", f'"{dep_str}"')

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
            # jsrun is a common launcher in LSF environments
            cmd_parts = ["jsrun"]
            # Map cpus_per_task to jsrun's resource set model
            if spec.cpus_per_task > 0:
                # 1 resource set with cpus_per_task cores, 1 task per set
                cmd_parts.append(f"--nrs {spec.num_tasks}")
                cmd_parts.append(f"--rs_per_host {spec.num_tasks // spec.num_nodes}")
                cmd_parts.append(f"--tasks_per_rs 1")
                cmd_parts.append(f"--cpu_per_rs {spec.cpus_per_task}")

            cmd_parts = spec.derive_command(cmd_parts)
            script.add_line(" ".join(cmd_parts))

        script.newline()

        return script.render()

    def _parse(self, content, return_unhandled=False):
        """
        Parses an LSF submission script string into a JobSpec.
        """
        spec = JobSpec()
        bsub_re = re.compile(r"#BSUB\s+(-[\w]+)(?:\s+(.+))?")
        command_lines = []
        not_handled = set()

        # Heuristic list of common GPU names to identify as gpu_type
        known_gpu_types = {"a100", "v100", "h100", "a30", "a40", "mi250"}

        for line in content.splitlines():
            if not line.strip():
                continue

            m = bsub_re.match(line)
            if m:
                key, val = m.groups()
                key = key.lstrip("-")
                if val:
                    val = val.split("#", 1)[0]  # Remove trailing comments

                val = val.strip().strip('"') if val else True

                if key == "J":
                    spec.job_name = val
                elif key == "P":
                    spec.account = val
                elif key == "q":
                    spec.queue = val
                elif key == "o":
                    spec.output_file = val
                elif key == "e":
                    spec.error_file = val
                elif key == "b":
                    spec.begin_time = lsf_begin_time_to_epoch(val)
                elif key == "sp":
                    spec.priority = lsf_priority_to_priority(int(val))
                elif key == "n":
                    spec.num_tasks = int(val)
                elif key == "W":
                    spec.wall_time = lsf_walltime_to_seconds(val)
                elif key == "x":
                    spec.exclusive_access = True
                elif key == "r":
                    spec.requeue = True
                elif key == "u":
                    spec.mail_user = val
                elif key == "B":
                    spec.mail_type.append("BEGIN")
                elif key == "N":
                    spec.mail_type.append("END")
                elif key == "w":
                    ended_jobs = re.findall(r"ended\(([^)]+)\)", val)
                    spec.depends_on = ended_jobs
                elif key == "R":
                    # Parse complex -R string
                    rusage_match = re.search(r"rusage\[(.*?)\]", val)
                    span_match = re.search(r"span\[ptile=(\d+)\]", val)
                    select_match = re.search(r"select\[(.*?)\]", val)

                    if rusage_match:
                        for part in rusage_match.group(1).split(":"):
                            k, v = part.split("=", 1)
                            if k == "mem":
                                spec.mem_per_task = f"{v}M"  # Assume parsed value is MB
                            elif k == "ngpus_excl_p":
                                spec.gpus_per_task = int(v)
                    if span_match:
                        tasks_per_node = int(span_match.group(1))
                        if spec.num_tasks > 0 and tasks_per_node > 0:
                            spec.num_nodes = spec.num_tasks // tasks_per_node
                    if select_match:
                        criteria = select_match.group(1).split(":")
                        for criterion in criteria:
                            # If a criterion is a known GPU type, set it and move on
                            if criterion.lower() in known_gpu_types:
                                spec.gpu_type = criterion
                            else:
                                spec.constraints.append(criterion)
                else:
                    not_handled.add(key)
                continue

            if line.startswith("#"):
                continue
            command_lines.append(line)

        # In LSF, -n usually defines total tasks. If num_nodes is not specified
        # we can assume 1, but this is an imperfect mapping back.
        if spec.num_tasks and spec.num_nodes == 1:
            pass

        # We again assume a block of text here.
        if command_lines:
            spec.script = command_lines
            parts = parse_lsf_command(command_lines, spec)
            if parts:
                # A full jsrun parser is complex; we can extract simple cases.
                try:
                    if "--cpu_per_rs" in parts:
                        idx = parts.index("--cpu_per_rs")
                        spec.cpus_per_task = int(parts[idx + 1])
                except (ValueError, IndexError):
                    pass
                spec.executable = parts[0]
                spec.arguments = parts[1:]

        if return_unhandled:
            return not_handled
        return spec
