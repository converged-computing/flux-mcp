# Global state to hold the scheduler instance
# I don't know if there is a use case for NOT holding a state.

RESOURCE_CLI = None


def get_resource_client(force_new: bool = False):
    """
    Lazy loader for the ReapiCli, in case the user doesn't
    have flux-sched-py installed.
    """
    global RESOURCE_CLI

    # 1. Lazy Import check
    try:
        from flux_sched.reapi_cli import ReapiCli
    except ImportError:
        raise ImportError(
            "The 'flux-sched' library is required to use scheduler tools. "
            "Please install it within your Flux environment."
        )

    # If we already have one (and not forcing new) just use it.
    # Otherwise, make a new one!
    if RESOURCE_CLI is None or force_new:
        RESOURCE_CLI = ReapiCli()

    return RESOURCE_CLI
