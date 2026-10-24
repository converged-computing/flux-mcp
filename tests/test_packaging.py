from importlib.metadata import requires


def requirements():
    """Return the install requirements of the installed flux-mcp distribution."""
    return [r.replace(" ", "") for r in requires("flux-mcp") or []]


def test_requires_mcp_2():
    assert "mcp>=2" in requirements()


def test_requires_fastmcp_4():
    assert "fastmcp>=4" in requirements()
