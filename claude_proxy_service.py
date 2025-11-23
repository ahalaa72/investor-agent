"""
Claude API Proxy Service with MCP Tools

This service allows you to use Claude API from your mobile device while
having access to MCP tools running on your laptop.

Usage:
1. Set ANTHROPIC_API_KEY in .env
2. Run: python claude_proxy_service.py
3. Create Pinggy tunnel: ssh -p 443 -R0:localhost:8001 a.pinggy.io
4. Send chat requests from your mobile app to the Pinggy URL

The service will:
- Receive your question from mobile
- Call MCP tools as needed
- Send results to Claude API
- Return Claude's response to your mobile
"""

from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import anthropic

# Import MCP server to call tools directly
from investor_agent import server

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
PORT = int(os.getenv("CLAUDE_PROXY_PORT", "8001"))

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY must be set in .env file")

# Initialize Claude client
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Create FastAPI app
app = FastAPI(
    title="Claude API Proxy with MCP Tools",
    description="Chat with Claude while having access to investor-agent MCP tools",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Your question or message")
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in the conversation"
    )
    model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model to use"
    )
    max_tokens: int = Field(default=4096, description="Max tokens in response")

class ChatResponse(BaseModel):
    response: str
    tool_calls_made: List[str] = []
    conversation_history: List[ChatMessage]

# Security
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if MCP_API_KEY is set"""
    if MCP_API_KEY and MCP_API_KEY != "":
        if not x_api_key or x_api_key != MCP_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key

# Helper functions
async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool directly"""
    try:
        # Get all tools
        tools = server.mcp._tool_manager._tools if hasattr(server.mcp, '_tool_manager') else {}

        if isinstance(tools, dict):
            tools_list = list(tools.values())
        else:
            tools_list = tools

        # Find the tool
        for tool in tools_list:
            if tool.name == tool_name:
                func = tool.fn
                # Call sync or async
                if asyncio.iscoroutinefunction(func):
                    result = await func(**arguments)
                else:
                    result = func(**arguments)
                return result

        raise ValueError(f"Tool '{tool_name}' not found")

    except Exception as e:
        logger.error(f"Error calling MCP tool '{tool_name}': {e}")
        raise

def get_available_tools() -> List[Dict[str, Any]]:
    """Get list of available MCP tools in Claude API format"""
    tools = server.mcp._tool_manager._tools if hasattr(server.mcp, '_tool_manager') else {}

    if isinstance(tools, dict):
        tools_list = list(tools.values())
    else:
        tools_list = tools

    claude_tools = []
    for tool in tools_list:
        # Convert MCP tool to Claude API tool format
        claude_tool = {
            "name": tool.name,
            "description": tool.description or f"MCP tool: {tool.name}",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        claude_tools.append(claude_tool)

    return claude_tools

# API Endpoints
@app.get("/", tags=["Status"])
async def root():
    """Root endpoint"""
    return {
        "name": "Claude API Proxy with MCP Tools",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "tools": "/tools",
            "health": "/health"
        },
        "usage": "Send POST to /chat with your message to chat with Claude using MCP tools"
    }

@app.get("/health", tags=["Status"])
async def health():
    """Health check"""
    return {"status": "healthy", "claude_api": "connected" if ANTHROPIC_API_KEY else "not configured"}

@app.get("/tools", tags=["Tools"])
async def list_tools(api_key: str = Depends(verify_api_key)):
    """List all available MCP tools"""
    tools = get_available_tools()
    return {"tools": tools, "count": len(tools)}

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    """
    Chat with Claude while having access to MCP tools.

    Claude will automatically call MCP tools when needed to answer your question.

    Example:
    ```json
    {
      "message": "What are today's top stock gainers?",
      "conversation_history": []
    }
    ```
    """
    try:
        # Build conversation history
        messages = request.conversation_history + [
            {"role": "user", "content": request.message}
        ]

        # Get available tools
        tools = get_available_tools()

        # Track tool calls
        tool_calls_made = []

        # Call Claude API with tool use
        logger.info(f"Calling Claude API with message: {request.message}")

        response = claude_client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            tools=tools,
            messages=messages
        )

        # Process response and handle tool calls
        while response.stop_reason == "tool_use":
            # Extract tool calls
            tool_results = []

            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input
                    tool_use_id = content_block.id

                    logger.info(f"Claude requested tool: {tool_name} with args: {tool_input}")
                    tool_calls_made.append(f"{tool_name}({json.dumps(tool_input)})")

                    # Call the MCP tool
                    try:
                        result = await call_mcp_tool(tool_name, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": str(result)
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": True,
                            "content": f"Error calling tool: {str(e)}"
                        })

            # Continue conversation with tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # Get Claude's response with tool results
            response = claude_client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                tools=tools,
                messages=messages
            )

        # Extract final text response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        # Update conversation history
        messages.append({"role": "assistant", "content": final_response})

        return ChatResponse(
            response=final_response,
            tool_calls_made=tool_calls_made,
            conversation_history=messages
        )

    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Claude API Proxy on port {PORT}")
    logger.info(f"API Key Auth: {'Enabled' if MCP_API_KEY else 'Disabled'}")
    logger.info(f"Available MCP tools: {len(get_available_tools())}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
