"""
Base utilities for MCP servers
"""

import os


def get_server_port(default_port: int) -> int:
    """Get server port from environment or use default"""
    port_str = os.environ.get("MCP_SERVER_PORT")
    if port_str:
        try:
            return int(port_str)
        except ValueError:
            pass
    return default_port


def get_transport_mode() -> str:
    """Get transport mode from command line arguments"""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        return "stdio"
    return "streamable-http"


def start_mcp_server(mcp_instance, default_port: int, server_name: str):
    """Standard MCP server startup routine"""
    # Update port from environment if provided
    port = get_server_port(default_port)
    mcp_instance.port = port
    
    transport = get_transport_mode()
    
    print(f"{server_name} MCP Server starting - Transport: {transport}")
    if transport == "streamable-http":
        print(f"HTTP server will start at http://localhost:{port}/mcp")
    
    mcp_instance.run(transport=transport)