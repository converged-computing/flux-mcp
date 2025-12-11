from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import Script, TransformerBase
from flux_mcp.validate.validate import Validator


class FluxScript(Script):
    def __init__(self):
        self.script_lines = ["#!/bin/bash"]
        self.directive = "#FLUX"


def priority_to_flux_priority(class_name):
    """
    Maps a pre-defined PriorityClass name string back to a representative
    numerical priority value. This is the reverse of map_numeric_priority_to_class_name.
    """
    # Define the mapping from the string class back to a representative number.
    mapping = {"low": 15, "normal": 16, "high": 50, "urgent": 100}

    # If we don't get it, default to Flux's default
    return mapping.get(class_name, 16)


class FluxTransformer(TransformerBase):
    """
    A Flux Transformer for converting a generic JobSpec into a Flux batch script.
    """

    def _parse(self, jobspec, return_unhandled=False):
        """
        Parse an (expected) Flux jobspec. Right now we assume it is from
        the user, so it is a Flux batch script.
        """
        validator = Validator("batch")

        # This is a parsed (normalized) JobSpec
        if return_unhandled:
            return validator.unhandled(jobspec)
        return validator.parse(jobspec)

    def run(self, matches, jobspec):
        """
        Parse the jobspec into tasks for flux.
        """
        namer = JobNamer()
        # Here we want to group by cluster
        # We need to artificially parse the match metadata
        # This is handled by the solver, because each solver can
        # hold and represent metadata differently.
        for _, subsystems in matches.matches.items():

            # There are two strategies we could take here. To update the flux
            # jobscript to have a batch script (more hardened, but doesn't
            # fit the LLM work we are doing) or try to write a flux run command
            # in a batch script (better fits). I don't like either way,
            # but I dislike the second way slightly less.
            script = "#!/bin/bash\n"
            for line in self.solver.render(subsystems):
                script += line

            # Now we add back in the command
            command = " ".join(jobspec["tasks"][0]["command"])
            script += f"\n{command}"

            # This is the task script data
            data = {"mode": 33216, "data": script, "encoding": "utf-8"}

            # I'm going to be careful about updating files
            files = jobspec["attributes"]["system"].get("files") or {}

            # Generate a name for the script
            script_name = namer.generate() + ".sh"
            files[script_name] = data
            jobspec["attributes"]["system"]["files"] = files
            jobspec["tasks"][0]["command"] = ["/bin/bash", f"./{script_name}"]
            yield jobspec

    def convert(self, spec):
        """
        Convert a normalized jobspec to a Flux batch script.
        """
        script = FluxScript()

        job_name = spec.job_name or JobNamer().generate()
        script.add("job-name", job_name)

        # Resource Directives
        script.add("N", spec.num_nodes if spec.num_nodes > 1 else None)
        script.add("n", spec.num_tasks if spec.num_tasks > 1 else None)
        script.add("c", spec.cpus_per_task if spec.cpus_per_task > 1 else None)
        script.add("gpus-per-task", spec.gpus_per_task if spec.gpus_per_task > 0 else None)

        # Add a constraint for the specific GPU type, if provided
        # We could probably add gpu_type to requires if an admin configures it,
        # but it's too risky.

        # Scheduling Directives
        if spec.exclusive_access:
            script.add_flag("exclusive")
        script.add("queue", spec.queue)

        # Flux's -t flag accepts wall time in seconds directly.
        script.add("t", spec.wall_time)

        flux_prio = priority_to_flux_priority(spec.priority)
        if flux_prio != 16:
            script.add("urgency", flux_prio)
        script.newline()

        # Environment
        if spec.environment:
            for key, value in spec.environment.items():
                script.add_line(f"export {key}='{value}'")
            script.newline()

        if spec.script:
            for line in spec.script:
                script.add_line(line)
        script.newline()
        return script.render()

    @property
    def resources(self):
        """
        This returns a global resource lookup
        """
        return self.js.get("resources", {})
