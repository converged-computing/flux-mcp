#!/bin/bash
# Start a Flux instance at the fixed URI in FLUX_URI, unless it is already running.

uri=local:///tmp/flux-agents/local

# The instance can run jobs once flux uptime reports the run state.
running() {
    [ "$(FLUX_URI=$uri flux uptime 2>/dev/null | awk '{print $2}')" = run ]
}

running && exit 0

mkdir -p /tmp/flux-agents
setsid flux start -Slocal-uri=$uri sleep inf < /dev/null > /tmp/flux-agents/broker.log 2>&1 &

for _ in $(seq 60); do
    running && exit 0
    sleep 1
done
echo "Flux did not start, see /tmp/flux-agents/broker.log" >&2
exit 1
