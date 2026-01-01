FROM fluxrm/flux-sched:noble

LABEL maintainer="Vanessasaurus <@vsoch>"

# Match the default user id for a single system so we aren't root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
ENV USERNAME=${USERNAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}
USER root
RUN apt-get update && apt-get install -y less python3-pip

# Add the group and user that match our ids
RUN groupadd -g ${USER_GID} ${USERNAME} && \
    adduser --disabled-password --uid ${USER_UID} --gid ${USER_GID} --gecos "" ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers

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
USER $USERNAME
