__version__ = "0.0.22"
AUTHOR = "Vanessa Sochat"
AUTHOR_EMAIL = "vsoch@users.noreply.github.com"
NAME = "flux-mcp"
PACKAGE_URL = "https://github.com/converged-computing/flux-mcp"
KEYWORDS = "mcp, model context protocol, flux, flux framework, hpc, scheduling, workloads"
DESCRIPTION = "Agentic MCP tools for Flux Framework and HPC"
LICENSE = "LICENSE"


################################################################################
# TODO vsoch: refactor this to use newer pyproject stuff.

INSTALL_REQUIRES = (
    # The servers use mcp.server.mcpserver (mcp 2.x) and the fastmcp 4.x API.
    ("mcp", {"spec": ">=2"}),
    ("fastmcp", {"spec": ">=4"}),
    ("rich", {"min_version": None}),
    ("fastapi", {"min_version": None}),
    # For Flux
    ("pyyaml", {"min_version": None}),
    ("ply", {"min_version": None}),
)

TESTS_REQUIRES = (
    ("pytest", {"min_version": "4.6.2"}),
    ("pytest-asyncio", {"min_version": None}),
)
INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
