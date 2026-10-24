import inspect
from collections import abc

# Submit options without a jobspec property, applied with the jobspec calls that
# JobspecV1._set_extra_options makes in newer Flux.
SHELL_OPTIONS = {"env_expand": "env-expand", "rlimits": "rlimit"}
ATTRIBUTES = {"name": "job.name", "queue": "queue", "bank": "bank"}

# File output paths that newer Flux leaves as the default (KVS) output.
DEFAULT_OUTPUT = ("none", "kvs")


def is_settable_property(cls, name):
    """Return True if name is a settable property on cls."""
    attr = inspect.getattr_static(cls, name, None)
    return isinstance(attr, property) and attr.fset is not None


def apply_jobspec_options(jobspec, options):
    """Apply submit options to a jobspec as newer Flux does; return the names it cannot set."""
    unsupported = []
    for key, value in options.items():
        if value is None or value is False or key == "label_io":
            continue
        if key in SHELL_OPTIONS:
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
