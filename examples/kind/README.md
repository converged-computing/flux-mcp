# Flux MCP Server Example

> Run Flux MCP in Kubernetes with basic manifests

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/) (Kubernetes in Docker)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Python 3.11+](https://www.python.org/downloads/) (for local testing)

## 1. Create a Kind Cluster

Start by creating a local Kubernetes cluster (with kind):

```bash
kind create cluster
```

## 2. Build and Load the Image

Build the container image locally and load it into the `kind` nodes so you don't have to push to a remote registry.
You can also pull and load.

```bash
# Build the image
docker build -t ghcr.io/converged-computing/flux-mcp:latest .
docker build -f Dockerfile.spack -t ghcr.io/converged-computing/flux-mcp:spack .

# Load into kind
kind load docker-image ghcr.io/converged-computing/flux-mcp:latest
kind load docker-image ghcr.io/converged-computing/flux-mcp:spack
# You can pull and load these, if desired
kind load docker-image ghcr.io/converged-computing/flux-view-ubuntu:tag-jammy
kind load docker-image ghcr.io/flux-framework/tutorials:flux-operator-pytorch
```

## 3. Install the Flux Operator

Install the Flux Operator:

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/refs/heads/main/examples/dist/flux-operator.yaml
```

## 4. Deploy the MiniCluster

Create the MiniCluster with the sidecar that runs Flux MCP.

```bash
kubectl apply -f minicluster.yaml
```

Wait for the pod to reach the `Running` state:

```bash
kubectl get pods
```

See the server running:

```bash
kubectl logs $(kubectl get pods -o json | jq -r .items[0].metadata.name) -f
```
```console
broker.info[0]: quorum-full: quorum->run 0.47581s
📖 Loading config from /code/scripts/run-spack.yaml
   ✅ Registered: flux_validate_batch_jobspec
   ✅ Registered: sleep_timer
   ✅ Registered: read_file
   ✅ Registered: list_directory
   ✅ Registered: spack_list
   ✅ Registered: spack_find
   ✅ Registered: spack_spec
   ✅ Registered: spack_info
   ✅ Registered: spack_install
   ✅ Registered: database_save
   ✅ Registered: database_get
   ✅ Registered: flux_resource_list
   ✅ Registered: flux_validate_jobspec
   ✅ Registered: flux_submit_job
   ✅ Registered: flux_cancel_job
   ✅ Registered: flux_get_job_info
   ✅ Registered: flux_get_job_logs
   ✅ Registered: flux_sched_qmanager_stats
   ✅ Registered: validate_jobspec_expert
   ✅ Registered: transform_jobspec_expert
   ✅ Registered: simple_echo
   ✅ Registered: check_finished_prompt
INFO:     Started server process [104]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8089 (Press CTRL+C to quit)
```

You can shell into the lead broker (index 0) pod: 

```bash
kubectl exec -it $(kubectl get pods -o json | jq -r .items[0].metadata.name) -- bash
. /mnt/flux/flux-view.sh
flux proxy $fluxsocket bash
```

And discover the MCP sidecar running on the headless service:

```bash
curl -k flux-mcp-0.flux-mcp.default.svc.cluster.local:8089/mcp
```

You'll need to export an API key, e.g., `GEMINI_API_KEY`. Then we can test launching work with fractale. This first example is asking to respond to a generic prompt:

```bash
fractale prompt Submit a job to tell me a joke, and ask me about the category. Get the output log to confirm it was successful.
```

Here is an example for how to target a specific sub-agent.

```bash
# fractale agent <sub-agent>
fractale agent -r ./fractale/examples/registry/analysis-agents.yaml optimize Discover resources and software installed to spack. Create an optimization agent single step with instruction to choose an application to run with flux, run, and get the logs. 

# Add a log parser?
fractale agent -r ./fractale/examples/registry/analysis-agents.yaml optimize Discover resources and verify cowsay is installed with spack. Run cowsay with flux, get the logs, and use the result parser to parse out the message.

# More specific - install lammps and parse the log.
fractale agent -r ./fractale/examples/registry/analysis-agents.yaml optimize Discover resources and verify lammps is installed with spack. Run lammps "lmp" with example data from the cloned repository with flux, get the logs, and parse the figure of merit.
```

## Clean Up

To delete the cluster and start over:

```bash
kind delete cluster
```
