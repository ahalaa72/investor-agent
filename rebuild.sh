#!/bin/bash
# Quick rebuild script for investor-agent-mcp Docker container
# Usage: ./rebuild.sh

set -e  # Exit on error

echo "=== Rebuilding investor-agent-mcp ==="
echo ""

# Step 1: Build Docker image
echo "1. Building Docker image..."
docker build -t investor-agent-mcp . || {
    echo "ERROR: Docker build failed!"
    exit 1
}
echo "   Done."
echo ""

# Step 2: Stop and remove old container
echo "2. Stopping old container..."
docker stop investor-agent-mcp 2>/dev/null || true
docker rm investor-agent-mcp 2>/dev/null || true
echo "   Done."
echo ""

# Step 3: Start new container with token volume and env file
echo "3. Starting new container..."
docker run -d --name investor-agent-mcp \
  -v ~/.questrade.json:/root/.questrade.json \
  -v /tmp:/tmp \
  --env-file .env \
  investor-agent-mcp || {
    echo "ERROR: Failed to start container!"
    exit 1
}
echo "   Done."
echo ""

# Step 4: Wait for container to initialize
echo "4. Waiting for container to start..."
sleep 3

# Step 5: Verify container is running
echo "5. Verifying container status..."
if docker ps | grep -q investor-agent-mcp; then
    echo "   Container is running."
else
    echo "   ERROR: Container not running!"
    docker logs investor-agent-mcp
    exit 1
fi
echo ""

# Step 6: Show container logs
echo "6. Recent logs:"
docker logs investor-agent-mcp --tail 5
echo ""

echo "=== Rebuild complete ==="
echo ""
echo "NEXT STEPS:"
echo "1. Restart Claude Code to reconnect MCP"
echo "2. Test with: get_questrade_accounts()"
echo ""
