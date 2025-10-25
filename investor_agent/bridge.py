"""
MCP-to-HTTP Bridge Server

This FastAPI application exposes the investor-agent MCP server tools as HTTP REST API endpoints,
enabling integration with n8n and other HTTP-based workflow systems.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import inspect
import logging
import sys
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import the MCP server instance
from investor_agent.server import mcp

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Create FastAPI app
app = FastAPI(
    title="Investor Agent MCP Bridge",
    description="HTTP REST API bridge for the Investor Agent MCP Server",
    version="1.0.0"
)

# Add CORS middleware for n8n and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# Helper functions
def get_tool_function(tool_name: str):
    """Get the actual function for a tool by name"""
    # FastMCP stores tools in the _tools dict
    if not hasattr(mcp, '_tools') or not mcp._tools:
        raise ValueError("No tools found in MCP server")

    for tool in mcp._tools:
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
                # Handle List, Dict, etc.
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
    return {
        "name": "Investor Agent MCP Bridge",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "tools": "/tools",
            "call": "/call",
            "health": "/health"
        }
    }


@app.get("/health", tags=["Status"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "investor-agent-bridge"
    }


@app.get("/tools", response_model=ToolListResponse, tags=["Tools"])
async def list_tools():
    """
    List all available MCP tools with their schemas.
    Returns tool names, descriptions, and parameter schemas in OpenAI function calling format.
    """
    try:
        if not hasattr(mcp, '_tools') or not mcp._tools:
            raise HTTPException(status_code=500, detail="No tools available in MCP server")

        tools_info = []
        for tool in mcp._tools:
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
async def call_tool(request: ToolCallRequest):
    """
    Call an MCP tool by name with the provided arguments.

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
        # Tool not found or invalid arguments
        logger.error(f"ValueError: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except TypeError as e:
        # Invalid arguments
        logger.error(f"TypeError: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid arguments: {str(e)}")

    except Exception as e:
        # Other errors
        logger.error(f"Error calling tool: {str(e)}", exc_info=True)
        return ToolCallResponse(
            success=False,
            tool_name=request.tool_name,
            error=str(e)
        )


@app.get("/tools/{tool_name}", tags=["Tools"])
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool"""
    try:
        if not hasattr(mcp, '_tools') or not mcp._tools:
            raise HTTPException(status_code=500, detail="No tools available in MCP server")

        for tool in mcp._tools:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
