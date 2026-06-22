"""Regression test for issue #5.

GraphQL allows field arguments whose names are Python reserved keywords
(e.g. ``from``). These cannot be used directly as ``inspect.Parameter`` names,
which previously raised ``ValueError: 'from' is not a valid parameter name``
when building MCP tools. The tool builder now sanitizes such names (appending a
trailing underscore) while still issuing the correct GraphQL argument name.
"""
import pytest

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast

from graphql_mcp.server import add_tools_from_schema


def get_result_text(result):
    if hasattr(result, "content"):
        return cast(TextContent, result.content[0]).text
    return cast(TextContent, result[0]).text


def _build_schema():
    def resolve_slice(root, info, **kwargs):
        # GraphQL passes the original argument names ("from"/"to").
        start = kwargs.get("from", 0)
        end = kwargs.get("to", 0)
        return list(range(start, end))

    def resolve_label(root, info, **kwargs):
        # "class" is also a Python keyword.
        return f"label:{kwargs.get('class', '')}"

    query = GraphQLObjectType(
        name="Query",
        fields={
            "slice": GraphQLField(
                GraphQLList(GraphQLInt),
                args={
                    "from": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
                    "to": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
                },
                resolve=resolve_slice,
            ),
            "label": GraphQLField(
                GraphQLString,
                args={
                    "class": GraphQLArgument(GraphQLNonNull(GraphQLString)),
                },
                resolve=resolve_label,
            ),
        },
    )
    return GraphQLSchema(query=query)


def test_build_tools_with_reserved_keyword_args():
    # Previously raised ValueError: 'from' is not a valid parameter name.
    server = add_tools_from_schema(_build_schema())
    assert server is not None


@pytest.mark.asyncio
async def test_call_tool_with_reserved_keyword_args():
    server = add_tools_from_schema(_build_schema())

    async with Client(server) as client:
        tools = {t.name for t in await client.list_tools()}
        assert "slice" in tools
        assert "label" in tools

        # The reserved keyword arg is exposed with a trailing underscore.
        import json
        result = await client.call_tool("slice", {"from_": 2, "to": 5})
        assert json.loads(get_result_text(result)) == [2, 3, 4]

        result = await client.call_tool("label", {"class_": "hello"})
        assert get_result_text(result) == "label:hello"
