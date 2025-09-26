#!/usr/bin/env python3
"""
Test stateful MCP server with proper session handling
"""

import uvicorn
from fastmcp import FastMCP

# Create a simple MCP server for testing
mcp = FastMCP("Stateful Test Server")

@mcp.tool()
def hello(name: str) -> str:
    """Say hello"""
    return f"Hello {name}!"

@mcp.tool()
def get_session_info() -> dict:
    """Get information about the current session"""
    # This might help us understand session state
    return {
        "message": "Session-aware tool called",
        "server": "stateful_test"
    }

def main():
    print("🚀 Starting STATEFUL MCP Server...")
    print("📚 Available endpoints:")
    print("   • MCP Protocol: http://localhost:8011/mcp")
    print("   • Mode: STATEFUL (requires session initialization)")
    print()

    # Create stateful app (default behavior)
    app = mcp.http_app(transport="http", stateless_http=False)

    # Start server
    uvicorn.run(app, host="0.0.0.0", port=8011)

if __name__ == "__main__":
    main()