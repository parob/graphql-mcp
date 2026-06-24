"""Tests for the per-library examples (library_*.py).

Each example exposes the same small "users" API through a different GraphQL
library and demonstrates the @mcp directive. These tests assert that, for every
library, basic exposure works AND the @mcp customizations take effect:

- list_users          -> normal tool
- fetch_user          -> renamed from get_user_by_id, with arg "id" (was userId)
- internal_metrics    -> hidden field, not exposed
- debug_token         -> hidden argument, not exposed

Note: @mcp is native for graphql-api, graphql-core and Ariadne. For Strawberry
and Graphene it is NOT native — those examples apply @mcp via a documented
workaround (see https://graphql-mcp.com/strawberry-graphene). These tests
assert the workarounds produce the same end result, so they double as
regression guards that the workarounds keep working.
"""

import pytest
from typing import cast

import httpx
from fastmcp.client import Client
from mcp.types import TextContent


def get_result_text(result):
    if hasattr(result, "content"):
        return cast(TextContent, result.content[0]).text
    return cast(TextContent, result[0]).text


# (module name, expected GraphiQL-served field, http port path is irrelevant here)
LIBRARIES = [
    "library_graphql_api",
    "library_graphql_core",
    "library_ariadne",
    "library_strawberry",
    "library_graphene",
]


def _load(module_name):
    import importlib
    return importlib.import_module(module_name)


@pytest.fixture(params=LIBRARIES)
def example(request):
    return _load(request.param)


class TestBasicExposure:

    async def test_expected_tools(self, example):
        async with Client(example.server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            # Basic field is exposed under its snake_case name.
            assert "list_users" in names
            # Renamed via @mcp.
            assert "fetch_user" in names
            # Original (pre-rename) name must be gone.
            assert "get_user_by_id" not in names
            # Hidden field must not be exposed under any name.
            assert "internal_metrics" not in names
            assert "internalMetrics" not in names

    async def test_list_users_call(self, example):
        async with Client(example.server) as client:
            result = await client.call_tool("list_users", {})
            text = get_result_text(result)
            assert "Alice" in text
            assert "Bob" in text


class TestMcpDirective:

    async def test_field_renamed_with_description(self, example):
        async with Client(example.server) as client:
            tools = await client.list_tools()
            fetch_user = next(t for t in tools if t.name == "fetch_user")
            assert fetch_user.description == "Fetch a user by ID."

    async def test_arg_renamed_and_hidden_arg_absent(self, example):
        async with Client(example.server) as client:
            tools = await client.list_tools()
            fetch_user = next(t for t in tools if t.name == "fetch_user")
            props = fetch_user.inputSchema.get("properties", {})
            # Argument renamed userId -> id.
            assert "id" in props
            assert "userId" not in props
            assert "user_id" not in props
            # Hidden argument absent under any spelling.
            assert "debugToken" not in props
            assert "debug_token" not in props

    async def test_call_renamed_tool_with_renamed_arg(self, example):
        async with Client(example.server) as client:
            # Caller uses the MCP-facing arg name "id"; graphql-mcp translates
            # it back to the GraphQL "userId" on the way out.
            result = await client.call_tool("fetch_user", {"id": "1"})
            assert get_result_text(result) == "Alice"


class TestGraphQLHttp:

    async def test_graphql_endpoint(self, example):
        transport = httpx.ASGITransport(app=example.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/graphql", json={"query": "{ listUsers }"})
            assert resp.status_code == 200
            data = resp.json()
            assert "Alice" in data["data"]["listUsers"]
