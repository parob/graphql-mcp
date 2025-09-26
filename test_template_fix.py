#!/usr/bin/env python3
"""
Test the template fix for the inspector
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument
from graphql_mcp.server import GraphQLMCP
from graphql_mcp.inspector import MCPInspector
from starlette.testclient import TestClient


def resolve_hello(root, info, name="World"):
    return f"Hello, {name}!"


def test_template_rendering():
    """Test that the HTML template renders without errors."""
    print("🧪 Testing HTML template rendering...")

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

        # Create MCP server with inspector
        server = GraphQLMCP(schema=schema, name="Test API", inspector=True, inspector_title="Test API Inspector", graphql_http=False)

        # Create HTTP app
        app = server.http_app(transport="http", stateless_http=True)

        # Create test client
        client = TestClient(app)

        # Test the inspector endpoint
        response = client.get("/inspector")

        if response.status_code == 200:
            print("✅ Inspector HTML template rendered successfully")
            print(f"✅ Response length: {len(response.text)} characters")

            # Check that the title was replaced
            if "Test API Inspector" in response.text:
                print("✅ Template variable replacement working")
            else:
                print("❌ Template variable replacement failed")
                print(f"Searching for 'Test API' in response...")
                # Show first 500 characters of response for debugging
                print(f"First 500 chars: {response.text[:500]}")
                if "{title}" in response.text:
                    print("Found unreplaced {title} in response")
                else:
                    print("No unreplaced {title} found")
                return False

            # Check that CSS is intact (no format errors)
            if "box-sizing: border-box" in response.text:
                print("✅ CSS preserved correctly")
            else:
                print("❌ CSS may have been corrupted")
                return False

            return True
        else:
            print(f"❌ Inspector endpoint returned {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_template_rendering()
    if success:
        print("\n🎉 Template rendering test passed!")
    else:
        print("\n❌ Template rendering test failed!")
        sys.exit(1)