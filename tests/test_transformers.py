import itertools
import json

import pytest


@pytest.fixture
def batch_scripts_matrix():
    """
    Returns a dictionary of equivalent 'Hello World' jobs
    (2 nodes, 1 hour walltime) for all supported schedulers.
    """
    return {
        "flux": """#!/bin/bash
#FLUX -N 2
#FLUX -t 60m
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
