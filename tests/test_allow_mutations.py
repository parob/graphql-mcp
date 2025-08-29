"""Tests for allow_mutations functionality."""

import pytest
from unittest.mock import Mock, patch
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument

from graphql_mcp.server import (
    GraphQLMCP,
    add_tools_from_schema,
    add_tools_from_schema_with_remote
)
from graphql_mcp.remote import RemoteGraphQLClient
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast


def get_result_text(result):
    """Helper function to get text from result"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


def create_test_schema():
    """Create a test GraphQL schema with both queries and mutations."""
    return GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "getUser": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString)
                    },
                    description="Get a user by ID"
                ),
                "listUsers": GraphQLField(
                    GraphQLString,
                    description="List all users"
                )
            }
        ),
        mutation=GraphQLObjectType(
            "Mutation",
            fields={
                "createUser": GraphQLField(
                    GraphQLString,
                    args={
                        "name": GraphQLArgument(GraphQLString),
                        "email": GraphQLArgument(GraphQLString)
                    },
                    description="Create a new user"
                ),
                "deleteUser": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString)
                    },
                    description="Delete a user"
                )
            }
        )
    )


@pytest.mark.asyncio
async def test_from_schema_with_mutations_enabled():
    """Test that mutations are included when allow_mutations=True (default)."""

    schema = create_test_schema()
    server = GraphQLMCP.from_schema(schema, name="Test Server")

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should include both queries and mutations
        assert "get_user" in tool_names
        assert "list_users" in tool_names
        assert "create_user" in tool_names
        assert "delete_user" in tool_names

        # Verify we have 4 tools total
        assert len(tools) == 4


@pytest.mark.asyncio
async def test_from_schema_with_mutations_disabled():
    """Test that mutations are excluded when allow_mutations=False."""

    schema = create_test_schema()
    server = GraphQLMCP.from_schema(schema, allow_mutations=False, name="Test Server")

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should include only queries
        assert "get_user" in tool_names
        assert "list_users" in tool_names

        # Should NOT include mutations
        assert "create_user" not in tool_names
        assert "delete_user" not in tool_names

        # Verify we have only 2 tools (queries only)
        assert len(tools) == 2


@pytest.mark.asyncio
async def test_from_remote_url_with_mutations_enabled():
    """Test remote server with mutations enabled."""

    # Mock the schema fetch
    schema = create_test_schema()

    with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
        mock_fetch.return_value = schema

        server = GraphQLMCP.from_remote_url(
            url="http://api.example.com/graphql",
            allow_mutations=True,
            name="Remote Server"
        )

        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            # Should include both queries and mutations
            assert "get_user" in tool_names
            assert "list_users" in tool_names
            assert "create_user" in tool_names
            assert "delete_user" in tool_names

            # Verify we have 4 tools total
            assert len(tools) == 4


@pytest.mark.asyncio
async def test_from_remote_url_with_mutations_disabled():
    """Test remote server with mutations disabled."""

    # Mock the schema fetch
    schema = create_test_schema()

    with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
        mock_fetch.return_value = schema

        server = GraphQLMCP.from_remote_url(
            url="http://api.example.com/graphql",
            allow_mutations=False,
            name="Remote Server"
        )

        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            # Should include only queries
            assert "get_user" in tool_names
            assert "list_users" in tool_names

            # Should NOT include mutations
            assert "create_user" not in tool_names
            assert "delete_user" not in tool_names

            # Verify we have only 2 tools (queries only)
            assert len(tools) == 2


@pytest.mark.asyncio
async def test_add_tools_from_schema_with_mutations_disabled():
    """Test the standalone add_tools_from_schema function with mutations disabled."""

    schema = create_test_schema()
    server = FastMCP(name="Test Server")

    # Add tools with mutations disabled
    add_tools_from_schema(schema, server, allow_mutations=False)

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should include only queries
        assert "get_user" in tool_names
        assert "list_users" in tool_names

        # Should NOT include mutations
        assert "create_user" not in tool_names
        assert "delete_user" not in tool_names


@pytest.mark.asyncio
async def test_add_tools_from_schema_with_remote_mutations_disabled():
    """Test the remote schema function with mutations disabled."""

    schema = create_test_schema()
    server = FastMCP(name="Test Server")

    # Create a mock remote client
    mock_client = Mock(spec=RemoteGraphQLClient)

    # Add tools with mutations disabled
    add_tools_from_schema_with_remote(schema, server, mock_client, allow_mutations=False)

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should include only queries
        assert "get_user" in tool_names
        assert "list_users" in tool_names

        # Should NOT include mutations
        assert "create_user" not in tool_names
        assert "delete_user" not in tool_names


@pytest.mark.asyncio
async def test_schema_with_no_mutations():
    """Test schema with no mutations defined."""

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "hello": GraphQLField(GraphQLString, description="Hello world")
            }
        )
        # No mutation type
    )

    # Should work fine with allow_mutations=True (default)
    server1 = GraphQLMCP.from_schema(schema, name="Server1")

    async with Client(server1) as client:
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "hello"

    # Should also work fine with allow_mutations=False
    server2 = GraphQLMCP.from_schema(schema, allow_mutations=False, name="Server2")

    async with Client(server2) as client:
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "hello"


@pytest.mark.asyncio
async def test_schema_with_only_mutations():
    """Test schema with only mutations (no queries)."""

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "__typename": GraphQLField(GraphQLString)  # Minimal query type
            }
        ),
        mutation=GraphQLObjectType(
            "Mutation",
            fields={
                "createUser": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                    description="Create user"
                )
            }
        )
    )

    # With mutations enabled
    server1 = GraphQLMCP.from_schema(schema, allow_mutations=True, name="Server1")

    async with Client(server1) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should have the mutation and the minimal query
        assert "create_user" in tool_names
        assert "__typename" in tool_names
        assert len(tools) == 2

    # With mutations disabled
    server2 = GraphQLMCP.from_schema(schema, allow_mutations=False, name="Server2")

    async with Client(server2) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Should have only the minimal query
        assert "create_user" not in tool_names
        assert "__typename" in tool_names
        assert len(tools) == 1


@pytest.mark.asyncio
async def test_bearer_token_with_mutations_disabled():
    """Test that bearer token still works when mutations are disabled."""

    schema = create_test_schema()

    with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
        mock_fetch.return_value = schema

        server = GraphQLMCP.from_remote_url(
            url="http://api.example.com/graphql",
            bearer_token="test-token",
            allow_mutations=False,
            name="Auth Server"
        )

        # Verify the fetch was called with the bearer token
        call_args = mock_fetch.call_args[0]
        headers = call_args[1]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"

        # Verify only queries are available
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            assert "get_user" in tool_names
            assert "list_users" in tool_names
            assert "create_user" not in tool_names
            assert "delete_user" not in tool_names
