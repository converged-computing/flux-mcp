import inspect

import flux.job
import pytest

from flux_mcp.utils import apply_jobspec_options, flux_version

COMMAND = {"command": ["true"], "num_tasks": 2}
ENV = {"PATH": "/usr/bin:/bin"}

CASES = {
    "duration": {"duration": 60},
    "environment": {"environment": {"ONLY": "1"}},
    "env_expand": {"env_expand": {"X": "{{id}}"}},
    "cwd": {"cwd": "/tmp"},
    "rlimits": {"rlimits": {"nofile": 512}},
    "name": {"name": "agent-job"},
    "input": {"input": "/tmp/in.txt"},
    "output": {"output": "/tmp/out.txt"},
    "error": {"error": "/tmp/err.txt"},
    "label_io": {"label_io": True, "output": "/tmp/out.txt", "error": "/tmp/err.txt"},
    "label_io_alone": {"label_io": True},
    "kvs_output": {"output": "kvs", "error": "none"},
    "unbuffered": {"unbuffered": True},
    "queue": {"queue": "batch"},
    "bank": {"bank": "agent-bank"},
}
CASES["all"] = {k: v for case in CASES.values() for k, v in case.items()}

FROM_COMMAND_OPTIONS = set(inspect.signature(flux.job.JobspecV1.from_command).parameters)


def options_jobspec(options):
    """Return the jobspec dict built with apply_jobspec_options."""
    jobspec = flux.job.JobspecV1.from_command(**COMMAND)
    assert apply_jobspec_options(jobspec, {"environment": ENV, **options}) == []
    return jobspec.jobspec


def from_command_jobspec(options):
    """Return the jobspec dict built by from_command with the options as arguments."""
    return flux.job.JobspecV1.from_command(**COMMAND, **{"environment": ENV, **options}).jobspec


@pytest.mark.parametrize("case", CASES, ids=str)
def test_matches_from_command_arguments(case):
    options = CASES[case]
    if not set(options) <= FROM_COMMAND_OPTIONS:
        pytest.skip("this Flux's from_command does not take these options")
    assert options_jobspec(options) == from_command_jobspec(options)


class Recorder:
    """A jobspec stand-in with no properties, recording setattr calls."""

    def __init__(self):
        self.calls = []

    def setattr(self, key, value):
        self.calls.append(("setattr", key, value))

    def setattr_shell_option(self, key, value):
        self.calls.append(("shell", key, value))


def test_options_without_setter_are_reported():
    recorder = Recorder()
    options = {"output": "/tmp/out.txt", "unbuffered": True, "name": "n"}
    assert apply_jobspec_options(recorder, options) == ["output", "unbuffered"]
    assert recorder.calls == [("setattr", "job.name", "n")]


def test_unset_options_are_skipped():
    recorder = Recorder()
    options = {"name": None, "label_io": False, "unbuffered": False, "output": None}
    assert apply_jobspec_options(recorder, options) == []
    assert recorder.calls == []


def test_shell_and_attribute_options():
    recorder = Recorder()
    options = {"rlimits": {"nofile": 1}, "env_expand": {"X": "y"}, "queue": "q", "bank": "b"}
    assert apply_jobspec_options(recorder, options) == []
    assert recorder.calls == [
        ("shell", "rlimit", {"nofile": 1}),
        ("shell", "env-expand", {"X": "y"}),
        ("setattr", "queue", "q"),
        ("setattr", "bank", "b"),
    ]


@pytest.mark.parametrize("option", ["rlimits", "env_expand"])
def test_mapping_options_must_be_mappings(option):
    with pytest.raises(ValueError, match="must be a mapping"):
        apply_jobspec_options(Recorder(), {option: ["not", "a", "mapping"]})


class Handle:
    """A Flux handle stand-in that reports a version attribute."""

    def __init__(self, version):
        self.version = version

    def attr_get(self, name):
        assert name == "version"
        return self.version


@pytest.mark.parametrize(
    "value,expected",
    [("0.89.0-124-g11c9d4c0f", (0, 89, 0)), ("0.70.0", (0, 70, 0)), ("1.2.3rc1", (1, 2, 3))],
)
def test_flux_version(value, expected):
    assert flux_version(Handle(value)) == expected


@pytest.mark.parametrize(
    "version,applied",
    [((0, 69, 0), False), ((0, 70, 0), True), ((0, 89, 0), True), (None, True)],
    ids=["0.69", "0.70", "0.89", "unknown"],
)
def test_env_expand_needs_flux_0_70(version, applied):
    recorder = Recorder()
    result = apply_jobspec_options(recorder, {"env_expand": {"X": "y"}}, version)
    if applied:
        assert result == []
        assert recorder.calls == [("shell", "env-expand", {"X": "y"})]
    else:
        assert result == ["env_expand"]
        assert recorder.calls == []


def test_rlimits_not_version_gated():
    recorder = Recorder()
    assert apply_jobspec_options(recorder, {"rlimits": {"nofile": 1}}, (0, 64, 0)) == []
    assert recorder.calls == [("shell", "rlimit", {"nofile": 1})]
