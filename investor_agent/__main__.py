"""
Entry point for running investor-agent as a module.

This allows the package to be executed with:
    python -m investor_agent
"""

from .server import mcp

if __name__ == "__main__":
    mcp.run()
