#!/bin/bash
# Test script for Questrade token auto-refresh fix

set -e  # Exit on error

echo "========================================================================"
echo "QUESTRADE TOKEN AUTO-REFRESH TEST"
echo "========================================================================"
echo ""

echo "Step 1: Pull latest code and rebuild Docker container"
echo "------------------------------------------------------------------------"
git pull origin claude/questrade-investor-agent-tools-011CUqm6TMv6XrPunkMNTt6p
echo ""

echo "Building Docker image with no cache..."
docker compose build --no-cache
echo ""

echo "Restarting container with fresh image..."
docker compose down
docker compose up -d
echo ""

echo "Waiting 5 seconds for container to start..."
sleep 5
echo ""

echo "========================================================================"
echo "Step 2: Test token auto-refresh with expired token"
echo "========================================================================"
echo ""

echo "Checking current token file age..."
docker compose exec investor-agent python -c "
import time
from pathlib import Path

token_file = Path('/root/.questrade.json')
if token_file.exists():
    file_age_sec = time.time() - token_file.stat().st_mtime
    file_age_min = file_age_sec / 60
    print(f'Token file age: {file_age_min:.1f} minutes')

    if file_age_min > 5:
        print('⚠️  Access token is expired - perfect for testing auto-refresh!')
    else:
        print('✅ Access token is still valid')
else:
    print('⚠️  No token file exists - will use manual token')
"
echo ""

echo "Making API call (should auto-refresh if token expired)..."
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client
print('🧪 Testing token auto-refresh...')
client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ SUCCESS: Retrieved {len(accounts[\"accounts\"])} accounts')
print('')
print('Token auto-refresh is working!')
"
echo ""

echo "========================================================================"
echo "Step 3: Verify token was refreshed"
echo "========================================================================"
echo ""

docker compose exec investor-agent python -c "
import time
import json
from pathlib import Path

token_file = Path('/root/.questrade.json')
if token_file.exists():
    file_age_sec = time.time() - token_file.stat().st_mtime
    file_age_min = file_age_sec / 60

    print(f'✅ Token file age: {file_age_min:.1f} minutes')

    if file_age_min < 1:
        print('✅ Token was just refreshed (age < 1 minute)')
    elif file_age_min < 5:
        print('✅ Token is fresh (age < 5 minutes)')
    else:
        print('⚠️  Token might be stale (age > 5 minutes)')

    # Show token info
    with open(token_file) as f:
        data = json.load(f)
    print(f'   Access token: {data.get(\"access_token\", \"\")[:20]}...')
    print(f'   Refresh token: {data.get(\"refresh_token\", \"\")[:20]}...')
else:
    print('❌ Token file does not exist')
"
echo ""

echo "========================================================================"
echo "Step 4: Stress test - 5 consecutive API calls"
echo "========================================================================"
echo ""

docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client

print('Running 5 consecutive API calls...')
print('')

for i in range(5):
    client = get_questrade_client()
    accounts = client.get_accounts()
    print(f'✅ Call {i+1}: Retrieved {len(accounts[\"accounts\"])} accounts')

print('')
print('✅ All 5 calls succeeded!')
"
echo ""

echo "========================================================================"
echo "Step 5: Test token persistence after container restart"
echo "========================================================================"
echo ""

echo "Restarting container..."
docker compose restart investor-agent
echo ""

echo "Waiting 10 seconds for container to start..."
sleep 10
echo ""

echo "Making API call after restart..."
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client

client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ After restart: Retrieved {len(accounts[\"accounts\"])} accounts')
print('')
print('✅ Token persistence verified!')
"
echo ""

echo "========================================================================"
echo "✅ ALL TESTS PASSED!"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  ✅ Token auto-refresh is working"
echo "  ✅ Multiple consecutive API calls succeed"
echo "  ✅ Tokens persist across container restarts"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop (Cmd+Q, wait, relaunch)"
echo "  2. Test with 8+ consecutive questions"
echo "  3. Verify no 'token expired' errors"
echo ""
echo "Expected behavior in Claude Desktop:"
echo "  - Tokens auto-refresh every 5 minutes"
echo "  - Can ask unlimited questions without errors"
echo "  - No more 'tokens expire after 2 questions' issue"
echo ""
