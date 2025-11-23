#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Investor Agent MCP - Pinggy Docker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Configuration
ENABLE_TUNNEL=${ENABLE_PINGGY_TUNNEL:-false}
PORT=${PINGGY_PORT:-8000}
HOST=${PINGGY_HOST:-0.0.0.0}
PINGGY_SUBDOMAIN=${PINGGY_SUBDOMAIN:-""}

# Validate MCP_API_KEY
if [ -z "$MCP_API_KEY" ]; then
    echo -e "${RED}ERROR: MCP_API_KEY is not set!${NC}"
    echo -e "${YELLOW}Please set MCP_API_KEY in your .env file for security.${NC}"
    echo -e "${YELLOW}Example: MCP_API_KEY=your-secure-random-key${NC}"
    exit 1
fi

echo -e "${GREEN}✓ MCP_API_KEY is configured${NC}"
echo ""

# Start FastAPI server in background
echo -e "${BLUE}Starting FastAPI server on ${HOST}:${PORT}...${NC}"
python -m uvicorn investor_agent.pinggy_wrapper:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info &

SERVER_PID=$!
echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"

# Wait for server to be ready
echo -e "${BLUE}Waiting for server to be ready...${NC}"
sleep 5

# Check if server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}✗ Server failed to start!${NC}"
    exit 1
fi

# Test server health
if curl -s http://localhost:${PORT}/health > /dev/null; then
    echo -e "${GREEN}✓ Server is healthy and responding${NC}"
else
    echo -e "${YELLOW}⚠️  Server health check failed, but continuing...${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Server Information${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Internal URL: ${BLUE}http://localhost:${PORT}${NC}"
echo -e "Health Check: ${BLUE}http://localhost:${PORT}/health${NC}"
echo -e "API Docs:     ${BLUE}http://localhost:${PORT}/docs${NC}"
echo -e "API Key:      ${GREEN}Configured${NC}"
echo ""

# Start Pinggy tunnel if enabled
if [ "$ENABLE_TUNNEL" = "true" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Starting Pinggy Tunnel${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""

    # Build SSH command
    if [ -n "$PINGGY_SUBDOMAIN" ]; then
        echo -e "${BLUE}Creating tunnel with custom subdomain: ${PINGGY_SUBDOMAIN}${NC}"
        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
            -p 443 -R0:localhost:${PORT} -t a.pinggy.io "$PINGGY_SUBDOMAIN" &
    else
        echo -e "${BLUE}Creating tunnel with random subdomain${NC}"
        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
            -p 443 -R0:localhost:${PORT} a.pinggy.io &
    fi

    TUNNEL_PID=$!
    echo -e "${GREEN}✓ Tunnel started (PID: $TUNNEL_PID)${NC}"
    echo ""
    echo -e "${YELLOW}Your public HTTPS URL will appear above.${NC}"
    echo -e "${YELLOW}Look for a line like: https://xxxx.a.pinggy.io${NC}"
    echo ""
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Pinggy Tunnel Disabled${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo -e "To enable Pinggy tunnel, set: ${BLUE}ENABLE_PINGGY_TUNNEL=true${NC}"
    echo ""
    echo -e "You can create a tunnel manually from another terminal:"
    echo -e "${BLUE}docker exec -it investor-agent-pinggy ssh -p 443 -R0:localhost:${PORT} a.pinggy.io${NC}"
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Usage Examples${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Test health endpoint:"
echo -e "${BLUE}curl http://localhost:${PORT}/health${NC}"
echo ""
echo "List all tools:"
echo -e "${BLUE}curl -H 'X-API-Key: \$MCP_API_KEY' http://localhost:${PORT}/tools${NC}"
echo ""
echo "Call a tool:"
echo -e "${BLUE}curl -X POST http://localhost:${PORT}/call \\
  -H 'Content-Type: application/json' \\
  -H 'X-API-Key: \$MCP_API_KEY' \\
  -d '{\"tool_name\": \"get_market_movers\", \"arguments\": {\"category\": \"gainers\", \"count\": 5}}'${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Container is running. Press Ctrl+C to stop.${NC}"
echo ""

# Trap signals for graceful shutdown
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    # Kill tunnel if running
    if [ ! -z "$TUNNEL_PID" ]; then
        echo -e "${BLUE}Stopping Pinggy tunnel...${NC}"
        kill $TUNNEL_PID 2>/dev/null || true
    fi

    # Kill server
    echo -e "${BLUE}Stopping FastAPI server...${NC}"
    kill $SERVER_PID 2>/dev/null || true

    echo -e "${GREEN}✓ Shutdown complete${NC}"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Keep container running and wait for server process
wait $SERVER_PID
