# Rebuild Script - Complete Guide

## What `rebuild.sh` Does

**Updated:** 2026-01-28 - Now includes Gate 5 testing

### Complete Rebuild Process

```bash
bash rebuild.sh
```

This script performs a **complete rebuild and validation** of the investor-agent MCP server:

| Step | Action | Purpose |
|------|--------|---------|
| 1 | Build Docker image | Compile all code including Gate 5 |
| 2 | Stop old container | Clean slate |
| 3 | Remove old container | Remove stale state |
| 4 | Start new container | Deploy fresh build |
| 5 | Wait for startup | Allow initialization |
| 6 | Verify running | Health check |
| 7 | Show logs | Quick status |
| **8** | **Run Gate 5 tests** | **Validate Gate 5 works** ✨ NEW |

### What's Included

✅ **All Gate 5 code:**
- `investor_agent/gates/options_tradability_gate.py`
- `investor_agent/options/decision_framework.py`
- All helper functions
- Integration with existing MCP tools

✅ **All dependencies:**
- scikit-learn (sklearn)
- pandas, numpy, scipy
- All options analysis libraries
- Questrade API client

✅ **Environment setup:**
- QUESTRADE_REFRESH_TOKEN from `.env`
- All other environment variables
- Proper Docker networking

✅ **Validation:**
- Container health check
- Optional: Gate 5 unit tests (17 tests)

## Usage

### Standard Rebuild

```bash
bash rebuild.sh
```

**When to use:**
- After modifying Gate 5 code
- After changing `.env` (new Questrade token)
- After pulling code updates
- When Docker container is in unknown state

### Expected Output

```
=== Rebuilding investor-agent-mcp ===

1. Building Docker image...
   Done.

2. Stopping old container...
   Done.

3. Starting new container...
   Done.

4. Waiting for container to start...

5. Verifying container status...
   Container is running.

6. Recent logs:
[Container startup messages]

7. Running Gate 5 tests in Docker...
test_basic_calculation PASSED
test_strike_rounding PASSED
test_high_iv PASSED
...
   Done.

=== Rebuild complete ===

✅ Docker container rebuilt with Gate 5
✅ Container running and healthy

NEXT STEPS:
1. Restart Claude Code to reconnect MCP
2. Test with MCP tools:
   - get_questrade_accounts()
   - analyze_options_mcmillan('AAPL')

GATE 5 STATUS:
- ✅ Code deployed to Docker
- ✅ MCP tools have Gate 5 available
- ✅ Ready for integration into generate_trading_signal()
```

## What About Local Development?

**rebuild.sh does NOT set up local Python environment.**

### For Local Development/Testing

If you want to run tests locally (outside Docker):

```bash
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Or using uv (faster, like Docker uses):
uv sync

# Run tests locally
pytest tests/test_gate_5_basic.py -v
```

### Why Two Environments?

| Environment | Purpose | Setup Command |
|-------------|---------|---------------|
| **Docker** | Production MCP server | `bash rebuild.sh` ✅ |
| **Local** | Development/debugging | `uv sync` or `pip install -r requirements.txt` |

**Recommendation:** Use Docker for everything (MCP tools run in Docker anyway)

## Testing Gate 5 After Rebuild

### Option 1: Use MCP Tools (Recommended)

After `rebuild.sh`, restart Claude Code, then:

```
> analyze_options_mcmillan("AAPL")
> analyze_iv_skew("AAPL")
> analyze_iv_term_structure("AAPL")
```

Gate 5 uses these tools internally.

### Option 2: Run Tests in Docker

```bash
docker exec investor-agent-mcp python -m pytest /app/tests/test_gate_5_basic.py -v
```

### Option 3: Direct Gate 5 Test

```bash
docker exec -i investor-agent-mcp python3 << 'PYTHON_EOF'
from investor_agent.gates.options_tradability_gate import calculate_expected_moves

result = calculate_expected_moves(228.00, 0.30, 45)
print(f"✅ Gate 5 working: 1SD move = ${result['1sd_move']:.2f}")
PYTHON_EOF
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs investor-agent-mcp

# Common causes:
# 1. Port conflict
# 2. Missing .env file
# 3. Invalid token in .env
```

### Tests Fail in Docker

```bash
# Check if pytest is installed
docker exec investor-agent-mcp python -m pytest --version

# Run tests with full output
docker exec investor-agent-mcp python -m pytest /app/tests/test_gate_5_basic.py -v -s
```

### Questrade Connection Fails

**Symptom:** `HTTP 403 Forbidden`

**Cause:** Refresh token is consumed/expired

**Fix:**
1. Generate NEW token from Questrade
2. Update `.env` with new token
3. Run `bash rebuild.sh`
4. **Don't test the token manually first** (it's single-use!)

### Local Tests Fail (sklearn not found)

**Symptom:** `ModuleNotFoundError: No module named 'sklearn'`

**Cause:** Local environment doesn't have dependencies

**Fix:**
```bash
# Install locally
pip install scikit-learn

# Or sync everything
uv sync
```

## Summary

### What rebuild.sh Guarantees

✅ Docker container with complete investor-agent
✅ All Gate 5 code deployed
✅ All dependencies installed (including sklearn)
✅ Container running and healthy
✅ Environment variables loaded from `.env`
✅ Optional: Basic validation tests run

### What rebuild.sh Does NOT Do

❌ Set up local Python venv
❌ Install local dependencies
❌ Modify system Python
❌ Install Claude Code/Desktop
❌ Configure `.mcp.json`

### Is rebuild.sh Enough?

**For MCP usage (production):** ✅ **YES** - `rebuild.sh` is complete

**For local development:** ⚠️ **Need one more step:** `uv sync` or `pip install -r requirements.txt`

---

## Quick Reference

```bash
# Complete Docker rebuild with Gate 5
bash rebuild.sh

# Verify Questrade connection
docker exec investor-agent-mcp python3 -c "from investor_agent.questrade import QuestradeClient; print(QuestradeClient().get_accounts())"

# Test Gate 5 directly
docker exec investor-agent-mcp python -m pytest /app/tests/test_gate_5_basic.py -v

# Check container status
docker ps | grep investor-agent-mcp
docker logs investor-agent-mcp --tail 20
```

---

**Last Updated:** 2026-01-28
**Status:** rebuild.sh is complete for MCP server deployment
**Gate 5:** Fully integrated and tested in Docker
