"""Tests for bearer token authentication functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastmcp import FastMCP
from fastmcp.client import Client
from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from graphql_mcp import server as server_module
from graphql_mcp.server import GraphQLMCP, add_tools_from_schema_with_remote
from graphql_mcp.remote import RemoteGraphQLClient
from mcp.types import TextContent
from typing import cast


def get_result_text(result):
    """Helper function to get text from result"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_from_remote_url_with_bearer_token():
    """Test creating a server with bearer token authentication."""

    # Mock introspection response
    mock_introspection_response = {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "name": "Query",
                        "kind": "OBJECT",
                        "fields": [
                            {
                                "name": "protectedData",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String"
                                },
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
                        "name": "String",
                        "kind": "SCALAR",
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

    # Create proper mocks
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_introspection_response)

    # Create an async context manager for post
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response
    mock_post_cm.__aexit__.return_value = None

    # Set up the session mock
    mock_session.post.return_value = mock_post_cm

    # Create an async context manager for ClientSession
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    with patch('graphql_mcp.remote.aiohttp.ClientSession', return_value=mock_session_cm):
        with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
            # Mock the schema fetch
            mock_schema = GraphQLSchema(
                query=GraphQLObjectType(
                    "Query",
                    fields={
                        "protectedData": GraphQLField(GraphQLString)
                    }
                )
            )
            mock_fetch.return_value = mock_schema

            # Create server with bearer token
            _ = GraphQLMCP.from_remote_url(
                url="http://api.example.com/graphql",
                bearer_token="test-token-123",
                name="Protected API"
            )

            # Verify the bearer token was included in headers
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args[0]
            headers = call_args[1]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-token-123"


@pytest.mark.asyncio
async def test_bearer_token_with_additional_headers():
    """Test that bearer token works alongside additional headers."""

    with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
        mock_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                fields={
                    "data": GraphQLField(GraphQLString)
                }
            )
        )
        mock_fetch.return_value = mock_schema

        # Create server with both bearer token and additional headers
        _ = GraphQLMCP.from_remote_url(
            url="http://api.example.com/graphql",
            bearer_token="my-bearer-token",
            headers={
                "X-API-Key": "additional-key",
                "X-Request-ID": "req-123"
            },
            name="Multi-Auth API"
        )

        # Verify all headers were included
        call_args = mock_fetch.call_args[0]
        headers = call_args[1]

        assert headers["Authorization"] == "Bearer my-bearer-token"
        assert headers["X-API-Key"] == "additional-key"
        assert headers["X-Request-ID"] == "req-123"


@pytest.mark.asyncio
async def test_token_refresh_callback():
    """Test token refresh callback functionality."""

    token_counter = {"value": 0}

    def refresh_token():
        """Mock token refresh callback."""
        token_counter["value"] += 1
        return f"refreshed-token-{token_counter['value']}"

    client = RemoteGraphQLClient(
        url="http://api.example.com/graphql",
        bearer_token="initial-token",
        token_refresh_callback=refresh_token
    )

    # Verify initial token is set
    assert client.headers["Authorization"] == "Bearer initial-token"

    # Test token refresh
    refreshed = await client.refresh_token()
    assert refreshed is True
    assert client.headers["Authorization"] == "Bearer refreshed-token-1"

    # Test another refresh
    refreshed = await client.refresh_token()
    assert refreshed is True
    assert client.headers["Authorization"] == "Bearer refreshed-token-2"


@pytest.mark.asyncio
async def test_automatic_token_refresh_on_401():
    """Test that token refresh callback works properly."""

    refresh_called = {"value": False}

    def refresh_token():
        refresh_called["value"] = True
        return "new-token"

    client = RemoteGraphQLClient(
        url="http://api.example.com/graphql",
        bearer_token="expired-token",
        token_refresh_callback=refresh_token
    )

    # Test manual token refresh
    assert client.headers["Authorization"] == "Bearer expired-token"

    refreshed = await client.refresh_token()
    assert refreshed is True
    assert refresh_called["value"] is True
    assert client.headers["Authorization"] == "Bearer new-token"


@pytest.mark.asyncio
async def test_no_refresh_without_callback():
    """Test that refresh doesn't happen without a callback."""

    client = RemoteGraphQLClient(
        url="http://api.example.com/graphql",
        bearer_token="token"
    )

    # Try to refresh without callback
    refreshed = await client.refresh_token()
    assert refreshed is False
    assert client.headers["Authorization"] == "Bearer token"  # Unchanged


def _schema_with_nested_field():
    user = GraphQLObjectType("User", {
        "posts": GraphQLField(
            GraphQLList(GraphQLString), args={"first": GraphQLArgument(GraphQLInt)}),
    })
    return GraphQLSchema(query=GraphQLObjectType("Query", {
        "hello": GraphQLField(
            GraphQLString, args={"name": GraphQLArgument(GraphQLString)}),
        "user": GraphQLField(
            user, args={"id": GraphQLArgument(GraphQLNonNull(GraphQLID))}),
    }))


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


async def _call_remote_tool(tool, arguments, forward_bearer_token):
    """Call a remote tool during a request carrying a bearer token; return the token sent upstream."""
    remote_client = AsyncMock(spec=RemoteGraphQLClient)
    remote_client.execute_with_token = AsyncMock(return_value={})
    server = FastMCP(name="TestServer")
    add_tools_from_schema_with_remote(
        _schema_with_nested_field(), server, remote_client,
        forward_bearer_token=forward_bearer_token,
    )

    request = _FakeRequest({"authorization": "Bearer caller-token"})
    with patch.object(server_module, "_get_http_request", return_value=request):
        async with Client(server) as client:
            await client.call_tool(tool, arguments)

    return remote_client.execute_with_token.call_args.kwargs["bearer_token_override"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, arguments", [
    ("hello", {"name": "Ann"}),
    ("user_posts", {"user_id": "1", "first": 2}),
])
async def test_forward_bearer_token_reaches_remote_server(tool, arguments):
    """The caller's token is forwarded, although generated tools never receive a Context."""
    assert await _call_remote_tool(tool, arguments, forward_bearer_token=True) == "caller-token"


@pytest.mark.asyncio
async def test_bearer_token_not_forwarded_by_default():
    assert await _call_remote_tool("hello", {"name": "Ann"}, forward_bearer_token=False) is None
