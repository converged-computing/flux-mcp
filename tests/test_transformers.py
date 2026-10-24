import itertools
import json
import subprocess
import tempfile

import pytest

from flux_mcp.validate.validate import Validator


@pytest.fixture
def batch_scripts_matrix():
    """
    Returns a dictionary of equivalent 'Hello World' jobs
    (2 nodes, 1 hour walltime) for all supported schedulers.
    """
    return {
        "flux": """#!/bin/bash
#FLUX: -N 2
#FLUX: -t 60m
echo "hello world"
""",
        "slurm": """#!/bin/bash
#SBATCH --nodes=2
#SBATCH --time=01:00:00
echo "hello world"
""",
        "pbs": """#!/bin/bash
#PBS -l nodes=2
#PBS -l walltime=01:00:00
echo "hello world"
""",
        "lsf": """#!/bin/bash
#BSUB -n 2
#BSUB -W 60
echo "hello world"
""",
        "cobalt": """#!/bin/bash
#COBALT -n 2
#COBALT -t 60
echo "hello world"
""",
        "oar": """#!/bin/bash
#OAR -l nodes=2,walltime=1:00:00
echo "hello world"
""",
        "kubernetes": """apiVersion: batch/v1
kind: Job
metadata:
  name: test-job
spec:
  template:
    spec:
      containers:
      - name: main
        image: ubuntu:latest
        command: ["echo", "hello world"]
        resources:
          limits:
            cpu: "2"
      restartPolicy: Never
""",
    }


@pytest.mark.asyncio
async def test_transform_matrix_explicit(client, batch_scripts_matrix):
    """
    Matrix Test: Converts every format TO every other format
    using explicit 'from_format' and 'to_format' arguments.
    """
    formats = list(batch_scripts_matrix.keys())

    # Generate all permutations (src, dest)
    # We use permutations to test A->B, but we also verify A->A works (identity)
    combinations = list(itertools.product(formats, formats))

    print(f"\nRunning {len(combinations)} transformation tests...")

    failures = []

    for src_fmt, dest_fmt in combinations:
        script_content = batch_scripts_matrix[src_fmt]

        print(f"Testing: {src_fmt.upper()} -> {dest_fmt.upper()}")

        result = await client.call_tool(
            "transform_jobspec",
            {"batch_job": script_content, "from_format": src_fmt, "to_format": dest_fmt},
        )

        # Parse result
        try:
            data = json.loads(result.content[0].text)
        except json.JSONDecodeError:
            failures.append(f"{src_fmt}->{dest_fmt}: Tool returned invalid JSON")
            continue

        # Check for success
        if data.get("status") != "SUCCESS":
            print(data)
            error_msg = data.get("error", "Unknown Error")
            # We log failures but continue testing the rest of the matrix
            failures.append(f"{src_fmt}->{dest_fmt}: {error_msg}")
        else:
            # Basic validation that result is not empty
            if not data.get("jobspec"):
                failures.append(f"{src_fmt}->{dest_fmt}: Returned SUCCESS but 'jobspec' was empty")

    # Final Assertion
    if failures:
        pytest.fail(f"Matrix Transformation Failures:\n" + "\n".join(failures))


@pytest.mark.asyncio
async def test_transform_auto_detect(client, batch_scripts_matrix):
    """
    Test automatic detection logic.
    We convert ALL formats to 'flux' without specifying 'from_format'.
    """
    dest_fmt = "flux"
    failures = []

    for src_fmt, script_content in batch_scripts_matrix.items():
        # Kubernetes is often hard to auto-detect from simple strings if not full YAML,
        # but let's assume the detector handles the 'apiVersion' line.

        print(f"Testing Auto-Detect: {src_fmt.upper()} -> {dest_fmt.upper()}")

        result = await client.call_tool(
            "transform_jobspec",
            {
                "batch_job": script_content,
                "to_format": dest_fmt,
                "from_format": None,  # Trigger auto-detection
            },
        )

        data = json.loads(result.content[0].text)

        if data.get("status") != "SUCCESS":
            failures.append(f"Auto-detect {src_fmt}: {data.get('error')}")

    if failures:
        pytest.fail(f"Auto-detection Failures:\n" + "\n".join(failures))


# Duration (seconds) each matrix script asks for; the Kubernetes Job sets none.
EXPECTED_DURATION = {
    "flux": 3600,
    "slurm": 3600,
    "pbs": 3600,
    "lsf": 3600,
    "cobalt": 3600,
    "oar": 3600,
    "kubernetes": 0,
}

# These parsers do not read the time limit yet.
TIME_NOT_PARSED = {"pbs", "lsf", "cobalt", "oar"}


def flux_batch_jobspec(script):
    """Return the jobspec flux batch would submit for a batch script."""
    with tempfile.NamedTemporaryFile("w", suffix=".sh") as handle:
        handle.write(script)
        handle.flush()
        proc = subprocess.run(
            ["flux", "batch", "--dry-run", handle.name], capture_output=True, text=True
        )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


async def transform(client, script, src_fmt, dest_fmt):
    """Transform a batch script and return the rendered result."""
    result = await client.call_tool(
        "transform_jobspec",
        {"batch_job": script, "to_format": dest_fmt, "from_format": src_fmt},
    )
    data = json.loads(result.content[0].text)
    assert data["status"] == "SUCCESS", data.get("error")
    return data["jobspec"]


@pytest.mark.asyncio
@pytest.mark.parametrize("src_fmt", list(EXPECTED_DURATION))
async def test_flux_output_accepted_by_flux_batch(client, batch_scripts_matrix, src_fmt):
    script = await transform(client, batch_scripts_matrix[src_fmt], src_fmt, "flux")
    flux_batch_jobspec(script)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "src_fmt",
    [
        (
            pytest.param(fmt, marks=pytest.mark.xfail(strict=True, reason="time limit not parsed"))
            if fmt in TIME_NOT_PARSED
            else fmt
        )
        for fmt in EXPECTED_DURATION
    ],
)
async def test_flux_output_keeps_time_limit(client, batch_scripts_matrix, src_fmt):
    script = await transform(client, batch_scripts_matrix[src_fmt], src_fmt, "flux")
    jobspec = flux_batch_jobspec(script)
    assert jobspec["attributes"]["system"]["duration"] == EXPECTED_DURATION[src_fmt]


@pytest.mark.asyncio
async def test_flux_to_slurm_keeps_resources_and_command(client, batch_scripts_matrix):
    script = await transform(client, batch_scripts_matrix["flux"], "flux", "slurm")
    for line in ["#SBATCH --nodes=2", "#SBATCH --time=01:00:00", 'echo "hello world"']:
        assert line in script.splitlines()


def test_flux_directives_map_to_jobspec(tmp_path):
    script = (
        "#!/bin/bash\n#FLUX: -N 2\n#FLUX: -n 4\n#FLUX: -c 2\n#FLUX: -t 1h\n"
        "#FLUX: --job-name=demo\n#FLUX: -q batch\n#FLUX: --env=A=1\n#FLUX: --urgency=20\n"
        "echo hi\n"
    )
    path = tmp_path / "job.sh"
    path.write_text(script)
    validator = Validator("batch")
    js = validator.parse(str(path))
    assert (js.num_nodes, js.num_tasks, js.cpus_per_task) == (2, 4, 2)
    assert (js.wall_time, js.job_name, js.queue) == (3600, "demo", "batch")
    assert js.environment == {"A": "1"}
    assert js.script == ["echo hi"]
    assert validator.unhandled(str(path)) == {"urgency"}
