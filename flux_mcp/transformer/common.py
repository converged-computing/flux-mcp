from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

# Requires Python 3.8+ for dataclass


@dataclass
class JobSpec:
    """
    A scheduler-agnostic data structure for defining a computational job.
    Version 2: Now includes accounting, priority, environment, and more constraints.
    """

    # Job Identity & Accounting
    job_name: Optional[str] = None
    account: Optional[str] = None

    # What to Run
    executable: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    container_image: Optional[str] = None
    working_directory: Optional[str] = None

    # Custom attributes or options
    attrs: Optional[dict] = field(default_factory=dict)
    options: Optional[dict] = field(default_factory=dict)

    # Resource Requests ---
    num_tasks: int = 1
    num_nodes: int = 1
    cpus_per_task: int = 1
    mem_per_task: Optional[str] = None
    gpus_per_task: int = 0
    gpu_type: Optional[str] = None

    # Scheduling and Constraints
    wall_time: Optional[int] = None
    queue: Optional[str] = None
    priority: Optional[int] = None
    exclusive_access: bool = False
    constraints: List[str] = field(default_factory=list)
    begin_time: Optional[int] = None

    # Environment and I/O
    environment: Dict[str, str] = field(default_factory=dict)
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    error_file: Optional[str] = None

    # Dependencies and script
    depends_on: Optional[Union[str, List[str]]] = None
    script: List[str] = field(default_factory=list)

    array_spec: Optional[str] = None
    generic_resources: Optional[str] = None
    mail_user: Optional[str] = None
    mail_type: List[str] = field(default_factory=list)
    requeue: Optional[bool] = None
    nodelist: Optional[str] = None
    exclude_nodes: Optional[str] = None
    licenses: Optional[str] = None

    def derive_command(self, cmd_parts):
        """
        Common/shared function to derive command parts
        """
        if self.container_image:
            cmd_parts.extend(["singularity", "exec", self.container_image])
        if self.executable and isinstance(self.executable, list):
            cmd_parts += self.executable
        elif self.executable:  # assume to be string
            cmd_parts.append(self.executable)

        if self.arguments and isinstance(self.arguments, list):
            cmd_parts += self.arguments
        elif self.arguments:
            cmd_parts.extend(self.arguments)
        return cmd_parts
