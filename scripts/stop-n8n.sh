#!/bin/bash

# =============================================================================
# Stop n8n and Cloudflare Tunnel
# =============================================================================

CONTAINER_NAME="${CONTAINER_NAME:-n8n}"
PID_FILE="/tmp/cloudflared-n8n-tunnel.pid"
URL_FILE="/tmp/cloudflared-n8n-tunnel-url.txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping n8n and Cloudflare tunnel...${NC}"
echo ""

# Stop n8n container
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  Stopping n8n container..."
    docker stop "$CONTAINER_NAME"
    echo -e "${GREEN}  ✓ n8n stopped${NC}"
else
    echo "  n8n container not running"
fi

# Stop tunnel using saved PID
if [ -f "$PID_FILE" ]; then
    TUNNEL_PID=$(cat "$PID_FILE")
    if ps -p "$TUNNEL_PID" > /dev/null 2>&1; then
        echo "  Stopping tunnel (PID: $TUNNEL_PID)..."
        kill "$TUNNEL_PID"
        echo -e "${GREEN}  ✓ Tunnel stopped${NC}"
    else
        echo "  Tunnel process not found"
    fi
    rm -f "$PID_FILE"
else
    # Fallback: kill any cloudflared tunnel process
    if pgrep -f "cloudflared.*tunnel" > /dev/null; then
        echo "  Stopping tunnel by name..."
        pkill -f "cloudflared.*tunnel"
        echo -e "${GREEN}  ✓ Tunnel stopped${NC}"
    else
        echo "  Tunnel not running"
    fi
fi

# Clean up URL file
rm -f "$URL_FILE"
rm -f /tmp/cloudflared-quicktunnel.log

echo ""
echo -e "${GREEN}Done!${NC}"
