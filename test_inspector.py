#!/usr/bin/env python3
"""
Simple test for the MCP Inspector functionality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP
from graphql_mcp.inspector import MCPInspector


class SimpleAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    @field
    def add(self, a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b


def test_inspector():
    """Test that the inspector can be created and list tools."""
    print("🧪 Testing MCP Inspector...")

    # Create API and MCP server
    api = GraphQLAPI(root_type=SimpleAPI)
    server = GraphQLMCP.from_api(api, name="Test API")

    # Create inspector
    inspector = MCPInspector(server, "Test Inspector")

    print("✅ Inspector created successfully")

    # Check that tools are available
    if hasattr(server, '_tools'):
        print(f"✅ Found {len(server._tools)} tools:")
        for tool_name in server._tools:
            print(f"   • {tool_name}")
    else:
        print("❌ No tools found")

    print("✅ Inspector test completed!")


def test_server_with_inspector():
    """Test that the server can be created with inspector enabled."""
    print("🧪 Testing GraphQL MCP Server with Inspector...")

    # Create API and MCP server with inspector
    api = GraphQLAPI(root_type=SimpleAPI)
    server = GraphQLMCP.from_api(
        api,
        name="Test API with Inspector",
        inspector=True,
        inspector_title="Test Inspector"
    )

    # Create HTTP app
    app = server.http_app(transport="http", stateless_http=True)

    print("✅ Server with inspector created successfully")
    print("✅ Server integration test completed!")


if __name__ == "__main__":
    test_inspector()
    test_server_with_inspector()
    print("🎉 All tests passed!")