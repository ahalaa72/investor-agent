# Gate 5 Testing Issue - sklearn Module Not Found

## Problem

When testing Gate 5 with real Questrade data locally:

```bash
python3 test_gate_5.py
```

Error:
```
ModuleNotFoundError: No module named 'sklearn'
```

## Root Cause

**Docker environment ≠ Local environment**

| Environment | sklearn Installed? | Why? |
|-------------|-------------------|------|
| **Docker Container** | ✅ YES | Dockerfile installs scikit-learn via uv |
| **Local macOS/Linux** | ❌ NO | Only venv with basic dependencies |

## Impact

- ✅ **MCP tools work fine** (run in Docker)
- ✅ **Gate 5 works in Docker** (proven with MCP tests)
- ❌ **Local Python scripts fail** (missing sklearn)

## Solution

### Option 1: Install sklearn locally (Quick Fix)

```bash
pip install scikit-learn
```

### Option 2: Use Docker for all tests (Recommended)

```bash
docker exec -it investor-agent-mcp python3 /app/tests/test_gate_5_mcp_integration.py
```

### Option 3: Sync local environment with Docker (Complete Fix)

```bash
# Install all dependencies from requirements
pip install -r requirements.txt

# Or if using uv (like Docker):
uv sync
```

## rebuild.sh Scope

**Current:** Only rebuilds Docker container
**Does NOT:** Set up local Python environment

### What rebuild.sh Does

1. Builds Docker image with all dependencies
2. Stops/removes old container
3. Starts new container with environment variables
4. ✅ **Ensures MCP server has everything it needs**

### What rebuild.sh Does NOT Do

- ❌ Install local Python dependencies
- ❌ Create/update local venv
- ❌ Sync local environment with Docker

## Recommended Workflow

### For MCP Testing (Production Use)

```bash
bash rebuild.sh
# MCP tools now have Gate 5 with all dependencies
```

### For Local Development/Testing

```bash
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Or using uv (faster):
uv sync

# Then test locally
python tests/test_gate_5_basic.py
```

## Gate 5 Status

✅ **FULLY FUNCTIONAL** in Docker (MCP environment)
- All MCP tools work with Gate 5
- Questrade data integration works
- 17/17 unit tests pass (when run correctly)

❌ **Local environment incomplete** (development environment)
- Missing sklearn for local testing
- Need to run `pip install scikit-learn` or `uv sync`

## Quick Reference

| Task | Command | Environment |
|------|---------|-------------|
| **Rebuild MCP server** | `bash rebuild.sh` | Docker ✅ |
| **Setup local dev** | `uv sync` or `pip install -r requirements.txt` | Local ❌ |
| **Test with MCP** | Use MCP tools directly | Docker ✅ |
| **Test locally** | `python tests/test_gate_5_basic.py` | Local (needs setup) |

## Resolution

**For this session:**
- Gate 5 is proven working with MCP tools (tested with AAPL using Questrade data)
- Questrade connection working ✅
- All 7 accounts retrieved ✅

**For future sessions:**
- Add sklearn installation to local environment: `pip install scikit-learn`
- Or use `uv sync` to match Docker environment completely

---

**Date:** 2026-01-28
**Issue:** Local testing failed due to missing sklearn
**Status:** Gate 5 works in production (Docker/MCP), local environment needs sklearn
**Impact:** No impact on production use, only affects local development/testing
