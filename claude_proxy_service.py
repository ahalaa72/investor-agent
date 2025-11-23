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

# Response configuration
RESPONSE_MODE = os.getenv("CLAUDE_RESPONSE_MODE", "balanced")  # concise, balanced, detailed
MAX_TOKENS_MAP = {
    "concise": 1024,
    "balanced": 2048,
    "detailed": 4096
}

# System prompt that defines Claude's role and behavior
SYSTEM_PROMPT = """You are an expert financial analyst with access to real-time market data and financial analysis tools. Your role is to:

1. **Understand user questions** about stocks, markets, and investments
2. **Use the available tools** to fetch current, accurate data when needed
3. **Provide clear, actionable insights** based on the data
4. **Be concise but thorough** - give the essential information without unnecessary elaboration

Guidelines for tool usage:
- Use tools proactively when you need current market data
- Call multiple tools if needed to answer comprehensively
- Always explain what the data shows, don't just present raw numbers
- If asked for analysis, provide context and interpretation

Response style based on mode:
- **Concise**: Brief, to-the-point answers (2-3 paragraphs max)
- **Balanced**: Standard analysis with key insights (3-5 paragraphs)
- **Detailed**: Comprehensive analysis with context (full analysis)

Current response mode: {response_mode}

Available data sources:
- Real-time stock prices and market data
- Options chains and derivatives data
- Financial statements (income, balance sheet, cash flow)
- Technical indicators and chart patterns
- Market sentiment indicators
- Institutional holdings and insider trades
- Earnings calendar and analyst recommendations
"""

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
    response_mode: str = Field(
        default=None,
        description="Response length: 'concise', 'balanced', or 'detailed'. Uses CLAUDE_RESPONSE_MODE env if not set."
    )
    max_tokens: int = Field(
        default=None,
        description="Max tokens (auto-set based on response_mode if not provided)"
    )

class ChatResponse(BaseModel):
    response: str
    tool_calls_made: List[str] = []
    conversation_history: List[ChatMessage]
    usage: Optional[Dict[str, int]] = None
    estimated_cost: Optional[float] = None
    response_mode: str = "balanced"

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
    import inspect
    from typing import get_type_hints

    tools = server.mcp._tool_manager._tools if hasattr(server.mcp, '_tool_manager') else {}

    if isinstance(tools, dict):
        tools_list = list(tools.values())
    else:
        tools_list = tools

    claude_tools = []
    for tool in tools_list:
        # Get function signature for parameter schema
        func = tool.fn
        sig = inspect.signature(func)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip self and cls
            if param_name in ('self', 'cls'):
                continue

            param_schema = {"type": "string"}  # Default

            # Try to infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                ann = param.annotation
                if ann == int or ann == "int":
                    param_schema["type"] = "integer"
                elif ann == float or ann == "float":
                    param_schema["type"] = "number"
                elif ann == bool or ann == "bool":
                    param_schema["type"] = "boolean"
                elif hasattr(ann, "__origin__"):
                    origin = getattr(ann, "__origin__", None)
                    if origin == list:
                        param_schema["type"] = "array"
                    elif origin == dict:
                        param_schema["type"] = "object"

            properties[param_name] = param_schema

            # Add to required if no default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        # Convert MCP tool to Claude API tool format
        claude_tool = {
            "name": tool.name,
            "description": tool.description or inspect.getdoc(func) or f"Financial analysis tool: {tool.name}",
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        claude_tools.append(claude_tool)

    return claude_tools

def estimate_cost(usage: Dict[str, int], model: str = "claude-3-5-sonnet-20241022") -> float:
    """Estimate cost based on token usage"""
    # Pricing for Claude 3.5 Sonnet (as of 2024)
    # https://www.anthropic.com/pricing
    input_cost_per_million = 3.0  # $3 per million input tokens
    output_cost_per_million = 15.0  # $15 per million output tokens

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    input_cost = (input_tokens / 1_000_000) * input_cost_per_million
    output_cost = (output_tokens / 1_000_000) * output_cost_per_million

    return input_cost + output_cost

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
        # Determine response mode and max tokens
        response_mode = request.response_mode or RESPONSE_MODE
        if response_mode not in MAX_TOKENS_MAP:
            response_mode = "balanced"

        max_tokens = request.max_tokens or MAX_TOKENS_MAP[response_mode]

        # Build system prompt with current response mode
        system_prompt = SYSTEM_PROMPT.format(response_mode=response_mode)

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
        logger.info(f"Response mode: {response_mode}, Max tokens: {max_tokens}")

        response = claude_client.messages.create(
            model=request.model,
            max_tokens=max_tokens,
            system=system_prompt,
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
                max_tokens=max_tokens,
                system=system_prompt,
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

        # Get usage and cost information
        usage_dict = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
        cost = estimate_cost(usage_dict, request.model)

        logger.info(f"Usage: {usage_dict}, Estimated cost: ${cost:.4f}")

        return ChatResponse(
            response=final_response,
            tool_calls_made=tool_calls_made,
            conversation_history=messages,
            usage=usage_dict,
            estimated_cost=cost,
            response_mode=response_mode
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
