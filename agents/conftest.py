import os

import pytest


def pytest_configure(config):
    """Stop early unless the tests run inside a Flux instance."""
    if not os.environ.get("FLUX_URI"):
        pytest.exit("Run the tests inside Flux with flux start --test-size=2 python -m pytest", 2)
