# MCP Server Crash Fix Plan

## Problem Statement

The investor-agent MCP server crashes unexpectedly with the error:
```
Server transport closed unexpectedly, this is likely due to the process exiting early.
```

### Root Cause
`ThreadPoolExecutor` futures use `future.result()` without:
1. **Timeout** - Calls block indefinitely on network hangs
2. **Exception handling** - Unhandled exceptions crash the server

### Affected Locations

| Function | Lines | Risk |
|----------|-------|------|
| `get_ticker_data()` | 302, 323, 331, 354, 358 | CRITICAL |
| `get_options()` | 398-406 (executor.map) | CRITICAL |
| `get_financial_statements()` | 471-472 | CRITICAL |
| `get_institutional_holders()` | 494-495 | CRITICAL |

---

## Fix Plan

### Phase 1: Timeout Fix (Current Sprint)

**Objective:** Prevent server crashes from hanging API calls by adding timeouts to all `future.result()` calls.

**Implementation:**

1. Create a helper function `safe_future_result()` that wraps `future.result()` with:
   - Configurable timeout (default: 30 seconds)
   - Exception handling with logging
   - Graceful fallback to `None` on failure

2. Replace all direct `future.result()` calls with `safe_future_result()`

3. Update `executor.map()` usage to use `as_completed()` pattern with timeout

**Files Modified:**
- `investor_agent/server.py`

---

### Phase 2: Future Improvements (Not in scope)

- Add circuit breaker pattern for external APIs
- Global exception handler at FastMCP level
- Memory limits for DataFrame operations
- Questrade token file error handling

---

## Implementation Details

### New Helper Function

```python
from concurrent.futures import TimeoutError as FuturesTimeoutError

def safe_future_result(future, timeout: float = 30.0, default=None, context: str = ""):
    """
    Safely get result from a future with timeout and exception handling.

    Args:
        future: The Future object to get result from
        timeout: Maximum seconds to wait (default: 30)
        default: Value to return on failure (default: None)
        context: Description for logging (e.g., "fetching ticker info")

    Returns:
        The future result or default value on failure
    """
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError:
        logger.error(f"Timeout after {timeout}s: {context}")
        return default
    except Exception as e:
        logger.error(f"Exception in {context}: {type(e).__name__}: {e}")
        return default
```

### Changes by Function

#### `get_ticker_data()` (lines 297-363)
```python
# Before
info = info_future.result()

# After
info = safe_future_result(info_future, timeout=30.0, context="fetching ticker info")
```

#### `get_options()` (lines 398-406)
```python
# Before
executor.map(lambda exp: get_options_chain(...), valid_expirations)

# After - use submit + as_completed pattern with timeout
futures = [executor.submit(get_options_chain, ticker_symbol, exp, option_type)
           for exp in valid_expirations]
chains = []
for future, expiry in zip(futures, valid_expirations):
    result = safe_future_result(future, timeout=30.0, context=f"options chain {expiry}")
    if result is not None:
        chains.append(result.assign(expiryDate=expiry))
```

#### `get_financial_statements()` (lines 467-481)
```python
# Before
df = future.result()

# After
df = safe_future_result(future, timeout=30.0, context=f"{stmt_type} statement")
```

#### `get_institutional_holders()` (lines 490-495)
```python
# Before
inst_holders = inst_future.result()
fund_holders = fund_future.result()

# After
inst_holders = safe_future_result(inst_future, timeout=30.0, context="institutional holders")
fund_holders = safe_future_result(fund_future, timeout=30.0, context="mutual fund holders")
```

---

## Testing Plan

### Unit Tests

Create `tests/test_timeout_handling.py`:

1. **Test timeout behavior**
   - Mock a slow API call that exceeds timeout
   - Verify `safe_future_result()` returns default value
   - Verify server doesn't crash

2. **Test exception handling**
   - Mock an API call that raises an exception
   - Verify exception is caught and logged
   - Verify default value is returned

3. **Test normal operation**
   - Verify normal API calls still work
   - Verify results are returned correctly

### Integration Tests

1. **Simulate network hang**
   ```bash
   # Use a non-routable IP to simulate hang
   # Configure mock to delay response > 30s
   ```

2. **Test each affected function**
   - `get_ticker_data` with slow ticker
   - `get_options` with network delay
   - `get_financial_statements` with timeout
   - `get_institutional_holders` with timeout

### Manual Verification

1. Start MCP server
2. Make tool calls that would previously hang
3. Verify server remains responsive
4. Check logs for timeout messages

### Test Script

```bash
# Run unit tests
pytest tests/test_timeout_handling.py -v

# Run integration test (requires mock server)
python -m pytest tests/test_integration_timeout.py -v

# Manual smoke test
python -c "
from investor_agent.server import get_ticker_data, get_institutional_holders
# These should timeout gracefully, not crash
try:
    result = get_ticker_data('AAPL')
    print('get_ticker_data: OK')
except ValueError as e:
    print(f'get_ticker_data: Expected error - {e}')
"
```

---

## Success Criteria

1. Server no longer crashes on network timeouts
2. Timeout errors are logged with context
3. Functions return meaningful errors instead of crashing
4. All existing tests continue to pass
5. Server remains responsive during slow API calls

---

## Rollback Plan

If issues arise:
1. Revert `server.py` to backup: `cp server.py.backup server.py`
2. Restart MCP server
3. Investigate logs for root cause

---

## Test Results (2025-12-01)

### Smoke Test Output

```
############################################################
# TIMEOUT FIX VERIFICATION TEST
# DEFAULT_FUTURE_TIMEOUT = 30.0s
############################################################

[TEST 1] Normal operation...
  PASS: Normal operation returns correct result

[TEST 2] Timeout handling...
  PASS: Timeout returned default after 0.51s (no crash!)

[TEST 3] Exception handling...
  PASS: Exception caught and default returned (no crash!)

[TEST] Multiple consecutive timeouts...
  PASS: Handled 5 consecutive timeouts without crash

[TEST] get_ticker_data('AAPL')...
  PASS: get_ticker_data returned valid data

[TEST] get_institutional_holders('AAPL')...
  PASS: get_institutional_holders returned valid data

ALL TESTS COMPLETED SUCCESSFULLY!
```

### Files Modified
- `investor_agent/server.py` - Added `safe_future_result()` and updated all `future.result()` calls

### Files Created
- `tests/test_timeout_handling.py` - pytest unit tests
- `test_timeout_fix.py` - Manual smoke test script

### Verification Commands
```bash
# Run smoke test
python test_timeout_fix.py

# Run pytest (if pytest is installed)
python -m pytest tests/test_timeout_handling.py -v
```
