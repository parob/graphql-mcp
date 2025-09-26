#!/usr/bin/env python3
"""
Working Example: GraphQL MCP Server with Web Inspector

This demonstrates the completed web inspector functionality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument, GraphQLInt
from graphql_mcp.server import GraphQLMCP
import uvicorn


def resolve_hello(root, info, name="World"):
    """Greet someone by name."""
    return f"Hello, {name}!"


def resolve_add(root, info, a, b):
    """Add two numbers together."""
    return a + b


def main():
    print("🚀 Starting GraphQL MCP Server with Web Inspector...")

    # Create a GraphQL schema with multiple tools
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                    resolve=resolve_hello,
                    description="Greet someone by name"
                ),
                "add": GraphQLField(
                    GraphQLInt,
                    args={
                        "a": GraphQLArgument(GraphQLInt),
                        "b": GraphQLArgument(GraphQLInt)
                    },
                    resolve=resolve_add,
                    description="Add two numbers together"
                )
            }
        )
    )

    # Create MCP server with web inspector enabled
    server = GraphQLMCP(
        schema=schema,
        name="Demo MCP Server",
        inspector=True,
        inspector_title="GraphQL MCP Inspector Demo",
        graphql_http=False  # Disable GraphQL HTTP for this demo
    )

    # Create HTTP app
    app = server.http_app(transport="http", stateless_http=True)

    print("✅ Server created successfully!")
    print()
    print("📚 Available endpoints:")
    print("   • Web Inspector: http://localhost:8003/inspector")
    print("   • MCP Protocol:  http://localhost:8003/mcp")
    print()
    print("🔥 Try the web inspector to:")
    print("   • Browse available MCP tools (hello, add)")
    print("   • View tool parameters and documentation")
    print("   • Test tools with real-time results")
    print("   • See the frontend-only architecture in action!")
    print()

    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8003)


if __name__ == "__main__":
    main()