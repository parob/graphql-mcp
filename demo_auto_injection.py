#!/usr/bin/env python3
"""
Demo: Automatic MCP Plugin Injection into GraphiQL

This example shows how the MCP plugin is automatically injected
into GraphiQL when both GraphQL HTTP and Inspector are enabled.
"""

import uvicorn
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument, GraphQLInt
from graphql_mcp.server import GraphQLMCP


def main():
    print("🚀 Starting GraphQL + MCP with Auto-Injection Demo...")
    print()

    # Create a GraphQL schema with sample tools
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                    resolve=lambda obj, info, name="World": f"Hello {name}!"
                ),
                "add": GraphQLField(
                    GraphQLInt,
                    args={
                        "a": GraphQLArgument(GraphQLInt),
                        "b": GraphQLArgument(GraphQLInt)
                    },
                    resolve=lambda obj, info, a, b: a + b
                ),
                "multiply": GraphQLField(
                    GraphQLInt,
                    args={
                        "x": GraphQLArgument(GraphQLInt),
                        "y": GraphQLArgument(GraphQLInt)
                    },
                    resolve=lambda obj, info, x, y: x * y
                )
            }
        )
    )

    # Create GraphQL MCP server with BOTH GraphQL HTTP and Inspector enabled
    server = GraphQLMCP(
        schema=schema,
        name="Auto-Injection Demo",
        inspector=True,  # Enable MCP inspector
        inspector_title="Auto-Injected MCP Tools",
        graphql_http=True  # Enable GraphQL HTTP with GraphiQL
    )

    # Create the app with both GraphQL and MCP endpoints
    app = server.http_app(transport="http", stateless_http=True)

    print("✅ Server created successfully!")
    print()
    print("🎯 Auto-Injection Demo:")
    print("   • GraphiQL with MCP: http://localhost:8005/")
    print("   • Standalone Inspector: http://localhost:8005/inspector")
    print("   • MCP Protocol:         http://localhost:8005/mcp")
    print()
    print("🔥 What happens:")
    print("   1. GraphiQL loads normally at /")
    print("   2. MCP plugin is automatically injected into the HTML")
    print("   3. MCP tools panel appears automatically in GraphiQL!")
    print("   4. No manual injection required!")
    print()
    print("💡 Try it:")
    print("   • Open http://localhost:8005/ in your browser")
    print("   • See the MCP tools panel on the right side")
    print("   • Use GraphQL queries AND MCP tools together!")
    print()

    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8005)


if __name__ == "__main__":
    main()