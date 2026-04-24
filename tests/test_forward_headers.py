"""Tests for generic header forwarding and build_remote_mcp()."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from mcp.types import TextContent
from typing import cast

from graphql_mcp import server as server_module
from graphql_mcp.remote import RemoteGraphQLClient
from graphql_mcp.server import (
    _HEADER_FORWARD_DENY,
    _extract_forwarded_headers_from_context,
    add_tools_from_schema_with_remote,
    build_remote_mcp,
)


def _get_result_text(result):
    if hasattr(result, "content"):
        return cast(TextContent, result.content[0]).text
    return cast(TextContent, result[0]).text


def _simple_schema():
    return GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                ),
            },
        )
    )


class _FakeRequest:
    def __init__(self, headers):
        # Starlette's Headers behaves like a case-insensitive dict; for our
        # helper, .items() returning (name, value) is enough.
        self.headers = headers


def test_extract_forwarded_headers_disabled_returns_empty():
    ctx = object()
    assert _extract_forwarded_headers_from_context(ctx, None) == {}
    assert _extract_forwarded_headers_from_context(ctx, []) == {}


def test_extract_forwarded_headers_no_context():
    assert _extract_forwarded_headers_from_context(None, ["authorization"]) == {}


def test_extract_forwarded_headers_allowlist():
    fake_req = _FakeRequest({
        "Authorization": "Bearer abc",
        "X-API-Key": "sekret",
        "X-Trace": "trace-1",
        "User-Agent": "claude",
    })
    with patch.object(server_module, "_get_http_request", return_value=fake_req):
        got = _extract_forwarded_headers_from_context(
            object(), ["authorization", "X-API-Key"]
        )
    assert got == {"authorization": "Bearer abc", "x-api-key": "sekret"}


def test_extract_forwarded_headers_wildcard_strips_denylist():
    fake_req = _FakeRequest({
        "Authorization": "Bearer abc",
        "Host": "bridge.local",
        "Content-Length": "42",
        "Content-Type": "application/json",
        "X-Custom": "yes",
    })
    with patch.object(server_module, "_get_http_request", return_value=fake_req):
        got = _extract_forwarded_headers_from_context(object(), "*")
    # Auth + X-Custom kept, hop-by-hop / framing stripped
    assert got == {"authorization": "Bearer abc", "x-custom": "yes"}
    for denied in ("host", "content-length", "content-type"):
        assert denied in _HEADER_FORWARD_DENY
        assert denied not in got


def test_extract_forwarded_headers_handles_getter_errors():
    def _boom():
        raise RuntimeError("no request in this context")

    with patch.object(server_module, "_get_http_request", side_effect=_boom):
        assert _extract_forwarded_headers_from_context(
            object(), ["authorization"]) == {}


@pytest.mark.asyncio
async def test_execute_with_token_merges_extra_headers():
    client = RemoteGraphQLClient(
        "http://example.com/graphql",
        headers={"User-Agent": "graphql-mcp-bridge/1.0"},
    )

    captured = {}

    async def _fake_execute(query, variables, operation_name,
                            retry_on_auth_error, headers):
        captured["headers"] = headers
        return {"hello": "ok"}

    with patch.object(client, "_execute_request", side_effect=_fake_execute):
        await client.execute_with_token(
            "query { hello }",
            extra_headers={"X-API-Key": "sekret", "X-Trace": "t1"},
        )
    assert captured["headers"]["User-Agent"] == "graphql-mcp-bridge/1.0"
    assert captured["headers"]["X-API-Key"] == "sekret"
    assert captured["headers"]["X-Trace"] == "t1"


@pytest.mark.asyncio
async def test_bearer_override_wins_over_extra_authorization():
    client = RemoteGraphQLClient("http://example.com/graphql")

    captured = {}

    async def _fake_execute(query, variables, operation_name,
                            retry_on_auth_error, headers):
        captured["headers"] = headers
        return {}

    with patch.object(client, "_execute_request", side_effect=_fake_execute):
        await client.execute_with_token(
            "query { hello }",
            bearer_token_override="winning-token",
            extra_headers={"Authorization": "Bearer losing-token"},
        )
    assert captured["headers"]["Authorization"] == "Bearer winning-token"


@pytest.mark.asyncio
async def test_forward_headers_end_to_end_remote_tool():
    schema = _simple_schema()
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock(return_value={"hello": "hi"})

    server = FastMCP(name="TestServer")
    add_tools_from_schema_with_remote(
        schema, server, mock_client,
        forward_headers=["authorization", "X-API-Key"],
    )

    fake_req = _FakeRequest({
        "Authorization": "Bearer user-tok",
        "X-API-Key": "abc",
        "X-Other": "ignore-me",
    })

    with patch.object(server_module, "_get_http_request", return_value=fake_req):
        async with Client(server) as c:
            result = await c.call_tool("hello", {"name": "Alice"})
    assert _get_result_text(result) == "hi"

    call = mock_client.execute_with_token.call_args
    extra_headers = call.kwargs["extra_headers"]
    assert extra_headers == {
        "authorization": "Bearer user-tok",
        "x-api-key": "abc",
    }


@pytest.mark.asyncio
async def test_forward_headers_disabled_by_default():
    schema = _simple_schema()
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock(return_value={"hello": "hi"})

    server = FastMCP(name="TestServer")
    add_tools_from_schema_with_remote(schema, server, mock_client)

    fake_req = _FakeRequest({"Authorization": "Bearer user-tok"})
    with patch.object(server_module, "_get_http_request", return_value=fake_req):
        async with Client(server) as c:
            await c.call_tool("hello", {"name": "Alice"})

    call = mock_client.execute_with_token.call_args
    # When forward_headers is not set, no extra_headers passed (or None).
    assert call.kwargs.get("extra_headers") is None


def test_build_remote_mcp_is_classmethod_equivalent():
    schema = _simple_schema()

    with patch("graphql_mcp.remote.fetch_remote_schema_sync", return_value=schema):
        instance = build_remote_mcp(
            "http://example.com/graphql",
            forward_headers=["authorization"],
            graphql_http=False,
        )

    assert instance.schema is schema
    assert instance.remote_client is not None
    assert instance.remote_client.url == "http://example.com/graphql"


def test_from_remote_url_delegates_to_build_remote_mcp():
    with patch.object(server_module, "build_remote_mcp") as mocked:
        mocked.return_value = Mock()
        server_module.GraphQLMCP.from_remote_url(
            "http://example.com/graphql",
            bearer_token="tok",
            forward_headers="*",
            graphql_http=False,
        )
    mocked.assert_called_once()
    kwargs = mocked.call_args.kwargs
    assert kwargs["bearer_token"] == "tok"
    assert kwargs["forward_headers"] == "*"
    assert kwargs["graphql_http"] is False
