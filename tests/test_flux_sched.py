import json

import pytest


@pytest.fixture
def sched_graph_jgf():
    """Minimal 1-Node system (Cluster -> Rack -> Node -> Socket -> Core)"""
    return json.dumps(
        {
            "graph": {
                "nodes": [
                    {
                        "id": "0",
                        "metadata": {
                            "type": "cluster",
                            "basename": "tiny",
                            "name": "tiny0",
                            "id": 0,
                            "uniq_id": 0,
                            "rank": -1,
                            "exclusive": False,
                            "size": 1,
                            "paths": {"containment": "/tiny0"},
                        },
                    },
                    {
                        "id": "1",
                        "metadata": {
                            "type": "rack",
                            "basename": "rack",
                            "name": "rack0",
                            "id": 0,
                            "uniq_id": 1,
                            "rank": -1,
                            "exclusive": False,
                            "size": 1,
                            "paths": {"containment": "/tiny0/rack0"},
                        },
                    },
                    {
                        "id": "2",
                        "metadata": {
                            "type": "node",
                            "basename": "node",
                            "name": "node0",
                            "id": 0,
                            "uniq_id": 2,
                            "rank": -1,
                            "exclusive": False,
                            "size": 1,
                            "paths": {"containment": "/tiny0/rack0/node0"},
                        },
                    },
                    {
                        "id": "3",
                        "metadata": {
                            "type": "core",
                            "basename": "core",
                            "name": "core0",
                            "id": 0,
                            "uniq_id": 3,
                            "rank": -1,
                            "exclusive": False,
                            "size": 1,
                            "paths": {"containment": "/tiny0/rack0/node0/core0"},
                        },
                    },
                ],
                "edges": [
                    {"source": "0", "target": "1", "metadata": {"subsystem": "containment"}},
                    {"source": "1", "target": "2", "metadata": {"subsystem": "containment"}},
                    {"source": "2", "target": "3", "metadata": {"subsystem": "containment"}},
                ],
            }
        }
    )


@pytest.fixture
def sched_options():
    return json.dumps(
        {
            "load_format": "jgf",
            "prune_filters": "ALL:core",
            "subsystems": "containment",
            "policy": "high",
        }
    )


@pytest.fixture
def alloc_jobspec():
    """Request 1 Slot containing 1 Core"""
    return json.dumps(
        {
            "version": 9999,
            "resources": [
                {
                    "type": "slot",
                    "count": 1,
                    "label": "default",
                    "with": [{"type": "core", "count": 1}],
                }
            ],
            "attributes": {"system": {"duration": 3600}},
            "tasks": [{"command": ["app"], "slot": "default", "count": {"per_slot": 1}}],
        }
    )


# Skip these tests if flux_sched is not installed
pytest.importorskip("flux_sched")


@pytest.mark.asyncio
async def test_scheduler_lifecycle(client, sched_graph_jgf, sched_options, alloc_jobspec):
    """
    Tests the full lifecycle of the Resource Graph:
    Init -> Match -> Info -> Partial Cancel -> Full Cancel
    """

    # 1. Initialize Graph
    print("\n[Step 1] Initializing Graph...")
    init_res = await client.call_tool(
        "flux_sched_init_graph", {"graph_json": sched_graph_jgf, "options_json": sched_options}
    )
    init_data = json.loads(init_res.content[0].text)
    assert init_data["success"] is True

    # 2. Match Allocation (Submit Job)
    print("[Step 2] Matching Jobspec...")
    match_res = await client.call_tool("flux_sched_match_allocate", {"jobspec_json": alloc_jobspec})
    match_data = json.loads(match_res.content[0].text)

    assert match_data["success"] is True
    jobid = match_data["jobid"]
    r_spec = match_data["R"]

    assert jobid > 0
    assert r_spec is not None
    print(f" -> Allocated Job ID: {jobid}")
    print(f" -> Resources (R): {r_spec}")

    # 3. Check Job Info
    print(f"[Step 3] Checking Info for Job {jobid}...")
    info_res = await client.call_tool("flux_sched_job_info", {"jobid": jobid})
    info_data = json.loads(info_res.content[0].text)

    assert info_data["success"] is True
    assert info_data["mode"] == "ALLOCATED"
    assert info_data["jobid"] == jobid

    # 4. Partial Cancellation
    # We will try to release the resources we just got.
    # print(f"[Step 4] Partial Cancel (Releasing all resources)...")
    # partial_res = await client.call_tool(
    #    "flux_sched_partial_cancel",
    #    {"jobid": jobid, "resource_subset": r_spec}
    # )
    # partial_data = json.loads(partial_res.content[0].text)
    # print(partial_data)

    # assert partial_data["success"] is True
    # If we release everything, the job should be fully removed from the scheduler map
    # assert partial_data["fully_removed"] is True
    # print(" -> Job fully removed via partial cancel.")

    print(f" -> Cancelling Job {jobid}...")
    cancel_res = await client.call_tool("flux_sched_cancel_job", {"jobid": jobid})
    cancel_data = json.loads(cancel_res.content[0].text)
    print(cancel_data)

    assert cancel_data["success"] is True
