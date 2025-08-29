"""Tests for remote GraphQL server functionality."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLInt, GraphQLArgument

from graphql_mcp.server import add_tools_from_schema_with_remote
from graphql_mcp.remote import RemoteGraphQLClient, fetch_remote_schema
from fastmcp import FastMCP
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


@pytest.mark.asyncio
async def test_fetch_remote_schema():
    """Test fetching schema from a remote GraphQL server."""

    # Mock the introspection response
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
                                "name": "hello",
                                "args": [
                                    {
                                        "name": "name",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "String"
                                        },
                                        "defaultValue": None
                                    }
                                ],
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

    # Create a proper mock for aiohttp.ClientSession
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
        schema = await fetch_remote_schema("http://example.com/graphql")

        assert schema is not None
        assert schema.query_type is not None
        assert "hello" in schema.query_type.fields


@pytest.mark.asyncio
async def test_remote_graphql_client_execute():
    """Test RemoteGraphQLClient initialization and basic functionality."""

    # Test basic client creation
    client = RemoteGraphQLClient("http://example.com/graphql")
    assert client.url == "http://example.com/graphql"
    assert client.timeout == 30
    assert client.bearer_token is None

    # Test client with bearer token
    client_with_token = RemoteGraphQLClient(
        "http://example.com/graphql",
        bearer_token="test-token"
    )
    assert "Authorization" in client_with_token.headers
    assert client_with_token.headers["Authorization"] == "Bearer test-token"

    # Test token refresh without callback
    refreshed = await client.refresh_token()
    assert refreshed is False  # No callback provided


@pytest.mark.asyncio
async def test_graphql_mcp_server_from_remote_url():
    """Test creating a GraphQLMCP from a remote URL."""

    # Create a simple schema
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={
                        "name": GraphQLArgument(GraphQLString)
                    },
                    description="Returns a greeting"
                ),
                "add": GraphQLField(
                    GraphQLInt,
                    args={
                        "a": GraphQLArgument(GraphQLInt),
                        "b": GraphQLArgument(GraphQLInt)
                    },
                    description="Adds two numbers"
                )
            }
        )
    )

    # Mock the remote client
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock()

    # Test with mocked remote client
    mcp_server = FastMCP(name="TestServer")
    add_tools_from_schema_with_remote(schema, mcp_server, mock_client)

    # Set up mock responses
    mock_client.execute_with_token.side_effect = [
        {"hello": "Hello, Alice!"},
        {"add": 8}
    ]

    async with Client(mcp_server) as client:
        # Test query tool
        result = await client.call_tool("hello", {"name": "Alice"})
        assert get_result_text(result) == "Hello, Alice!"

        # Test another query tool
        result = await client.call_tool("add", {"a": 3, "b": 5})
        assert str(get_result_text(result)) == "8"

        # Verify the remote client was called correctly
        assert mock_client.execute_with_token.call_count == 2

        # Check the first call (hello)
        first_call = mock_client.execute_with_token.call_args_list[0]
        assert "hello" in first_call[0][0]
        assert first_call[0][1] == {"name": "Alice"}

        # Check the second call (add)
        second_call = mock_client.execute_with_token.call_args_list[1]
        assert "add" in second_call[0][0]
        assert second_call[0][1] == {"a": 3, "b": 5}


@pytest.mark.asyncio
async def test_remote_server_with_headers():
    """Test remote server connection with authentication headers."""

    headers = {"Authorization": "Bearer test-token"}

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
        schema = await fetch_remote_schema("http://example.com/graphql", headers=headers)

        # Verify headers were passed
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[1]["headers"] == headers

        assert schema is not None
        assert schema.query_type is not None
        assert "protectedData" in schema.query_type.fields
