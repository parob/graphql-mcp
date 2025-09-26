#!/usr/bin/env python3
"""
Basic test for the MCP Inspector functionality using graphql-core directly.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument
from graphql_mcp.server import GraphQLMCP
from graphql_mcp.inspector import MCPInspector


def resolve_hello(root, info, name="World"):
    """Greet someone by name."""
    return f"Hello, {name}!"


def test_inspector_basic():
    """Test that the inspector works with a basic GraphQL schema."""
    print("🧪 Testing MCP Inspector with basic schema...")

    # Create a simple GraphQL schema
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                    resolve=resolve_hello,
                    description="Greet someone by name"
                )
            }
        )
    )

    # Create MCP server
    server = GraphQLMCP(schema=schema, name="Test API", inspector=True)

    print("✅ MCP server created successfully")

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

    # Test HTTP app creation
    try:
        app = server.http_app(transport="http", stateless_http=True)
        print("✅ HTTP app with inspector created successfully")
    except Exception as e:
        print(f"❌ Failed to create HTTP app: {e}")
        return False

    print("✅ Basic inspector test completed!")
    return True


if __name__ == "__main__":
    success = test_inspector_basic()
    if success:
        print("🎉 Inspector test passed!")
    else:
        print("❌ Inspector test failed!")
        sys.exit(1)