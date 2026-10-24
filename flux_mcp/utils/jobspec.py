import inspect
import re
from collections import abc

# Submit options without a jobspec property, applied with the jobspec calls that
# JobspecV1._set_extra_options makes in newer Flux.
SHELL_OPTIONS = {"env_expand": "env-expand", "rlimits": "rlimit"}
ATTRIBUTES = {"name": "job.name", "queue": "queue", "bank": "bank"}

# Shell options the job shell silently ignores before this flux-core version.
SHELL_OPTION_MIN_VERSION = {"env-expand": (0, 70, 0)}

# File output paths that newer Flux leaves as the default (KVS) output.
DEFAULT_OUTPUT = ("none", "kvs")


def is_settable_property(cls, name):
    """Return True if name is a settable property on cls."""
    attr = inspect.getattr_static(cls, name, None)
    return isinstance(attr, property) and attr.fset is not None


def flux_version(handle):
    """Return the flux-core version of the instance as a tuple, e.g. (0, 89, 0)."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", handle.attr_get("version"))
    return tuple(int(part) for part in match.groups())


def apply_jobspec_options(jobspec, options, version=None):
    """
    Apply submit options to a jobspec as newer Flux does; return the names it
    cannot set, including shell options the instance's job shell (version) ignores.
    """
    unsupported = []
    for key, value in options.items():
        if value is None or value is False or key == "label_io":
            continue
        if key in SHELL_OPTIONS:
            minimum = SHELL_OPTION_MIN_VERSION.get(SHELL_OPTIONS[key])
            if version is not None and minimum and version < minimum:
                unsupported.append(key)
                continue
            if not isinstance(value, abc.Mapping):
                raise ValueError(f"{key} must be a mapping")
            jobspec.setattr_shell_option(SHELL_OPTIONS[key], value)
        elif key in ATTRIBUTES:
            jobspec.setattr(ATTRIBUTES[key], value)
        elif key in ("output", "error") and value in DEFAULT_OUTPUT:
            continue
        elif is_settable_property(type(jobspec), key):
            setattr(jobspec, key, value)
            # label_io only labels file output, as in newer Flux.
            if key in ("output", "error") and options.get("label_io"):
                stream = "stdout" if key == "output" else "stderr"
                jobspec.setattr_shell_option(f"output.{stream}.label", True)
        else:
            unsupported.append(key)
    return unsupported
