import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import flux_strands  # noqa: E402


def call(client, name, **args):
    """Call a tool through the Strands MCP client and return its JSON result."""
    result = client.call_tool_sync(f"test-{name}", name, args)
    assert result["status"] == "success", result
    return json.loads(result["content"][0]["text"])


def test_server_gets_only_server_env(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    env = flux_strands.server_params().env
    assert set(env) <= set(flux_strands.SERVER_ENV)
    assert env["FLUX_URI"] == os.environ["FLUX_URI"]


def test_client_tools_and_filter():
    with flux_strands.flux_client() as client:
        tools = sorted(tool.tool_name for tool in client.list_tools_sync())
        assert tools == sorted(flux_strands.FLUX_TOOLS)
    with flux_strands.flux_client(["flux_resource_list"]) as client:
        assert [tool.tool_name for tool in client.list_tools_sync()] == ["flux_resource_list"]


def test_submit_logs_info_cancel():
    with flux_strands.flux_client() as client:
        job = call(client, "flux_submit_job", command=["echo", "from-strands"], num_tasks=2)
        assert job["success"], job["error"]
        logs = call(client, "flux_get_job_logs", job_id=job["job_id"])
        info = call(client, "flux_get_job_info", job_id=job["job_id"])
        assert logs["lines"] == ["from-strands\n", "from-strands\n"]
        assert info["info"]["status"] == "COMPLETED"
        long = call(client, "flux_submit_job", command=["sleep", "300"])
        assert call(client, "flux_cancel_job", job_id=long["job_id"])["success"]


def test_jobs_get_user_environment(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    with flux_strands.flux_client() as client:
        job = call(client, "flux_submit_job", command=["env"])
        lines = "".join(call(client, "flux_get_job_logs", job_id=job["job_id"])["lines"])
    env = {line.split("=", 1)[0] for line in lines.splitlines() if "=" in line}
    assert {"HOME", "USER", "PATH"} <= env
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_agent_and_model(monkeypatch):
    with flux_strands.flux_client() as client:
        agent = flux_strands.flux_agent(client)
        assert sorted(agent.tool_names) == sorted(flux_strands.FLUX_TOOLS)
    monkeypatch.setenv("STRANDS_MODEL", "test-model-id")
    with flux_strands.flux_client(["flux_resource_list"]) as client:
        assert flux_strands.flux_agent(client).model.config["model_id"] == "test-model-id"


def test_script_exits_on_end_of_input():
    script = str(HERE / "flux_strands.py")
    proc = subprocess.run(
        [sys.executable, script], input="", capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    assert "flux>" in proc.stdout
