"""
Pinggy Tunnel MCP Wrapper

This FastAPI application wraps the investor-agent MCP server for secure remote access via Pinggy tunnel.
Includes API key authentication, rate limiting, and enhanced security for internet exposure.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import inspect
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import the MCP server instance and all tool definitions
from investor_agent import server
mcp = server.mcp

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Security Configuration
API_KEY = os.getenv("MCP_API_KEY", "")
RATE_LIMIT_CALLS = int(os.getenv("RATE_LIMIT_CALLS", "100"))  # calls per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # seconds (1 hour default)

# Rate limiting storage (in production, use Redis)
rate_limit_storage = defaultdict(lambda: {"count": 0, "reset_time": datetime.now()})

# Create FastAPI app
app = FastAPI(
    title="Investor Agent MCP - Pinggy Tunnel",
    description="Secure HTTP REST API wrapper for remote access to Investor Agent MCP Server via Pinggy tunnel",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class ToolCallRequest(BaseModel):
    """Request model for calling an MCP tool"""
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")


class ToolCallResponse(BaseModel):
    """Response model for tool calls"""
    success: bool
    tool_name: str
    result: Any = None
    error: str | None = None


class ToolInfo(BaseModel):
    """Information about a single tool"""
    name: str
    description: str | None = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_async: bool = False


class ToolListResponse(BaseModel):
    """Response model for listing all tools"""
    tools: List[ToolInfo]
    count: int


class RateLimitInfo(BaseModel):
    """Rate limit information"""
    limit: int
    remaining: int
    reset_time: str


# Security dependencies
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key from header"""
    if API_KEY and API_KEY != "":
        if not x_api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key. Provide X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"}
            )
        if x_api_key != API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key"
            )
    return x_api_key


async def rate_limiter(request: Request, api_key: str = Depends(verify_api_key)):
    """Rate limiting middleware"""
    client_id = api_key or request.client.host
    now = datetime.now()

    # Get or create rate limit entry
    limit_info = rate_limit_storage[client_id]

    # Reset counter if window expired
    if now >= limit_info["reset_time"]:
        limit_info["count"] = 0
        limit_info["reset_time"] = now + timedelta(seconds=RATE_LIMIT_WINDOW)

    # Check rate limit
    if limit_info["count"] >= RATE_LIMIT_CALLS:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": RATE_LIMIT_CALLS,
                "window_seconds": RATE_LIMIT_WINDOW,
                "reset_time": limit_info["reset_time"].isoformat()
            }
        )

    # Increment counter
    limit_info["count"] += 1

    return {
        "limit": RATE_LIMIT_CALLS,
        "remaining": RATE_LIMIT_CALLS - limit_info["count"],
        "reset_time": limit_info["reset_time"].isoformat()
    }


# Helper functions
def get_tools_list():
    """Get list of tools from MCP server"""
    if hasattr(mcp, '_tool_manager') and mcp._tool_manager:
        tool_manager = mcp._tool_manager
        if hasattr(tool_manager, '_tools') and tool_manager._tools:
            tools = tool_manager._tools
            return list(tools.values()) if isinstance(tools, dict) else tools
        elif hasattr(tool_manager, 'tools') and tool_manager.tools:
            tools = tool_manager.tools
            return list(tools.values()) if isinstance(tools, dict) else tools

    if hasattr(mcp, '_tools') and mcp._tools:
        return list(mcp._tools.values()) if isinstance(mcp._tools, dict) else mcp._tools
    elif hasattr(mcp, 'tools') and mcp.tools:
        return list(mcp.tools.values()) if isinstance(mcp.tools, dict) else mcp.tools

    return None


def get_tool_function(tool_name: str):
    """Get the actual function for a tool by name"""
    tools = get_tools_list()

    if not tools:
        raise ValueError("No tools found in MCP server")

    for tool in tools:
        if tool.name == tool_name:
            return tool.fn

    raise ValueError(f"Tool '{tool_name}' not found")


def get_function_signature(func) -> Dict[str, Any]:
    """Extract function signature as OpenAI-compatible schema"""
    sig = inspect.signature(func)
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    for param_name, param in sig.parameters.items():
        param_info = {
            "type": "string",  # Default type
        }

        # Try to infer type from annotation
        if param.annotation != inspect.Parameter.empty:
            annotation = param.annotation

            # Handle basic types
            if annotation == str or annotation == "str":
                param_info["type"] = "string"
            elif annotation == int or annotation == "int":
                param_info["type"] = "integer"
            elif annotation == float or annotation == "float":
                param_info["type"] = "number"
            elif annotation == bool or annotation == "bool":
                param_info["type"] = "boolean"
            elif hasattr(annotation, "__origin__"):
                origin = getattr(annotation, "__origin__", None)
                if origin == list:
                    param_info["type"] = "array"
                elif origin == dict:
                    param_info["type"] = "object"

            # Handle Literal types (extract enum values)
            if hasattr(annotation, "__args__") and hasattr(annotation, "__origin__"):
                if str(annotation).startswith("typing.Literal"):
                    param_info["enum"] = list(annotation.__args__)

        # Check if parameter has a default value
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param_name)
        else:
            param_info["default"] = param.default

        parameters["properties"][param_name] = param_info

    return parameters


async def call_tool_safe(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Safely call a tool with error handling"""
    try:
        func = get_tool_function(tool_name)

        # Check if function is async
        if inspect.iscoroutinefunction(func):
            result = await func(**arguments)
        else:
            # Run sync function in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: func(**arguments))

        return result

    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {str(e)}", exc_info=True)
        raise


# API Endpoints

@app.get("/", tags=["Status"])
async def root():
    """Root endpoint with API information"""
    auth_required = bool(API_KEY and API_KEY != "")
    return {
        "name": "Investor Agent MCP - Pinggy Tunnel",
        "version": "1.0.0",
        "status": "running",
        "authentication": "required" if auth_required else "disabled",
        "rate_limit": {
            "calls": RATE_LIMIT_CALLS,
            "window_seconds": RATE_LIMIT_WINDOW
        },
        "endpoints": {
            "tools": "/tools",
            "call": "/call",
            "health": "/health",
            "rate_limit": "/rate-limit",
            "docs": "/docs"
        },
        "usage": {
            "authentication": "Add X-API-Key header with your API key" if auth_required else "No authentication required",
            "example_curl": f'curl -X POST "{request.url}call" -H "Content-Type: application/json"' +
                          (f' -H "X-API-Key: YOUR_API_KEY"' if auth_required else '') +
                          ' -d \'{"tool_name": "get_market_movers", "arguments": {"category": "gainers", "count": 5}}\''
        }
    }


@app.get("/health", tags=["Status"])
async def health_check():
    """Health check endpoint (no authentication required)"""
    return {
        "status": "healthy",
        "service": "investor-agent-pinggy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/rate-limit", tags=["Status"])
async def get_rate_limit(limit_info: dict = Depends(rate_limiter)):
    """Check current rate limit status"""
    return RateLimitInfo(**limit_info)


@app.get("/tools", response_model=ToolListResponse, tags=["Tools"])
async def list_tools(limit_info: dict = Depends(rate_limiter)):
    """
    List all available MCP tools with their schemas.
    Returns tool names, descriptions, and parameter schemas in OpenAI function calling format.

    Requires authentication via X-API-Key header if MCP_API_KEY is set.
    """
    try:
        tools = get_tools_list()

        if not tools:
            logger.error("No tools available in MCP server")
            logger.error(f"MCP attributes: {dir(mcp)}")
            raise HTTPException(status_code=500, detail="No tools available in MCP server")

        tools_info = []
        for tool in tools:
            tool_info = ToolInfo(
                name=tool.name,
                description=tool.description or inspect.getdoc(tool.fn) or "No description available",
                parameters=get_function_signature(tool.fn),
                is_async=inspect.iscoroutinefunction(tool.fn)
            )
            tools_info.append(tool_info)

        logger.info(f"Returning {len(tools_info)} tools")
        return ToolListResponse(tools=tools_info, count=len(tools_info))

    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call", response_model=ToolCallResponse, tags=["Tools"])
async def call_tool(request: ToolCallRequest, limit_info: dict = Depends(rate_limiter)):
    """
    Call an MCP tool by name with the provided arguments.

    Requires authentication via X-API-Key header if MCP_API_KEY is set.

    Example request:
    ```json
    {
        "tool_name": "get_market_movers",
        "arguments": {
            "category": "gainers",
            "count": 10
        }
    }
    ```

    Example with curl:
    ```bash
    curl -X POST "https://your-pinggy-url.ngrok.io/call" \\
         -H "Content-Type: application/json" \\
         -H "X-API-Key: your-api-key" \\
         -d '{"tool_name": "get_ticker_data", "arguments": {"ticker": "AAPL"}}'
    ```
    """
    try:
        logger.info(f"Calling tool '{request.tool_name}' with arguments: {request.arguments}")

        result = await call_tool_safe(request.tool_name, request.arguments)

        return ToolCallResponse(
            success=True,
            tool_name=request.tool_name,
            result=result
        )

    except ValueError as e:
        logger.error(f"ValueError: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except TypeError as e:
        logger.error(f"TypeError: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")

    except Exception as e:
        logger.error(f"Error calling tool: {str(e)}", exc_info=True)
        return ToolCallResponse(
            success=False,
            tool_name=request.tool_name,
            error=str(e)
        )


@app.get("/tools/{tool_name}", tags=["Tools"])
async def get_tool_info(tool_name: str, limit_info: dict = Depends(rate_limiter)):
    """
    Get detailed information about a specific tool.

    Requires authentication via X-API-Key header if MCP_API_KEY is set.
    """
    try:
        tools = get_tools_list()

        if not tools:
            raise HTTPException(status_code=500, detail="No tools available in MCP server")

        for tool in tools:
            if tool.name == tool_name:
                return {
                    "name": tool.name,
                    "description": tool.description or inspect.getdoc(tool.fn) or "No description available",
                    "parameters": get_function_signature(tool.fn),
                    "is_async": inspect.iscoroutinefunction(tool.fn)
                }

        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("PINGGY_HOST", "127.0.0.1")
    port = int(os.getenv("PINGGY_PORT", "8000"))

    logger.info(f"Starting Pinggy MCP Wrapper on {host}:{port}")
    logger.info(f"API Key Authentication: {'Enabled' if API_KEY else 'Disabled'}")
    logger.info(f"Rate Limit: {RATE_LIMIT_CALLS} calls per {RATE_LIMIT_WINDOW} seconds")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
