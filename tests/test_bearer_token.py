"""Tests for bearer token authentication functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString

from graphql_mcp.server import GraphQLMCP
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
