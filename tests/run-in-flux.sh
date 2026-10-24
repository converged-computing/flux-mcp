#!/usr/bin/env bash
# Run pytest inside a Flux instance, with the HTTP server the tests connect to.
#
# Usage: flux start --test-size=2 tests/run-in-flux.sh [pytest args...]
#
# Environment:
#   PYTHON  interpreter with flux-mcp and the test dependencies (default: python3)

set -uo pipefail

PYTHON="${PYTHON:-python3}"
URL="http://localhost:8089/mcp"
LOG="$(mktemp)"

if [ -z "${FLUX_URI:-}" ]; then
    echo "error: run inside Flux: flux start --test-size=2 $0" >&2
    exit 2
fi

flux env "$PYTHON" -m flux_mcp.server.fastmcp > "$LOG" 2>&1 &
server=$!
trap 'kill -9 "$server" 2>/dev/null' EXIT

for _ in $(seq 120); do
    curl -s -o /dev/null "$URL" && break
    if ! kill -0 "$server" 2>/dev/null; then
        echo "error: flux-mcp server exited during startup" >&2
        cat "$LOG" >&2
        exit 2
    fi
    sleep 0.5
done
if ! curl -s -o /dev/null "$URL"; then
    echo "error: flux-mcp server did not start at $URL" >&2
    cat "$LOG" >&2
    exit 2
fi

flux env "$PYTHON" -m pytest "$@"
status=$?
if [ "$status" -ne 0 ]; then
    echo "--- flux-mcp server log (last 50 lines)"
    tail -n 50 "$LOG"
fi
exit "$status"
