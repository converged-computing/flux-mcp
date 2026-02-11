FROM fluxrm/flux-sched:noble

# docker build -t ghcr.io/converged-computing/flux-mcp:latest .
# Install system-level dependencies for HPC introspection
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip python3-venv && \
    apt remove -y python3-zipp && apt remove -y python3-typing-extensions \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/code

WORKDIR /code
COPY . /code
RUN python3 -m pip install mcp-serve --no-cache-dir --break-system-packages && python3 -m pip install . --no-cache-dir --break-system-packages
EXPOSE 8089
ENTRYPOINT ["mcpserver", "start"]

# Default command if no arguments are provided.
# We bind to 0.0.0.0 so the server is reachable outside the container.
CMD ["-t", "http", "--host", "0.0.0.0", "--port", "8089", "--config", "/code/examples/servers/flux-mcp.yaml"]
