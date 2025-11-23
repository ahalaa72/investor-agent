#!/bin/bash

# Startup script for Investor Agent MCP with Pinggy Tunnel
# This script starts the FastAPI wrapper and optionally creates a Pinggy tunnel

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT=${PINGGY_PORT:-8000}
HOST=${PINGGY_HOST:-127.0.0.1}
AUTO_TUNNEL=${AUTO_TUNNEL:-false}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Investor Agent MCP - Pinggy Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Copying from template...${NC}"
    if [ -f .env.template ]; then
        cp .env.template .env
        echo -e "${GREEN}✓ Created .env file. Please edit it with your API keys.${NC}"
        echo -e "${YELLOW}⚠️  You need to configure the following in .env:${NC}"
        echo "   - MCP_API_KEY (for securing your remote access)"
        echo "   - ALPACA_API_KEY and ALPACA_API_SECRET (for intraday data)"
        echo "   - QUESTRADE_REFRESH_TOKEN (for account access)"
        echo ""
        read -p "Press Enter after you've configured your .env file..."
    else
        echo -e "${RED}✗ .env.template not found!${NC}"
        exit 1
    fi
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check if MCP_API_KEY is set
if [ -z "$MCP_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  MCP_API_KEY not set in .env${NC}"
    echo "   For security, it's recommended to set an API key for remote access."
    echo "   Add this line to your .env file:"
    echo "   MCP_API_KEY=your-secure-random-key-here"
    echo ""
    read -p "Continue without API key? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Python dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"
if ! python -c "import investor_agent" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  investor_agent not installed. Installing...${NC}"
    pip install -e ".[bridge]"
fi

# Start the FastAPI server in the background
echo -e "${GREEN}Starting FastAPI server on ${HOST}:${PORT}...${NC}"
python -m investor_agent.pinggy_wrapper &
SERVER_PID=$!

# Wait for server to start
echo -e "${BLUE}Waiting for server to start...${NC}"
sleep 3

# Check if server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}✗ Failed to start server!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Server started successfully (PID: $SERVER_PID)${NC}"
echo ""

# Test local endpoint
echo -e "${BLUE}Testing local endpoint...${NC}"
if curl -s "http://${HOST}:${PORT}/health" > /dev/null; then
    echo -e "${GREEN}✓ Server is responding${NC}"
else
    echo -e "${RED}✗ Server is not responding!${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Server is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Local URL: ${BLUE}http://${HOST}:${PORT}${NC}"
echo -e "API Docs:  ${BLUE}http://${HOST}:${PORT}/docs${NC}"
echo -e "Health:    ${BLUE}http://${HOST}:${PORT}/health${NC}"
echo ""

# Offer to start Pinggy tunnel
if [ "$AUTO_TUNNEL" = "true" ] || command -v ssh &> /dev/null; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Pinggy Tunnel Setup${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "To create a Pinggy tunnel, you have two options:"
    echo ""
    echo "1. ${GREEN}Automatic (using ssh command):${NC}"
    echo "   ssh -p 443 -R0:localhost:${PORT} a.pinggy.io"
    echo ""
    echo "2. ${GREEN}Using Pinggy CLI:${NC}"
    echo "   pinggy -p ${PORT}"
    echo ""

    if [ "$AUTO_TUNNEL" != "true" ]; then
        read -p "Start Pinggy tunnel automatically? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            AUTO_TUNNEL=true
        fi
    fi

    if [ "$AUTO_TUNNEL" = "true" ]; then
        echo -e "${BLUE}Starting Pinggy tunnel...${NC}"
        echo ""
        ssh -p 443 -R0:localhost:${PORT} a.pinggy.io &
        TUNNEL_PID=$!

        echo ""
        echo -e "${GREEN}✓ Tunnel started (PID: $TUNNEL_PID)${NC}"
        echo ""
        echo -e "${YELLOW}Your public URL will appear above.${NC}"
        echo -e "${YELLOW}Copy it and use it to access your MCP server remotely.${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Manual Pinggy Setup Required${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "SSH is not available. To create a Pinggy tunnel:"
    echo ""
    echo "1. Install Pinggy CLI:"
    echo "   ${BLUE}https://pinggy.io/download${NC}"
    echo ""
    echo "2. Run:"
    echo "   ${GREEN}pinggy -p ${PORT}${NC}"
    echo ""
    echo "Or use SSH tunnel:"
    echo "   ${GREEN}ssh -p 443 -R0:localhost:${PORT} a.pinggy.io${NC}"
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Usage Instructions${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Test with curl:"
if [ -n "$MCP_API_KEY" ]; then
    echo -e "${BLUE}curl -X POST 'http://${HOST}:${PORT}/call' \\
  -H 'Content-Type: application/json' \\
  -H 'X-API-Key: ${MCP_API_KEY}' \\
  -d '{\"tool_name\": \"get_market_movers\", \"arguments\": {\"category\": \"gainers\", \"count\": 5}}'${NC}"
else
    echo -e "${BLUE}curl -X POST 'http://${HOST}:${PORT}/call' \\
  -H 'Content-Type: application/json' \\
  -d '{\"tool_name\": \"get_market_movers\", \"arguments\": {\"category\": \"gainers\", \"count\": 5}}'${NC}"
fi
echo ""
echo "List all tools:"
echo -e "${BLUE}curl 'http://${HOST}:${PORT}/tools'${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for interrupt
trap "echo ''; echo 'Stopping services...'; kill $SERVER_PID 2>/dev/null || true; [ ! -z \$TUNNEL_PID ] && kill \$TUNNEL_PID 2>/dev/null || true; exit 0" INT TERM

# Keep script running
wait
