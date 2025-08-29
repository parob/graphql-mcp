"""Test remote GraphQL server functionality with reliable mocking."""

import asyncio
import pytest
import aiohttp
import json
from unittest.mock import AsyncMock, patch, MagicMock

from graphql_mcp.server import GraphQLMCP
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        # New API: result has .content attribute
        return cast(TextContent, result.content[0]).text
    else:
        # Old API: result is already the content list
        return cast(TextContent, result[0]).text


# Mock schema response for introspection
MOCK_SCHEMA_RESPONSE = {
    "data": {
        "__schema": {
            "queryType": {"name": "Query"},
            "mutationType": {"name": "Mutation"},
            "subscriptionType": None,
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "description": None,
                    "fields": [
                        {
                            "name": "hello",
                            "description": "Returns a greeting",
                            "args": [
                                {
                                    "name": "name",
                                    "description": None,
                                    "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                                    "defaultValue": '"World"'
                                }
                            ],
                            "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "String", "ofType": None}},
                            "isDeprecated": False,
                            "deprecationReason": None
                        },
                        {
                            "name": "add",
                            "description": "Adds two numbers",
                            "args": [
                                {
                                    "name": "a",
                                    "description": None,
                                    "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                                    "defaultValue": None
                                },
                                {
                                    "name": "b",
                                    "description": None,
                                    "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                                    "defaultValue": None
                                }
                            ],
                            "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                            "isDeprecated": False,
                            "deprecationReason": None
                        }
                    ],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None
                },
                {
                    "kind": "OBJECT",
                    "name": "Mutation",
                    "description": None,
                    "fields": [
                        {
                            "name": "multiply",
                            "description": "Multiplies two numbers",
                            "args": [
                                {
                                    "name": "x",
                                    "description": None,
                                    "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                                    "defaultValue": None
                                },
                                {
                                    "name": "y",
                                    "description": None,
                                    "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                                    "defaultValue": None
                                }
                            ],
                            "type": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}},
                            "isDeprecated": False,
                            "deprecationReason": None
                        }
                    ],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None
                },
                {
                    "kind": "SCALAR",
                    "name": "String",
                    "description": "Built-in String",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None
                },
                {
                    "kind": "SCALAR",
                    "name": "Int",
                    "description": "Built-in Int",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None
                }
            ],
            "directives": []
        }
    }
}


def create_mock_response(json_data=None):
    """Create a mock HTTP response for GraphQL requests."""
    mock_response = AsyncMock()
    mock_response.status = 200

    if json_data and 'query' in json_data:
        query = json_data['query'].strip()
        variables = json_data.get('variables', {})

        # Handle introspection (including first call which may not have query key)
        if 'IntrospectionQuery' in query or '__schema' in query or 'queryType' in query:
            mock_response.json = AsyncMock(return_value=MOCK_SCHEMA_RESPONSE)
        # Handle regular queries
        elif 'hello' in query:
            name = variables.get('name', 'World')
            mock_response.json = AsyncMock(return_value={
                "data": {"hello": f"Hello, {name}!"}
            })
        elif 'add' in query:
            a = variables.get('a', 0)
            b = variables.get('b', 0)
            mock_response.json = AsyncMock(return_value={
                "data": {"add": a + b}
            })
        elif 'multiply' in query:
            x = variables.get('x', 1)
            y = variables.get('y', 1)
            mock_response.json = AsyncMock(return_value={
                "data": {"multiply": x * y}
            })
        else:
            mock_response.json = AsyncMock(return_value=MOCK_SCHEMA_RESPONSE)
    else:
        # Default introspection response for schema fetching during server creation
        mock_response.json = AsyncMock(return_value=MOCK_SCHEMA_RESPONSE)

    return mock_response


@pytest.mark.asyncio
async def test_real_remote_graphql_server():
    """Test against a mock remote GraphQL server."""

    def mock_post(url, json=None, **kwargs):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=create_mock_response(json))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_post):
        # Create MCP server from a mock remote URL
        mcp_server = GraphQLMCP.from_remote_url(
            url="http://mock-server.example.com/graphql",
            name="Test Remote GraphQL",
            timeout=10
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
            # Test the hello tool
            result = await client.call_tool("hello", {"name": "Remote"})
            assert get_result_text(result) == "Hello, Remote!"

            # Test the add tool
            result = await client.call_tool("add", {"a": 10, "b": 20})
            assert str(get_result_text(result)) == "30"

            # Test the multiply tool (mutation)
            result = await client.call_tool("multiply", {"x": 5, "y": 6})
            assert str(get_result_text(result)) == "30"


@pytest.mark.asyncio
async def test_remote_server_with_headers():
    """Test remote server accepts custom headers."""

    headers_received = {}

    def mock_post_with_headers(url, json=None, headers=None, **kwargs):
        headers_received.update(headers or {})
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=create_mock_response(json))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_post_with_headers):
        # Create MCP server with custom headers
        mcp_server = GraphQLMCP.from_remote_url(
            url="http://mock-server.example.com/graphql",
            headers={
                "X-Custom-Header": "test-value",
                "User-Agent": "GraphQL-MCP-Test/1.0"
            },
            timeout=10,
            name="Remote GraphQL with Headers"
        )

        # The server should be created successfully with headers
        assert mcp_server is not None

        # Test that it works by calling a simple tool
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools) > 0

            result = await client.call_tool("hello", {"name": "HeaderTest"})
            assert get_result_text(result) == "Hello, HeaderTest!"

        # Verify headers were sent
        assert "X-Custom-Header" in headers_received
        assert headers_received["X-Custom-Header"] == "test-value"
        assert "User-Agent" in headers_received
        assert headers_received["User-Agent"] == "GraphQL-MCP-Test/1.0"


@pytest.mark.asyncio
async def test_remote_server_connection_error_handling():
    """Test proper error handling when server is not available."""

    def mock_connection_error(*args, **kwargs):
        raise aiohttp.ClientConnectorError(
            connection_key=MagicMock(),
            os_error=OSError("Connection refused")
        )

    with patch('aiohttp.ClientSession.post', side_effect=mock_connection_error):
        try:
            # This should fail because the connection is mocked to fail
            GraphQLMCP.from_remote_url(
                url="http://unreachable-server.example.com/graphql",
                timeout=2,
                name="Non-existent Server"
            )
            pytest.fail("Expected connection error but server creation succeeded")

        except Exception as e:
            # Should get a connection error
            error_str = str(e).lower()
            assert any(word in error_str for word in [
                "connection", "connect", "refused", "timeout", "unreachable", "failed"
            ]), f"Unexpected error type: {e}"


@pytest.mark.asyncio
async def test_remote_server_with_ssl_disabled():
    """Test remote server with SSL verification disabled."""

    ssl_config_captured = {}

    def mock_post_capture_ssl(*args, ssl=None, json=None, **kwargs):
        ssl_config_captured['ssl'] = ssl
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=create_mock_response(json))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_post_capture_ssl):
        # Create MCP server with SSL verification disabled
        mcp_server = GraphQLMCP.from_remote_url(
            url="https://mock-server.example.com/graphql",
            verify_ssl=False,
            timeout=10,
            name="Remote GraphQL No SSL"
        )

        assert mcp_server is not None

        # Verify it works
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools) > 0


@pytest.mark.asyncio
async def test_remote_server_with_bearer_token():
    """Test bearer token authentication."""

    auth_headers_received = {}

    def mock_auth_post(url, json=None, headers=None, **kwargs):
        auth_headers_received.update(headers or {})

        # Check for authorization header
        auth_header = headers.get('Authorization', '') if headers else ''

        mock_cm = AsyncMock()

        if not auth_header.startswith('Bearer '):
            # Simulate 401 Unauthorized
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json = AsyncMock(return_value={
                "errors": [{"message": "Authentication required"}]
            })
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        else:
            token = auth_header.split(' ')[1]
            if token != "test-token-123":
                # Simulate 403 Forbidden
                mock_response = AsyncMock()
                mock_response.status = 403
                mock_response.json = AsyncMock(return_value={
                    "errors": [{"message": "Invalid token"}]
                })
                mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            else:
                # Valid token - return normal response
                mock_cm.__aenter__ = AsyncMock(return_value=create_mock_response(json))

        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_auth_post):
        # Test without token - should fail
        try:
            GraphQLMCP.from_remote_url(
                url="http://auth-required.example.com/graphql",
                timeout=5,
                name="Auth Required Server"
            )
            pytest.fail("Expected authentication error")
        except Exception as e:
            error_str = str(e).lower()
            assert any(word in error_str for word in [
                "401", "authentication", "unauthorized", "error"
            ]), f"Expected auth error, got: {e}"

        # Test with correct token - should succeed
        mcp_server = GraphQLMCP.from_remote_url(
            url="http://auth-required.example.com/graphql",
            headers={"Authorization": "Bearer test-token-123"},
            timeout=5,
            name="Authenticated Server"
        )

        assert mcp_server is not None

        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools) > 0

        # Verify the correct token was sent
        assert "Authorization" in auth_headers_received
        assert auth_headers_received["Authorization"] == "Bearer test-token-123"


@pytest.mark.asyncio
async def test_remote_server_query_execution():
    """Test direct GraphQL query execution."""

    queries_received = []

    def mock_post_capture_queries(url, json=None, **kwargs):
        if json:
            queries_received.append(json)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=create_mock_response(json))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_post_capture_queries):
        # Create server
        mcp_server = GraphQLMCP.from_remote_url(
            url="http://mock-server.example.com/graphql",
            name="Query Test Server",
            timeout=10
        )

        # Execute through MCP client
        async with Client(mcp_server) as client:
            result = await client.call_tool("hello", {"name": "QueryTest"})
            assert get_result_text(result) == "Hello, QueryTest!"

        # Verify queries were made
        assert len(queries_received) > 0

        # Should have introspection query and actual query
        introspection_found = any('__schema' in q.get('query', '') for q in queries_received)
        hello_query_found = any('hello' in q.get('query', '') for q in queries_received)

        assert introspection_found, "Should have made introspection query"
        assert hello_query_found, "Should have made hello query"


@pytest.mark.asyncio
async def test_remote_server_timeout_handling():
    """Test handling of request timeouts."""

    def mock_timeout_post(*args, **kwargs):
        raise asyncio.TimeoutError("Request timed out")

    with patch('aiohttp.ClientSession.post', side_effect=mock_timeout_post):
        try:
            GraphQLMCP.from_remote_url(
                url="http://slow-server.example.com/graphql",
                timeout=1,  # Very short timeout
                name="Slow Server"
            )
            pytest.fail("Expected timeout error")
        except Exception as e:
            error_str = str(e).lower()
            assert any(word in error_str for word in [
                "timeout", "timed out", "time out"
            ]), f"Expected timeout error, got: {e}"


@pytest.mark.asyncio
async def test_remote_server_graphql_errors():
    """Test handling of GraphQL errors from server."""

    def mock_error_response(url, json=None, **kwargs):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": None,
            "errors": [
                {
                    "message": "Field 'nonExistent' doesn't exist on type 'Query'",
                    "locations": [{"line": 1, "column": 9}]
                }
            ]
        })
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_error_response):
        try:
            GraphQLMCP.from_remote_url(
                url="http://error-server.example.com/graphql",
                name="Error Server"
            )
            pytest.fail("Expected GraphQL error")
        except Exception as e:
            error_str = str(e).lower()
            assert any(word in error_str for word in [
                "error", "field", "exist", "graphql"
            ]), f"Expected GraphQL error, got: {e}"


if __name__ == "__main__":
    # Run tests manually for development
    import pytest
    pytest.main([__file__, "-v"])