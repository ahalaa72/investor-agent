"""Self-contained MCP server using modular tool packages.

Delegates tool registration to investor_agent.tools.* modules.
No dependency on investor_agent.server — all functions are in
tools/*.py modules or investor_agent.core/*.

Usage:
    python -m investor_agent.server_modular

Modules (13 total, 72 tools):
    tools/market_data.py        6 tools
    tools/financial_data.py     5 tools
    tools/options_analysis.py   7 tools
    tools/questrade_api.py     14 tools
    tools/technical_analysis.py 7 tools
    tools/position_mgmt.py      5 tools
    tools/risk.py               3 tools
    tools/funds.py              3 tools
    tools/tracking.py           6 tools
    tools/ml_tools.py           4 tools
    tools/scanning.py           5 tools
    tools/catalysts.py          5 tools
    tools/signals.py            2 tools
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
]

for mod in _modules:
    try:
        mod.register_tools(mcp)
        logger.info(f"Registered tools from {mod.__name__}")
    except Exception as e:
        logger.error(f"Failed to register tools from {mod.__name__}: {e}")

logger.info(f"Modular server ready: {len(_modules)} modules loaded")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
