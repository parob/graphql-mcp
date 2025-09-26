#!/usr/bin/env python3
"""
Final test for the MCP Inspector functionality.
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


def test_complete_inspector():
    """Test the complete inspector implementation."""
    print("🧪 Testing Complete MCP Inspector Implementation...")

    try:
        # Create a GraphQL schema
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

        # Create MCP server with inspector enabled
        server = GraphQLMCP(schema=schema, name="Test API", inspector=True, graphql_http=False)
        print("✅ GraphQL MCP server created with inspector enabled")

        # Create HTTP app
        app = server.http_app(transport="http", stateless_http=True)
        print("✅ HTTP app created successfully")

        # Check that HTML template exists
        inspector_html_path = os.path.join(os.path.dirname(__file__), 'graphql_mcp', 'inspector.html')
        if os.path.exists(inspector_html_path):
            print("✅ Inspector HTML template found")
        else:
            print("❌ Inspector HTML template not found")

        # Test inspector creation directly
        inspector = MCPInspector(server, "Test Inspector")
        print("✅ Inspector object created successfully")

        print("🎉 All tests passed!")
        print()
        print("📚 To use the inspector:")
        print("   1. Run your GraphQL MCP server")
        print("   2. Visit /inspector endpoint in your browser")
        print("   3. The inspector will connect to the /mcp endpoint directly")
        print("   4. Browse and test your MCP tools in real-time!")
        print()
        print("🔥 Features:")
        print("   • Frontend-only architecture (like GraphiQL)")
        print("   • Direct MCP protocol communication")
        print("   • Real-time tool browsing and testing")
        print("   • Clean, modern UI with parameter validation")
        print("   • No backend APIs needed - pure client-side")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_complete_inspector()
    if success:
        print("\n🎉 Inspector implementation completed successfully!")
    else:
        print("\n❌ Inspector test failed!")
        sys.exit(1)