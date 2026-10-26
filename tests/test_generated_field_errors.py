"""A field graphql-mcp added to a remote tool's selection set doesn't fail the call."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from graphql import (
    TypeInfo,
    TypeInfoVisitor,
    Visitor,
    build_schema,
    get_location,
    graphql,
    parse,
    visit,
)

from graphql_mcp.remote import RemoteGraphQLClient, RemoteGraphQLError
from graphql_mcp.server import add_tools_from_schema_with_remote

SDL = """
type Owner { login: String, email: String }
type Billing { email: String }

type Repository {
  name: String
  projects: [String]
  owner: Owner
  billing: Billing
  topics: [String]
  issue(number: Int!): Issue
}

type Issue { title: String, assignee: String }

type Query {
  repository(name: String!): Repository
  secret: String
}

type Mutation { star(name: String!): Repository }
"""


def _fail(*_args, **_kwargs):
    raise ValueError("Not allowed to read topics")


ROOT = {
    "repository": {
        "name": "graphql-mcp",
        "projects": ["roadmap"],
        "owner": {"login": "parob", "email": "rob@example.com"},
        "billing": {"email": "billing@example.com"},
        "topics": _fail,
        "issue": {"title": "Bug", "assignee": "parob"},
    },
    "star": {"name": "graphql-mcp", "projects": None, "owner": None,
             "billing": None, "topics": None},
    "secret": "hidden",
}


class _ScopedUpstream:
    """Runs queries against a local schema, refusing ``gated`` fields the way
    GitHub refuses fields a token lacks the scope for: the whole query is
    rejected, with each field's location and no ``data`` entry."""

    def __init__(self, gated, root=ROOT):
        self.schema = build_schema(SDL)
        self.gated = gated
        self.root = root
        self.queries = []

    async def execute_with_token(self, query, variables=None, **_kwargs):
        self.queries.append(query)
        document = parse(query)
        type_info = TypeInfo(self.schema)
        gated, refused = self.gated, []

        class Scopes(Visitor):
            def enter_field(self, node, *_args):
                parent = type_info.get_parent_type()
                if parent and f"{parent.name}.{node.name.value}" in gated:
                    location = get_location(document.loc.source, node.loc.start)
                    refused.append({
                        "type": "INSUFFICIENT_SCOPES",
                        "message": f"The '{node.name.value}' field requires a scope",
                        "locations": [{"line": location.line, "column": location.column}],
                    })

        visit(document, TypeInfoVisitor(type_info, Scopes()))
        if refused:
            raise RemoteGraphQLError(refused, None, False, query)
        result = await graphql(
            self.schema, query, root_value=self.root, variable_values=variables)
        if result.errors:
            raise RemoteGraphQLError(
                [error.formatted for error in result.errors], result.data, True, query)
        return result.data


async def _call(upstream, tool, arguments):
    server = FastMCP(name="remote")
    add_tools_from_schema_with_remote(
        upstream.schema, server, upstream, allow_mutations=True)
    async with Client(server) as client:
        return await client.call_tool(tool, arguments, raise_on_error=False)


@pytest.mark.asyncio
async def test_retries_without_fields_the_upstream_refused():
    upstream = _ScopedUpstream({"Repository.projects", "Owner.email", "Billing.email"})

    result = await _call(upstream, "repository", {"name": "graphql-mcp"})

    assert not result.is_error
    data = result.structured_content
    assert data["owner"] == {"login": "parob"}
    # billing selected nothing else, so it goes too rather than staying empty.
    assert "projects" not in data and "billing" not in data
    assert len(upstream.queries) == 2


@pytest.mark.asyncio
async def test_returns_partial_data_when_a_generated_field_fails():
    upstream = _ScopedUpstream(set())

    result = await _call(upstream, "repository", {"name": "graphql-mcp"})

    assert not result.is_error
    data = result.structured_content
    assert data["name"] == "graphql-mcp"
    assert data["topics"] is None
    assert len(upstream.queries) == 1


@pytest.mark.asyncio
async def test_error_on_the_tools_own_field_still_fails():
    upstream = _ScopedUpstream({"Query.secret"})

    result = await _call(upstream, "secret", {})

    assert result.is_error
    assert "INSUFFICIENT_SCOPES" in result.content[0].text
    assert len(upstream.queries) == 1


@pytest.mark.asyncio
async def test_nested_tool_retries_below_its_own_fields():
    upstream = _ScopedUpstream({"Issue.assignee"})

    result = await _call(
        upstream, "repository_issue", {"repository_name": "graphql-mcp", "number": 1})

    assert not result.is_error
    assert result.structured_content == {"title": "Bug"}
    assert len(upstream.queries) == 2


@pytest.mark.asyncio
async def test_rejected_mutation_is_retried_because_it_never_ran():
    upstream = _ScopedUpstream({"Repository.projects"})

    result = await _call(upstream, "star", {"name": "graphql-mcp"})

    assert not result.is_error
    assert result.structured_content["name"] == "graphql-mcp"
    assert len(upstream.queries) == 2


@pytest.mark.asyncio
async def test_mutation_that_ran_is_not_retried():
    def star_then_fail(*_args, **_kwargs):
        raise ValueError("Starred, but the result can't be read")

    upstream = _ScopedUpstream(set(), root={**ROOT, "star": star_then_fail})

    result = await _call(upstream, "star", {"name": "graphql-mcp"})

    assert result.is_error
    assert len(upstream.queries) == 1


@pytest.mark.asyncio
async def test_error_without_a_location_still_fails():
    class Upstream(_ScopedUpstream):
        async def execute_with_token(self, query, variables=None, **_kwargs):
            self.queries.append(query)
            raise RemoteGraphQLError([{"message": "Rate limited"}], None, False, query)

    upstream = Upstream(set())

    result = await _call(upstream, "repository", {"name": "graphql-mcp"})

    assert result.is_error
    assert len(upstream.queries) == 1


def _post_returning(payload):
    response = MagicMock(status=200, content_type="application/json")
    response.json = AsyncMock(return_value=payload)
    post = MagicMock()
    post.return_value.__aenter__ = AsyncMock(return_value=response)
    post.return_value.__aexit__ = AsyncMock(return_value=None)
    return post


@pytest.mark.asyncio
async def test_client_error_says_whether_the_operation_ran():
    client = RemoteGraphQLClient(
        "http://example.com/graphql", schema=build_schema(SDL))
    query = "query { repository(name: \"x\") { name, topics } }"
    errors = [{"message": "nope", "locations": [{"line": 1, "column": 3}]}]

    with patch("aiohttp.ClientSession.post", _post_returning({"errors": errors})):
        with pytest.raises(RemoteGraphQLError) as rejected:
            await client.execute(query)
    with patch("aiohttp.ClientSession.post", _post_returning(
            {"data": {"repository": {"name": "x", "topics": None}}, "errors": errors})):
        with pytest.raises(RemoteGraphQLError) as partial:
            await client.execute(query)

    assert not rejected.value.executed and rejected.value.data is None
    assert rejected.value.query == query
    assert str(rejected.value) == f"GraphQL errors: {errors}"
    assert partial.value.executed
    assert partial.value.data == {"repository": {"name": "x", "topics": []}}
