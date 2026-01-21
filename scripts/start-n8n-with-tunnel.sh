#!/bin/bash

# =============================================================================
# n8n with Cloudflare Quick Tunnel Startup Script
# =============================================================================
# This script:
# 1. Stops and removes existing n8n container
# 2. Starts n8n Docker first
# 3. Starts Cloudflare Quick Tunnel (auto-generates public URL)
# 4. Displays the generated URL for webhook configuration
# =============================================================================

set -e

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-n8n}"
N8N_PORT="${N8N_PORT:-5678}"
N8N_VOLUME="${N8N_VOLUME:-investor-agent_n8n_data}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  n8n + Cloudflare Tunnel Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check prerequisites
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}Error: cloudflared is not installed${NC}"
    echo "Install with: brew install cloudflared"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ cloudflared found${NC}"
echo -e "${GREEN}  ✓ docker found${NC}"

# -----------------------------------------------------------------------------
# Step 2: Verify configuration
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[2/5] Verifying configuration...${NC}"

echo -e "${GREEN}  ✓ Data volume: $N8N_VOLUME${NC}"
echo -e "${GREEN}  ✓ Local port: $N8N_PORT${NC}"

# Check if Docker volume exists
if docker volume ls --format '{{.Name}}' | grep -q "^${N8N_VOLUME}$"; then
    echo -e "${GREEN}  ✓ Docker volume exists${NC}"
else
    echo "  Creating Docker volume..."
    docker volume create "$N8N_VOLUME"
    echo -e "${GREEN}  ✓ Docker volume created${NC}"
fi

# -----------------------------------------------------------------------------
# Step 3: Stop and remove existing container
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[3/5] Cleaning up existing container...${NC}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  Stopping container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    echo "  Removing container '$CONTAINER_NAME'..."
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Container removed${NC}"
else
    echo -e "${GREEN}  ✓ No existing container found${NC}"
fi

# Also kill any existing cloudflared tunnel processes
if pgrep -f "cloudflared.*tunnel" > /dev/null; then
    echo "  Stopping existing tunnel process..."
    pkill -f "cloudflared.*tunnel" || true
    sleep 2
    echo -e "${GREEN}  ✓ Tunnel process stopped${NC}"
fi

# -----------------------------------------------------------------------------
# Step 4: Start Cloudflare Quick Tunnel
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[4/5] Starting Cloudflare Quick Tunnel...${NC}"

# Create log file for tunnel output
TUNNEL_LOG="/tmp/cloudflared-quicktunnel.log"
rm -f "$TUNNEL_LOG"

# Start Quick Tunnel in background (auto-generates public URL)
cloudflared tunnel --url "http://localhost:${N8N_PORT}" > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# Wait for tunnel to establish and capture URL
echo "  Waiting for tunnel URL..."
TUNNEL_URL=""
for i in {1..30}; do
    if [ -f "$TUNNEL_LOG" ]; then
        TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
        if [ -n "$TUNNEL_URL" ]; then
            break
        fi
    fi
    sleep 1
done

# Check if tunnel is running and URL was captured
if ! ps -p $TUNNEL_PID > /dev/null 2>&1; then
    echo -e "${RED}Error: Tunnel failed to start${NC}"
    echo "Check logs: cat $TUNNEL_LOG"
    exit 1
fi

if [ -z "$TUNNEL_URL" ]; then
    echo -e "${RED}Error: Could not capture tunnel URL${NC}"
    echo "Check logs: cat $TUNNEL_LOG"
    exit 1
fi

echo -e "${GREEN}  ✓ Tunnel started (PID: $TUNNEL_PID)${NC}"
echo -e "${GREEN}  ✓ Public URL: $TUNNEL_URL${NC}"

# -----------------------------------------------------------------------------
# Step 5: Start n8n container
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[5/5] Starting n8n container...${NC}"

docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${N8N_PORT}:5678" \
    -e WEBHOOK_URL="$TUNNEL_URL" \
    -e N8N_HOST="0.0.0.0" \
    -e N8N_PORT=5678 \
    -e N8N_SECURE_COOKIE=false \
    -v "${N8N_VOLUME}:/home/node/.n8n" \
    n8nio/n8n

# Wait for container to start
sleep 3

# Check container status
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${GREEN}  ✓ n8n container started${NC}"
else
    echo -e "${RED}Error: Container failed to start${NC}"
    echo "Check logs with: docker logs $CONTAINER_NAME"
    exit 1
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  SUCCESS! n8n is running${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  ${BLUE}Local URL:${NC}    http://localhost:${N8N_PORT}"
echo -e "  ${BLUE}Public URL:${NC}   $TUNNEL_URL"
echo -e "  ${BLUE}Data Volume:${NC}  $N8N_VOLUME"
echo -e "  ${BLUE}Tunnel PID:${NC}   $TUNNEL_PID"
echo ""
echo -e "  ${YELLOW}⚠️  IMPORTANT:${NC}"
echo "    The Quick Tunnel URL changes each time you restart!"
echo "    Update your Telegram bot webhook with the new URL:"
echo ""
echo -e "  ${BLUE}Telegram Webhook URL:${NC}"
echo "    $TUNNEL_URL/webhook/telegram-webhook"
echo ""
echo -e "  ${YELLOW}Commands:${NC}"
echo "    View logs:     docker logs -f $CONTAINER_NAME"
echo "    Tunnel logs:   cat $TUNNEL_LOG"
echo "    Stop n8n:      docker stop $CONTAINER_NAME"
echo "    Stop tunnel:   kill $TUNNEL_PID"
echo "    Stop both:     ./scripts/stop-n8n.sh"
echo ""

# Save PID and URL for later cleanup/reference
echo "$TUNNEL_PID" > /tmp/cloudflared-n8n-tunnel.pid
echo "$TUNNEL_URL" > /tmp/cloudflared-n8n-tunnel-url.txt
echo -e "${GREEN}Tunnel PID saved to /tmp/cloudflared-n8n-tunnel.pid${NC}"
echo -e "${GREEN}Tunnel URL saved to /tmp/cloudflared-n8n-tunnel-url.txt${NC}"
