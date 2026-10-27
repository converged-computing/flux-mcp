#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, and pipeline failures
IFS=$'\n\t'       # Stricter word splitting

# Regions for the model APIs that have one. Add the region you set in AWS_REGION for
# Strands or GOOGLE_CLOUD_LOCATION for Vertex AI. The script runs with sudo, which does
# not pass those variables through. us-west-2 is the Strands default.
BEDROCK_REGIONS=("us-west-2" "us-east-1")
VERTEX_LOCATION="us-central1"

# Domains each agent needs. Remove the ones for agents you do not use.
ALLOWED_DOMAINS=(
    # Claude Code
    "api.anthropic.com"
    "claude.ai"
    "platform.claude.com"
    "downloads.claude.ai"
    "storage.googleapis.com"
    "raw.githubusercontent.com"
    # Codex with an API key, or signed in with ChatGPT
    "api.openai.com"
    "auth.openai.com"
    "chatgpt.com"
    # Google ADK with a Gemini API key, or with Vertex AI
    "generativelanguage.googleapis.com"
    "oauth2.googleapis.com"
    "aiplatform.googleapis.com"
    "${VERTEX_LOCATION}-aiplatform.googleapis.com"
    # AWS Strands with Bedrock
    $(printf 'bedrock-runtime.%s.amazonaws.com\n' "${BEDROCK_REGIONS[@]}")
    # opencode, plus the model API it is set up to use from the lists above
    "opencode.ai"
    "api.opencode.ai"
    "models.opencode.ai"
    # Python packages, for pip install -e . from the checkout
    "pypi.org"
    "files.pythonhosted.org"
)

# 1. Extract Docker DNS info BEFORE any flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush existing rules and delete existing ipsets
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
# Stop the dnsmasq from an earlier run, since it holds the ipset we are about to replace
if [ -f /run/dnsmasq-firewall.pid ]; then
    kill "$(cat /run/dnsmasq-firewall.pid)" 2>/dev/null || true
    rm -f /run/dnsmasq-firewall.pid
fi
ipset destroy allowed-domains 2>/dev/null || true

# 2. Selectively restore ONLY internal Docker DNS resolution
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
else
    echo "No Docker DNS rules to restore"
fi

# First allow DNS and localhost before any restrictions
# Allow outbound DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
# Allow inbound DNS responses
iptables -A INPUT -p udp --sport 53 -j ACCEPT
# Allow outbound SSH
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
# Allow inbound SSH responses
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
# Allow localhost
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Create ipset with CIDR support
ipset create allowed-domains hash:net

# Fetch GitHub meta information and aggregate + add their IP ranges
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s https://api.github.com/meta)
if [ -z "$gh_ranges" ]; then
    echo "ERROR: Failed to fetch GitHub IP ranges"
    exit 1
fi

if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
    echo "ERROR: GitHub API response missing required fields"
    exit 1
fi

echo "Processing GitHub IPs..."
while read -r cidr; do
    if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        echo "ERROR: Invalid CIDR range from GitHub meta: $cidr"
        exit 1
    fi
    echo "Adding GitHub range $cidr"
    ipset add allowed-domains "$cidr"
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | aggregate -q)

# Resolve and add other allowed domains
for domain in "${ALLOWED_DOMAINS[@]}"; do
    echo "======================================"
    echo "Checking: $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "ERROR: Failed to resolve $domain"
        exit 1
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "ERROR: Invalid IP from DNS for $domain: $ip"
            exit 1
        fi
        echo "Adding $ip for $domain"
        ipset add allowed-domains "$ip" -exist
    done < <(echo "$ips")
done

# Some domains, such as the Bedrock endpoints, hand out a new set of IPs every minute, so the
# IPs above go stale. dnsmasq answers DNS for the container and adds every IP it resolves for
# an allowed domain to the ipset before it returns the answer.
echo "Starting dnsmasq to keep allowed domain IPs current..."
if [ ! -f /etc/resolv.conf.upstream ]; then
    cp /etc/resolv.conf /etc/resolv.conf.upstream
fi
upstream=$(awk '$1 == "nameserver" {print "--server=" $2}' /etc/resolv.conf.upstream)
if [ -z "$upstream" ]; then
    echo "ERROR: No upstream nameserver in /etc/resolv.conf.upstream"
    exit 1
fi
dnsmasq \
    --user=root \
    --no-resolv \
    --no-hosts \
    --listen-address=127.0.0.1 \
    --bind-interfaces \
    --pid-file=/run/dnsmasq-firewall.pid \
    --log-facility=/var/log/dnsmasq-firewall.log \
    $upstream \
    --ipset="/$(IFS=/; echo "${ALLOWED_DOMAINS[*]}")/allowed-domains"
# Docker bind mounts resolv.conf, so write it in place instead of replacing it
echo "nameserver 127.0.0.1" > /etc/resolv.conf

# Get host IP from default route
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP"
    exit 1
fi

HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
echo "Host network detected as: $HOST_NETWORK"

# Set up remaining iptables rules
iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

# Set default policies to DROP first
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# First allow established connections for already approved traffic
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Then allow only specific outbound traffic to allowed domains
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Explicitly REJECT all other outbound traffic for immediate feedback
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "Firewall configuration complete"
echo "Verifying firewall rules..."
if curl --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - was able to reach https://example.com"
    exit 1
else
    echo "Firewall verification passed - unable to reach https://example.com as expected"
fi

# Verify that a domain resolved after startup lands in the ipset
domain="${ALLOWED_DOMAINS[0]}"
ip=$(dig +short A "$domain" | grep -E '^[0-9.]+$' | head -1)
if [ -z "$ip" ] || ! ipset test allowed-domains "$ip" 2>/dev/null; then
    echo "ERROR: Firewall verification failed - dnsmasq did not add $domain ($ip) to the ipset"
    exit 1
else
    echo "Firewall verification passed - dnsmasq adds resolved IPs to the ipset"
fi

# Verify GitHub API access
if ! curl --connect-timeout 5 https://api.github.com/zen >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - unable to reach https://api.github.com"
    exit 1
else
    echo "Firewall verification passed - able to reach https://api.github.com as expected"
fi
