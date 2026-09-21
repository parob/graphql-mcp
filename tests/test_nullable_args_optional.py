"""Nullable GraphQL arguments without a default are optional MCP arguments.

A nullable argument with no default is legal to omit in GraphQL, and omitting
it is not the same as passing ``null`` (many servers apply a server-side
default only when the argument is absent). The tool schema must therefore not
list such arguments as required, and the wrapper must leave omitted ones out
of the operation entirely. Non-null arguments without a default stay required.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.client import Client
from graphql import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLInt,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from graphql_mcp import server as server_module
from graphql_mcp.server import GraphQLMCP, build_remote_mcp


def _schema(received: dict):
    def resolve_search(_root, _info, **kwargs):
        received.clear()
        received.update(kwargs)
        return json.dumps(kwargs)

    query = GraphQLObjectType(
        "Query",
        {
            "search": GraphQLField(
                GraphQLString,
                args={
                    "term": GraphQLArgument(GraphQLString),
                    "limit": GraphQLArgument(GraphQLInt, default_value=10),
                    "strict": GraphQLArgument(GraphQLNonNull(GraphQLBoolean)),
                },
                resolve=resolve_search,
            ),
        },
    )
    return GraphQLSchema(query=query)


@pytest.mark.asyncio
async def test_local_tool_schema_marks_only_non_null_args_required():
    server = GraphQLMCP(schema=_schema({}), graphql_http=False)
    async with Client(server) as client:
        tool = next(t for t in await client.list_tools() if t.name == "search")
    assert tool.inputSchema.get("required") == ["strict"]
    assert set(tool.inputSchema["properties"]) == {"term", "limit", "strict"}
    assert tool.inputSchema["properties"]["limit"]["default"] == 10
    assert "default" not in tool.inputSchema["properties"]["term"]


@pytest.mark.asyncio
async def test_local_tool_omits_nullable_arg_the_caller_left_out():
    received: dict = {}
    server = GraphQLMCP(schema=_schema(received), graphql_http=False)
    async with Client(server) as client:
        await client.call_tool("search", {"strict": True})
        assert received == {"strict": True, "limit": 10}

        await client.call_tool("search", {"strict": True, "term": None})
        assert received == {"strict": True, "limit": 10, "term": None}

        await client.call_tool("search", {"strict": True, "term": "x", "limit": 3})
        assert received == {"strict": True, "limit": 3, "term": "x"}


@pytest.mark.asyncio
async def test_local_tool_still_requires_non_null_arg():
    server = GraphQLMCP(schema=_schema({}), graphql_http=False)
    async with Client(server) as client:
        result = await client.call_tool("search", {"term": "x"}, raise_on_error=False)
    assert result.is_error


def _remote_instance():
    with patch("graphql_mcp.remote.fetch_remote_schema_sync", return_value=_schema({})):
        return build_remote_mcp("http://example.com/graphql", graphql_http=False)


@pytest.mark.asyncio
async def test_remote_tool_schema_marks_only_non_null_args_required():
    instance = _remote_instance()
    async with Client(instance) as client:
        tool = next(t for t in await client.list_tools() if t.name == "search")
    assert tool.inputSchema.get("required") == ["strict"]


@pytest.mark.asyncio
async def test_remote_tool_only_sends_the_args_the_caller_supplied():
    instance = _remote_instance()
    execute = AsyncMock(return_value={"search": "ok"})
    calls = []

    async def _capture(query, variables, **kwargs):
        calls.append((query, variables))
        return await execute(query, variables, **kwargs)

    with patch.object(instance.remote_client, "execute_with_token", side_effect=_capture):
        async with Client(instance) as client:
            await client.call_tool("search", {"strict": True})
            query, variables = calls[-1]
            assert variables == {"strict": True, "limit": 10}
            assert "$term" not in query and "term:" not in query
            assert "$strict: Boolean!" in query and "$limit: Int" in query

            await client.call_tool("search", {"strict": True, "term": None})
            query, variables = calls[-1]
            assert variables == {"strict": True, "limit": 10, "term": None}
            assert "$term: String" in query and "term: $term" in query


def test_build_remote_mcp_registers_tools_once():
    """The constructor must not add local tools that the remote registration
    then replaces one by one (each replacement logs a fastmcp warning)."""
    with patch.object(server_module, "add_tools_from_schema") as local_add:
        instance = _remote_instance()
    local_add.assert_not_called()

    import asyncio

    async def _names():
        async with Client(instance) as client:
            return sorted(t.name for t in await client.list_tools())

    assert asyncio.run(_names()) == ["search"]


def test_graphql_mcp_registers_local_tools_by_default():
    with patch.object(server_module, "add_tools_from_schema") as local_add:
        GraphQLMCP(schema=_schema({}), graphql_http=False)
    local_add.assert_called_once()
