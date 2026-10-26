"""Nested tool names: shortest paths, no collisions, within MCP's length limit."""

import logging

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from graphql import build_schema

from graphql_mcp.server import GraphQLMCP, add_tools_from_schema_with_remote


class _FakeRemoteClient:
    async def execute_with_token(self, query, variables=None, **kwargs):
        return {}


async def _tools(server):
    async with Client(server) as client:
        return {tool.name: tool for tool in await client.list_tools()}


def _local(sdl):
    return GraphQLMCP(schema=build_schema(sdl), graphql_http=False)


def _remote(sdl):
    server = FastMCP(name="remote")
    add_tools_from_schema_with_remote(build_schema(sdl), server, _FakeRemoteClient())
    return server


BUILDERS = pytest.mark.parametrize("build", [_local, _remote], ids=["local", "remote"])


@BUILDERS
@pytest.mark.asyncio
async def test_nested_tools_hang_off_the_shortest_path(build):
    # A depth-first walk reaches Repository through Query.organization first.
    tools = await _tools(build("""
        type Issue { title: String }
        type Repository { issue(number: Int!): Issue }
        type Organization { repository(name: String!): Repository }
        type Query {
          organization(login: String!): Organization
          repository(owner: String!, name: String!): Repository
        }
    """))

    assert "repository_issue" in tools
    assert "organization_repository_issue" not in tools
    assert set(tools["repository_issue"].input_schema["properties"]) == {
        "repository_owner", "repository_name", "number"}


@BUILDERS
@pytest.mark.asyncio
async def test_colliding_nested_name_keeps_the_shorter_path(build, caplog):
    # User.gistComments and User.gist → Gist.comments both join to user_gist_comments.
    with caplog.at_level(logging.WARNING, logger="graphql_mcp.server"):
        tools = await _tools(build("""
            type Gist { comments(first: Int): [String] }
            type User {
              gistComments(first: Int): [String]
              gist(name: String!): Gist
            }
            type Query { user(login: String!): User }
        """))

    assert set(tools["user_gist_comments"].input_schema["properties"]) == {
        "user_login", "first"}
    assert "already named 'user_gist_comments'" in caplog.text


@BUILDERS
@pytest.mark.asyncio
async def test_nested_tool_never_replaces_a_top_level_tool(build):
    tools = await _tools(build("""
        type User { posts(first: Int): [String] }
        type Query {
          "Every user's posts."
          userPosts(first: Int): [String]
          user(id: ID!): User
        }
    """))

    assert tools["user_posts"].description == "Every user's posts."


@BUILDERS
@pytest.mark.asyncio
async def test_nested_tool_names_stay_within_128_characters(build, caplog):
    long = "a" * 70
    with caplog.at_level(logging.WARNING, logger="graphql_mcp.server"):
        tools = await _tools(build(f"""
            type Inner {{ {long}Leaf(id: ID!): String }}
            type Outer {{ {long}Inner: Inner }}
            type Query {{ outer: Outer }}
        """))

    assert all(len(name) <= 128 for name in tools)
    assert "longer than 128 characters" in caplog.text
