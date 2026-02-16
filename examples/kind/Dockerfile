FROM ghcr.io/converged-computing/metric-lammps-cpu:zen4-reax

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    wget \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code
COPY ./scripts /code/scripts
RUN git clone -b add-manager-agent https://github.com/converged-computing/fractale /code/fractale && python3 -m pip install -e /code/fractale[all]
# then need to write manage ragent
# manager agent should select subset of tools
RUN git clone -b add-optimization-agent https://github.com/converged-computing/hpc-mcp /code/hpc-mcp && \
    cd /code/hpc-mcp && pip install .
RUN git clone -b add-resource-list https://github.com/converged-computing/flux-mcp /code/flux-mcp && \
    cd /code/flux-mcp && pip install . && pip install -r /code/scripts/requirements.txt
# RUN pip install flux-mcp
ENV LD_LIBRARY_PATH=/opt/hpcx/ompi/lib:/opt/hpcx/mxm/lib:/opt/hpcx/ucx/lib:$LD_LIBRARY_PATH
ENV PATH=/opt/hpcx/ompi/bin:$PATH
ENV SHELL=/usr/bin/bash
