import os

import flux_mcp.utils as utils

from .cobalt import Transformer as CobaltTransformer
from .flux import Transformer as FluxTransformer
from .kubernetes import Transformer as KubernetesTransformer
from .lsf import Transformer as LSFTransformer
from .moab import Transformer as MoabTransformer
from .oar import Transformer as OARTransformer
from .pbs import Transformer as PBSTransformer
from .slurm import Transformer as SlurmTransformer

plugins = {
    "kubernetes": KubernetesTransformer,
    "flux": FluxTransformer,
    "slurm": SlurmTransformer,
    "pbs": PBSTransformer,
    "lsf": LSFTransformer,
    "oar": OARTransformer,
    "cobalt": CobaltTransformer,
    "moab": MoabTransformer,
}


def get_transformer(name, solver=None):
    if name not in plugins:
        raise ValueError(f"{name} is not a valid transformer.")
    return plugins[name](solver)


def detect_transformer(content):
    """
    Quick and dirty detection.
    """
    # Support being provided the string or filepath
    if os.path.exists(content):
        content = utils.read_file(content)
    if "#FLUX" in content and "FLUX_CAPACITOR" not in content:
        return "flux"
    if "#MSUB " in content:
        return "moab"
    if "#SBATCH " in content:
        return "slurm"
    if "kind:" in content and "Job" in content:
        return "kubernetes"
    if "#PBS " in content:
        return "pbs"
    if "#BSUB" in content:
        return "lsf"
    if "#OAR" in content:
        return "oar"
    if "#COBALT" in content:
        return "cobalt"
    raise ValueError("Unkown transformer.")
