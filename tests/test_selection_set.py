"""Generated selection sets only select fields a query can actually ask for."""

from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from graphql import (
    build_client_schema,
    build_schema,
    introspection_from_schema,
    parse,
    validate,
)

from graphql_mcp.remote import RemoteGraphQLClient
from graphql_mcp.server import (
    GraphQLMCP,
    _build_selection_set,
    add_tools_from_schema_with_remote,
)

SDL = """
type Issue { number: Int!, title: String! }

type Repository {
  name: String!
  "Needs an argument the generated query has no value for."
  issue(number: Int!): Issue
  "Required argument with a default: selectable."
  issues(first: Int! = 10): [Issue!]!
  "Optional argument: selectable."
  description(format: String): String
  "Deprecated fields may already be gone upstream."
  projects: [String!]! @deprecated(reason: "Use projectsV2")
  projectsV2: [String!]!
}

type Query { repository(name: String!): Repository }
"""


def _schemas():
    sdl_schema = build_schema(SDL)
    # Introspected schemas store argument defaults differently in graphql-core 3.3.
    introspected = build_client_schema(introspection_from_schema(sdl_schema))
    return [sdl_schema, introspected]


@pytest.mark.parametrize("schema", _schemas(), ids=["sdl", "introspected"])
def test_selection_set_skips_unselectable_fields(schema):
    selection = _build_selection_set(schema.type_map["Repository"])

    assert selection == (
        "{ name, issues { number, title }, description, projectsV2 }"
    )


@pytest.mark.parametrize("schema", _schemas(), ids=["sdl", "introspected"])
@pytest.mark.asyncio
async def test_remote_tool_sends_a_valid_query(schema):
    remote_client = AsyncMock(spec=RemoteGraphQLClient)
    remote_client.execute_with_token = AsyncMock(return_value={"repository": None})
    server = FastMCP(name="TestServer")
    add_tools_from_schema_with_remote(schema, server, remote_client)

    async with Client(server) as client:
        await client.call_tool("repository", {"name": "graphql-mcp"})

    query = remote_client.execute_with_token.call_args.args[0]
    assert validate(schema, parse(query)) == []


@pytest.mark.asyncio
async def test_local_tool_returns_type_with_unselectable_fields():
    schema = build_schema(SDL)
    schema.query_type.fields["repository"].resolve = lambda _root, _info, name: {
        "name": name,
        "issues": [{"number": 1, "title": "First"}],
        "description": None,
        "projects": ["classic"],
        "projectsV2": ["new"],
    }
    mcp = GraphQLMCP(schema=schema, graphql_http=False, name="t")

    async with Client(mcp) as client:
        tool = (await client.list_tools())[0]
        result = await client.call_tool("repository", {"name": "graphql-mcp"})

    assert result.structured_content["result"] == {
        "name": "graphql-mcp",
        "issues": [{"number": 1, "title": "First"}],
        "description": None,
        "projectsV2": ["new"],
    }
    # The output schema describes what the tool fetches, not the fields it skips.
    repository = tool.output_schema["properties"]["result"]["anyOf"][0]
    assert set(repository["properties"]) == {
        "name", "issues", "description", "projectsV2"}
