"""
Example Custom MCP Server

This is a template for creating custom MCP servers.
Copy this file and modify it to create your own server.
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


class EchoRequest(BaseModel):
    message: str = Field(description="Message to echo back")


mcp = FastMCP(
    "ExampleServer",
    title="Example Custom MCP Server",
    description="A simple example server that echoes messages",
    port=8005  # Will be auto-assigned by launcher
)


@mcp.tool()
def echo(req: EchoRequest) -> dict:
    """
    Echo back a message with timestamp
    
    Args:
        req: Request containing the message to echo
        
    Returns:
        Dictionary with echoed message and timestamp
    """
    from datetime import datetime
    
    return {
        "echoed_message": req.message,
        "timestamp": datetime.now().isoformat(),
        "server_name": "ExampleServer"
    }


@mcp.tool()
def hello_world() -> str:
    """Simple hello world function"""
    return "Hello from custom MCP server!"


if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from server_base import start_mcp_server
    
    start_mcp_server(mcp, 8005, "ExampleServer")