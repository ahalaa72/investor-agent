"""Self-contained MCP server using modular tool packages.

Delegates tool registration to investor_agent.tools.* modules.
No dependency on investor_agent.server — all functions are in
tools/*.py modules or investor_agent.core/*.

Usage:
    python -m investor_agent.server_modular

Modules (20 total, 93 tools):
    tools/market_data.py              6 tools
    tools/financial_data.py           5 tools
    tools/options_analysis.py         7 tools
    tools/questrade_api.py           14 tools
    tools/technical_analysis.py       7 tools
    tools/position_mgmt.py            5 tools
    tools/risk.py                     3 tools
    tools/funds.py                    3 tools
    tools/tracking.py                 6 tools
    tools/ml_tools.py                 4 tools
    tools/scanning.py                 5 tools
    tools/catalysts.py                5 tools
    tools/signals.py                  2 tools
    tools/sector_scanner.py           1 tool
    tools/dalio_analysis.py           2 tools
    tools/statistical_validation.py   7 tools
    tools/institutional_analysis.py   4 tools
    tools/pullback_analysis.py        1 tool
"""
from dotenv import load_dotenv
load_dotenv()

import logging
import sys

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("Investor-Agent", dependencies=["yfinance", "pandas", "pytrends"])

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)],
)

# ---------------------------------------------------------------------------
# Register ALL module tools with the MCP server
# ---------------------------------------------------------------------------
from .tools import (
    market_data,
    financial_data,
    options_analysis,
    questrade_api,
    technical_analysis,
    position_mgmt,
    risk,
    funds,
    tracking,
    ml_tools,
    scanning,
    catalysts,
    signals,
    sector_scanner,
    dalio_analysis,
    statistical_validation,
    institutional_analysis,
    pullback_analysis,
    beta_analysis,
    fixed_income,
)

_modules = [
    market_data,
    financial_data,
    options_analysis,
    questrade_api,
    technical_analysis,
    position_mgmt,
    risk,
    funds,
    tracking,
    ml_tools,
    scanning,
    catalysts,
    signals,
    sector_scanner,
    dalio_analysis,
    statistical_validation,
    institutional_analysis,
    pullback_analysis,
    beta_analysis,
    fixed_income,
]

for mod in _modules:
    try:
        mod.register_tools(mcp)
        logger.info(f"Registered tools from {mod.__name__}")
    except Exception as e:
        logger.error(f"Failed to register tools from {mod.__name__}: {e}")

logger.info(f"Modular server ready: {len(_modules)} modules loaded")

# ---------------------------------------------------------------------------
# Monkey-patch FastMCP's JSON encoder to handle numpy/pandas types globally.
# This prevents "Unable to serialize unknown type: <class 'numpy.bool'>" errors
# from ANY tool without requiring per-tool sanitization.
# ---------------------------------------------------------------------------
import json as _json
_OrigEncoder = _json.JSONEncoder

class _NumpySafeEncoder(_OrigEncoder):
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                v = float(obj)
                return None if np.isnan(v) else v
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if hasattr(obj, 'item'):
                return obj.item()
        except ImportError:
            pass
        return super().default(obj)

_json.JSONEncoder = _NumpySafeEncoder
# Also replace the cached default encoder used by json.dumps()
_json._default_encoder = _NumpySafeEncoder(
    skipkeys=False, ensure_ascii=True, check_circular=True,
    allow_nan=True, indent=None, separators=None, default=None,
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
