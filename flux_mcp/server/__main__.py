from mcp.server.mcpserver import MCPServer

from flux_mcp.registry import TOOLS
from flux_mcp.server.threads import run_in_thread


def register_with(server_instance):
    """
    Register (mount) flux-mcp tools to a given MCP server instance.
    """
    # 1. Identify which kind of server it is (Optional robust check)
    if hasattr(server_instance, "add_tool"):
        # MCPServer pattern
        for func in TOOLS:
            server_instance.add_tool(run_in_thread(func))

    elif hasattr(server_instance, "register_tool"):
        # Low-level Server pattern (requires more manual schema work)
        raise NotImplementedError("Please use MCPServer or wrapper")

    else:
        raise TypeError("Server instance must support .add_tool()")


def get_server():
    mcp = MCPServer(
        name="Flux MCP Gateway",
        instructions="This server provides tools for Flux Framework.",
        website_url="https://github.com/converged-computing/flux-mcp",
    )
    register_with(mcp)
    return mcp


def main():
    mcp = get_server()
    mcp.run()


if __name__ == "__main__":
    main()
