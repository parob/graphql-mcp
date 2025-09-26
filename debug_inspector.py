#!/usr/bin/env python3
"""
Debug script for the MCP Inspector functionality.
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


def debug_inspector():
    """Debug the inspector functionality."""
    print("🧪 Debug MCP Inspector...")

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

    # Create MCP server with debug info
    print("Creating MCP server...")
    server = GraphQLMCP(schema=schema, name="Debug API", inspector=False, graphql_http=False)

    print(f"Server created: {server}")
    print(f"Server attributes: {dir(server)}")

    # Check for tools
    if hasattr(server, '_tools'):
        print(f"✅ _tools attribute exists: {server._tools}")
    else:
        print("❌ _tools attribute missing")

    if hasattr(server, 'tools'):
        print(f"✅ tools attribute exists: {server.tools}")
    else:
        print("❌ tools attribute missing")

    # Try to find tools another way
    for attr in dir(server):
        if 'tool' in attr.lower():
            print(f"Found tool-related attribute: {attr} = {getattr(server, attr)}")

    # Create inspector
    print("Creating inspector...")
    inspector = MCPInspector(server, "Debug Inspector")
    print(f"Inspector created: {inspector}")

    print("✅ Debug completed!")


if __name__ == "__main__":
    debug_inspector()