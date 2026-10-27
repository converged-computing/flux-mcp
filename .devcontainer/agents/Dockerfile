FROM fluxrm/flux-sched:noble

LABEL maintainer="Vanessasaurus <@vsoch>"

# Match the default user id for a single system so we aren't root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
ARG CLAUDE_CODE_VERSION=latest
ARG CODEX_VERSION=latest
ARG OPENCODE_VERSION=latest

# Claude Code needs Node 22 or newer and Ubuntu has Node 18, so Node comes from nodejs.org
ARG NODE_MAJOR=22

ENV USERNAME=${USERNAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}
USER root

# Interactive utilities, Python tools, and the firewall tools for init-firewall.sh
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        curl \
        less \
        fd-find \
        bats \
        ripgrep \
        sqlite3 \
        jq \
        python3-pip \
        python3-venv \
        iptables \
        ipset \
        iproute2 \
        dnsutils \
        dnsmasq-base \
        aggregate && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m pip install --break-system-packages 'black~=26.1'

# Add the group and user that match our ids
RUN groupadd -g ${USER_GID} ${USERNAME} && \
    adduser --disabled-password --uid ${USER_UID} --gid ${USER_GID} --gecos "" ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# Install flux-sched python bindings
RUN python3 -m pip install Cython setuptools --break-system-packages && git clone https://github.com/flux-framework/flux-sched /tmp/flux-sched && \
    git clone https://github.com/flux-framework/flux-sched-py /tmp/flux-sched-py && \
    mv /tmp/flux-sched-py/ /tmp/flux-sched/resource/reapi/bindings/python && \
    cd /tmp/flux-sched && \
    ./configure --prefix=/usr && make && make install && \
    cd /tmp/flux-sched/resource/reapi/bindings/python && \
    python3 setup.py sdist bdist_wheel && \
    pip install --break-system-packages dist/flux_sched-0.0.0*.whl

ENV PYTHONPATH="/usr/lib/flux/python3.12/"

# The latest Node release in NODE_MAJOR, checked against the checksums published with it
RUN case "$(uname -m)" in \
        x86_64) arch=x64 ;; \
        aarch64) arch=arm64 ;; \
        *) echo "No Node build for $(uname -m)" >&2; exit 1 ;; \
    esac && \
    url=https://nodejs.org/dist/latest-v${NODE_MAJOR}.x && \
    cd /tmp && \
    curl -fsSL -O "${url}/SHASUMS256.txt" && \
    grep "linux-${arch}.tar.xz\$" SHASUMS256.txt > node.sha256 && \
    curl -fsSL -O "${url}/$(awk '{print $2}' node.sha256)" && \
    sha256sum -c node.sha256 && \
    tar -xJf node-v*-linux-${arch}.tar.xz -C /usr/local --strip-components=1 && \
    rm node-v*-linux-${arch}.tar.xz SHASUMS256.txt node.sha256

# Claude Code, Codex and opencode
RUN npm install -g --no-fund --no-audit \
        @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
        @openai/codex@${CODEX_VERSION} \
        opencode-ai@${OPENCODE_VERSION}

# flux-mcp from this checkout with the ADK and Strands agents
COPY pyproject.toml README.md LICENSE NOTICE /tmp/flux-mcp/
COPY flux_mcp /tmp/flux-mcp/flux_mcp
RUN python3 -m venv --system-site-packages /opt/flux-mcp && \
    /opt/flux-mcp/bin/pip install --no-cache-dir \
        /tmp/flux-mcp \
        "setuptools>=77" \
        "google-adk>=2.12" \
        "strands-agents>=1.60" \
        pytest \
        pytest-asyncio \
        pytest-timeout && \
    rm -rf /tmp/flux-mcp && \
    chown -R ${USERNAME}:${USERNAME} /opt/flux-mcp
ENV PATH=/opt/flux-mcp/bin:$PATH

# Claude Code settings, the firewall script and the script that starts Flux
RUN mkdir -p /home/${USERNAME}/.claude && chown ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude
COPY .devcontainer/agents/init-firewall.sh .devcontainer/agents/start-flux.sh /usr/local/bin/
COPY .devcontainer/agents/settings.json /home/${USERNAME}/.claude/settings.json
RUN chmod +x /usr/local/bin/init-firewall.sh /usr/local/bin/start-flux.sh && \
    echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/${USERNAME}-firewall && \
    chmod 0440 /etc/sudoers.d/${USERNAME}-firewall

USER $USERNAME
