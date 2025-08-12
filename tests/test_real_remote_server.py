"""Test against a real remote GraphQL server."""

import asyncio
import pytest
from threading import Thread
import uvicorn
from graphql_api import GraphQLAPI
from graphql_http_server import GraphQLHTTPServer

from graphql_mcp.server import GraphQLMCPServer
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast


# Create a simple GraphQL API for testing
test_api = GraphQLAPI()


@test_api.type(is_root_type=True)
class TestRoot:
    @test_api.field
    def hello(self, name: str = "World") -> str:
        """Returns a greeting."""
        return f"Hello, {name}!"

    @test_api.field
    def add(self, a: int, b: int) -> int:
        """Adds two numbers."""
        return a + b

    @test_api.field(mutable=True)
    def multiply(self, x: int, y: int) -> int:
        """Multiplies two numbers."""
        return x * y


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        # New API: result has .content attribute
        return cast(TextContent, result.content[0]).text
    else:
        # Old API: result is already the content list
        return cast(TextContent, result[0]).text


def run_test_server():
    """Run the test GraphQL server in a thread."""
    graphql_server = GraphQLHTTPServer.from_api(api=test_api, auth_enabled=False)
    app = graphql_server.app

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="error")


@pytest.mark.asyncio
async def test_real_remote_graphql_server():
    """Test against a real GraphQL server running locally."""

    # Start the GraphQL server in a background thread
    server_thread = Thread(target=run_test_server, daemon=True)
    server_thread.start()

    # Give the server time to start
    await asyncio.sleep(2)

    try:
        # Create MCP server from the remote URL
        mcp_server = GraphQLMCPServer.from_remote_url(
            url="http://127.0.0.1:8765/graphql",
            name="Test Remote GraphQL"
        )

        # Test with the MCP client
        async with Client(mcp_server) as client:
            # List available tools
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            # Check that our tools are available
            assert "hello" in tool_names
            assert "add" in tool_names
            assert "multiply" in tool_names

            # Test the hello tool
            result = await client.call_tool("hello", {"name": "Remote"})
            assert get_result_text(result) == "Hello, Remote!"

            # Test the add tool
            result = await client.call_tool("add", {"a": 10, "b": 20})
            assert str(get_result_text(result)) == "30"

            # Test the multiply tool (mutation)
            result = await client.call_tool("multiply", {"x": 5, "y": 6})
            assert str(get_result_text(result)) == "30"

    except Exception as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.asyncio
async def test_remote_server_with_authentication():
    """Test remote server with authentication headers."""

    # This test demonstrates how authentication headers would work
    # In a real scenario, you'd have a server that requires auth

    try:
        # Attempt to create MCP server with auth headers
        mcp_server = GraphQLMCPServer.from_remote_url(
            url="http://127.0.0.1:8765/graphql",
            headers={
                "Authorization": "Bearer test-token",
                "X-API-Key": "test-key"
            },
            timeout=10,
            name="Authenticated Remote GraphQL"
        )

        # The server should be created successfully even with headers
        # (our test server doesn't require auth, but it should accept the headers)
        assert mcp_server is not None

    except Exception as e:
        # If the server isn't running, skip this test
        if "Connection refused" in str(e):
            pytest.skip("Test server not running")
        else:
            raise


if __name__ == "__main__":
    # Run the test manually
    asyncio.run(test_real_remote_graphql_server())
