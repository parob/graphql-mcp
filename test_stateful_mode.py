#!/usr/bin/env python3
"""
Test stateful vs stateless MCP server modes
"""

from fastmcp import FastMCP

# Create a simple MCP server
mcp = FastMCP("Test Server")

@mcp.tool()
def hello(name: str) -> str:
    """Say hello"""
    return f"Hello {name}!"

def test_stateful_mode():
    """Test what happens with stateful mode"""
    print("🧪 Testing MCP server modes...")

    # Test stateless mode
    print("\n1️⃣ Creating STATELESS server...")
    stateless_app = mcp.http_app(transport="http", stateless_http=True)
    print(f"Stateless app: {type(stateless_app)}")

    # Test stateful mode (default)
    print("\n2️⃣ Creating STATEFUL server...")
    stateful_app = mcp.http_app(transport="http", stateless_http=False)
    print(f"Stateful app: {type(stateful_app)}")

    # Check if there are any differences in the middleware or handlers
    print(f"\nStateless routes: {[route.path for route in stateless_app.routes]}")
    print(f"Stateful routes: {[route.path for route in stateful_app.routes]}")

    return stateless_app, stateful_app

if __name__ == "__main__":
    test_stateful_mode()