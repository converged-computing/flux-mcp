#!/usr/bin/env python3

import re

import yaml

from flux_mcp.logger.generate import JobNamer
from flux_mcp.transformer.base import TransformerBase
from flux_mcp.transformer.common import JobSpec

# Assume GPUs are NVIDIA
gpu_resource_name = "nvidia.com/gpu"
gpu_product_label = "nvidia.com/gpu.product"


def normalize_cpu_request(cpus: int) -> str:
    """
    Convert an integer number of CPUs to a Kubernetes CPU string.
    """
    # Kubernetes can use millicores, e.g., 1 -> "1000m", 0.5 -> "500m"
    # We will stick to whole numbers, but this is where you'd convert.
    return str(cpus)


def normalize_memory_request(mem_str):
    """
    Convert memory units like 'G' and 'M' to Kubernetes 'Gi' and 'Mi'.
    """
    if not mem_str:
        return None
    mem_str = mem_str.upper()
    if mem_str.endswith("G"):
        return mem_str.replace("G", "Gi")
    if mem_str.endswith("M"):
        return mem_str.replace("M", "Mi")

    # Assume other formats (like Gi, Mi, K, Ki) are already correct
    return mem_str


def parse_memory(mem_str: str) -> str:
    """
    Converts K8s memory (e.g., 1Gi) to JobSpec format (e.g., 1G).
    """
    if not mem_str:
        return None
    mem_str = mem_str.upper()
    if mem_str.endswith("GI"):
        return mem_str.replace("GI", "G")
    if mem_str.endswith("MI"):
        return mem_str.replace("MI", "M")
    if mem_str.endswith("KI"):
        return mem_str.replace("KI", "K")
    return mem_str


def parse_cpu(cpu_str: str) -> int:
    """
    Converts K8s CPU string to an integer. Assumes no millicores.
    """
    if not cpu_str:
        return 1
    return int(cpu_str)


def get_resources(spec):
    """
    Get Kubernetes resources from standard jobspec
    """
    # Resources (CPU, Memory, GPU)
    resources = {"requests": {}, "limits": {}}

    # We usually map tasks to kubernetes cores
    if spec.num_tasks > 1:
        cpu_request = normalize_cpu_request(spec.num_tasks)
        resources["requests"]["cpu"] = cpu_request
        resources["limits"]["cpu"] = cpu_request

    elif spec.cpus_per_task > 0:
        cpu_request = normalize_cpu_request(spec.cpus_per_task)
        resources["requests"]["cpu"] = cpu_request
        resources["limits"]["cpu"] = cpu_request

    if spec.mem_per_task:
        mem_request = normalize_memory_request(spec.mem_per_task)
        resources["requests"]["memory"] = mem_request
        resources["limits"]["memory"] = mem_request
    if spec.gpus_per_task > 0:
        resources["limits"][gpu_resource_name] = str(spec.gpus_per_task)
    return resources


class KubernetesTransformer(TransformerBase):
    """
    A Kubernetes Transformer is a very manual transformation to convert
    a standard JobSpec to a Kubernetes Job.
    """

    def convert(self, spec):
        """
        Convert a normalized jobspec to the format here.
        """
        # If we don't have a job name, generate one
        # Also sanitize for Kubernetes (DNS-1123 subdomain name)
        job_name = spec.job_name or JobNamer().generate()
        job_name = re.sub(r"[^a-z0-9-]", "-", job_name.lower()).strip("-")

        # This gets passed from flux attribute, --setattr=container_image=<value>
        if not spec.container_image:
            print("Warning: spec.container_image not defined, will create dummy name.")
            spec.container_image = f"test-{job_name}"

        # Parse the application container first.
        command = spec.executable if spec.executable else ["/bin/bash", "-c"]
        container = {
            "name": job_name,
            "image": spec.container_image,
            "command": command,
            "args": spec.arguments or None,
        }

        resources = get_resources(spec)
        if resources["requests"] or resources["limits"]:
            container["resources"] = resources
        if spec.working_directory:
            container["workingDir"] = spec.working_directory
        if spec.environment:
            container["env"] = [{"name": k, "value": v} for k, v in spec.environment.items()]

        # This is the spec for the pod template
        template_pod_spec = {"containers": [container], "restartPolicy": "Never"}
        pod_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": job_name},
            "spec": {
                "template": {"spec": template_pod_spec},
                "backoffLimit": 0,
            },
        }

        if spec.priority:
            pod_spec["priorityClassName"] = str(spec.priority)

        # If >1 node, set affinity to spread across
        if spec.num_nodes > 1:
            pod_spec.setdefault("affinity", {})
            pod_spec["affinity"]["podAntiAffinity"] = {
                "requiredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "labelSelector": {
                            "matchExpressions": [
                                {"key": "job-name", "operator": "In", "values": [spec.job_name]}
                            ]
                        },
                        "topologyKey": "kubernetes.io/hostname",
                    }
                ]
            }

        # This controls the Job controller itself (parallelism, deadline, etc.)
        job_spec = {
            "parallelism": spec.num_nodes,
            "completions": spec.num_nodes,
            "backoffLimit": 4,
            "template": {"metadata": {"labels": {"job-name": spec.job_name}}, "spec": pod_spec},
        }

        # This is already in seconds
        if spec.wall_time:
            job_spec["activeDeadlineSeconds"] = spec.wall_time

        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": spec.job_name,
            },
            "spec": job_spec,
        }

        # Add extra attributes that aren't relevant as labels
        if spec.account:
            job["metadata"].setdefault("labels", {})
            job["metadata"]["labels"]["account"] = spec.account
        return job

    def parse(self, job_manifest):
        """
        Parses a Kubernetes Job manifest (dict or YAML string) into a JobSpec.
        """
        if isinstance(job_manifest, str):
            manifest = yaml.safe_load(job_manifest)
        else:
            manifest = job_manifest

        spec = JobSpec()

        # Metadata
        metadata = manifest.get("metadata", {})
        spec.job_name = metadata.get("name")
        spec.account = metadata.get("labels", {}).get("account")

        # Job Spec and template
        job_spec = manifest.get("spec", {})
        spec.num_nodes = job_spec.get("parallelism", 1)
        spec.wall_time = job_spec.get("activeDeadlineSeconds")
        pod_template = job_spec.get("template", {})
        pod_spec = pod_template.get("spec", {})

        if not pod_spec.get("containers"):
            raise ValueError("Kubernetes manifest has no containers to parse.")

        containers = pod_spec["containers"]
        if len(containers) > 1:
            print("Warning: job has >1 container, will use first.")

        container = containers[0]
        spec.container_image = container.get("image")
        spec.executable = container.get("command")
        spec.arguments = container.get("args", [])
        spec.working_directory = container.get("workingDir")

        # Environment
        env_list = container.get("env", [])
        if env_list:
            spec.environment = {item["name"]: item["value"] for item in env_list}

        # Resources
        resources = container.get("resources", {})
        limits = resources.get("limits", {})
        requests = resources.get("requests", {})

        if gpu_resource_name in limits:
            spec.gpus_per_task = int(limits[gpu_resource_name])

        if "memory" in requests:
            spec.mem_per_task = parse_memory(requests["memory"])

        if "cpu" in requests:
            cpu_val = parse_cpu(requests["cpu"])
            # convert uses num_tasks for the CPU request
            # if it's > 1, otherwise it uses cpus_per_task. We map it back to num_tasks.
            spec.num_tasks = cpu_val
            if cpu_val == 1:
                spec.cpus_per_task = 1

        # GPU Type from Node Selector
        node_selector = pod_spec.get("nodeSelector", {})
        if gpu_product_label in node_selector:
            spec.gpu_type = node_selector[gpu_product_label]

        # Scheduling
        if pod_spec.get("priorityClassName"):
            try:
                spec.priority = int(pod_spec.get("priorityClassName"))
            except (ValueError, TypeError):
                spec.priority = None

        return spec
