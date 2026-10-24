import os
import sys

# Jobs inherit the server environment, and the server does not need agent credentials.
DEFAULT_UNSET = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_BEARER_TOKEN_BEDROCK",
]

REEXEC = "FLUX_MCP_STDIO_REEXEC"


def fail(message):
    """Print an error to stderr and exit."""
    print(f"flux-mcp-stdio: {message}", file=sys.stderr)
    sys.exit(1)


def ensure_flux_bindings():
    """Re-run under `flux env` if the Flux Python bindings are not importable."""
    try:
        import flux  # noqa: F401

        return
    except ImportError:
        pass
    if os.environ.get(REEXEC):
        fail("cannot import the flux Python bindings, even under 'flux env'")
    os.environ[REEXEC] = "1"
    argv = ["flux", "env", sys.executable, "-m", "flux_mcp.server.stdio", *sys.argv[1:]]
    try:
        os.execvp("flux", argv)
    except FileNotFoundError:
        fail("flux not on PATH")


def check_instance():
    """Exit unless FLUX_URI points at a reachable instance owned by this user."""
    uri = os.environ.get("FLUX_URI")
    if not uri:
        fail("FLUX_URI not set; start the agent inside your allocation")

    import flux

    try:
        owner = int(flux.Flux().attr_get("security.owner"))
    except OSError as e:
        fail(f"cannot reach Flux at {uri}: {e}")
    if owner != os.getuid():
        fail(f"instance at {uri} is owned by uid {owner}, not {os.getuid()}")


def scrub_environment():
    """Remove agent credentials (or FLUX_MCP_UNSET names) from the environment."""
    names = os.environ.get("FLUX_MCP_UNSET")
    for name in names.split() if names is not None else DEFAULT_UNSET:
        os.environ.pop(name, None)
    os.environ.pop(REEXEC, None)


def main():
    """Run the flux-mcp stdio server for the Flux instance in FLUX_URI."""
    if not os.environ.get("FLUX_URI"):
        fail("FLUX_URI not set; start the agent inside your allocation")
    ensure_flux_bindings()
    check_instance()
    scrub_environment()

    from flux_mcp.server.__main__ import main as serve

    serve()


if __name__ == "__main__":
    main()
