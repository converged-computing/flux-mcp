import sys

sys.modules["yaml.cyaml"] = None

import json

import flux
import flux.job


def flux_handle_delegation(jobid, remote_uri, jobspec_str):
    """
    Performs only the remote job submission.
    Returns the remote job ID on success, or -1 on failure.
    The C worker thread will handle waiting and resolving the dependency.
    I tried doing it in Python but it was weird and janky.
    """
    remote_h = flux.Flux(remote_uri)
    print(f"Delegate: Starting remote submission for job {jobid} to {remote_uri}")

    jobspec = json.loads(jobspec_str)
    if (
        "attributes" in jobspec
        and "system" in jobspec["attributes"]
        and "dependencies" in jobspec["attributes"]["system"]
    ):
        del jobspec["attributes"]["system"]["dependencies"]

    # This would do it infinitely...
    if "delegate" in jobspec["attributes"]["system"]:
        del jobspec["attributes"]["system"]["delegate"]
    encoded_jobspec = json.dumps(jobspec)

    # Use the one helper function that has been proven to work reliably.
    future = flux.job.submit_async(remote_h, encoded_jobspec)
    remote_jobid = future.get_id()
    aslong = flux.job.JobID(remote_jobid)

    print(f"Delegate: Job {jobid} submitted. Remote jobid is {remote_jobid}")
    return aslong
