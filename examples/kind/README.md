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
docker build --no-cache -t ghcr.io/converged-computing/flux-mcp:latest .

# Load into kind
kind load docker-image ghcr.io/converged-computing/flux-mcp:latest
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
broker.info[0]: quorum-full: quorum->run 0.465563s
📖 Loading config from /code/scripts/flux-mcp.yaml
   ✅ Registered: sleep_timer
   ✅ Registered: read_file
   ✅ Registered: list_directory
   ✅ Registered: flux_resource_list
   ✅ Registered: flux_validate_jobspec
   ✅ Registered: flux_submit_job
   ✅ Registered: flux_cancel_job
   ✅ Registered: flux_get_job_info
   ✅ Registered: flux_get_job_logs
   ✅ Registered: flux_sched_qmanager_stats
   ✅ Registered: simple_echo
   ✅ Registered: check_finished_prompt
INFO:     Started server process [108]
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

You'll need to export an API key. Then we can test launching work with fractale.

```bash
fractale prompt Run lammps on the resources you find with input files in /code. Wait until the job finishes and then get the output logs.
```

## 5. Expose the server

Expose the service to your local machine:

```bash
kubectl port-forward svc/mcp-server-service 8080:80
```

Check health:

```bash
$ curl -s http://localhost:8080/health  | jq
{
  "status": 200,
  "message": "OK"
}
```

Ask for pancakes (you need fastmcp installed for this).

```bash
$ python3 get_pancakes.py 
  ⭐ Discovered tool: pancakes_tool
  ⭐ Discovered tool: simple_echo

CallToolResult(content=[TextContent(type='text', text='Pancakes for Vanessa 🥞', annotations=None, meta=None)], structured_content={'result': 'Pancakes for Vanessa 🥞'}, meta=None, data='Pancakes for Vanessa 🥞', is_error=False)
```

Note that we can also run the server in stdio mode and then echo json RPC to it, but nah, don't really want to do that. 

## Clean Up

To delete the cluster and start over:

```bash
kind delete cluster
```
