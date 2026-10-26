"""The remote client learns field types from the schema it is given, not a second introspection."""

from unittest.mock import AsyncMock, patch

import pytest
from graphql import build_schema, introspection_from_schema

from graphql_mcp.remote import RemoteGraphQLClient
from graphql_mcp.server import build_remote_mcp

SDL = """
interface Node { id: ID! }

type User implements Node {
  id: ID!
  name: String
  tags: [String!]
  friends: [User!]!
  profile: Profile
}

type Profile { bio: String, links: [String] }

type Query { user(id: ID!): User, users: [User] }
type Mutation { renameUser(id: ID!, name: String!): User }
"""


@pytest.mark.asyncio
async def test_schema_fills_the_caches_introspection_would():
    schema = build_schema(SDL)
    introspected = RemoteGraphQLClient("http://example.com/graphql")
    with patch.object(
        introspected, "_raw_execute_request",
        AsyncMock(return_value=introspection_from_schema(schema)),
    ):
        await introspected._introspect_schema()

    seeded = RemoteGraphQLClient("http://example.com/graphql", schema=schema)

    assert seeded._introspected
    assert seeded._array_fields_cache == introspected._array_fields_cache
    assert seeded._field_type_map == introspected._field_type_map


@pytest.mark.asyncio
async def test_remote_server_client_does_not_introspect_again():
    schema = build_schema(SDL)
    with patch("graphql_mcp.remote.fetch_remote_schema_sync", return_value=schema):
        server = build_remote_mcp("http://example.com/graphql", graphql_http=False)

    client = server.remote_client
    with patch.object(client, "_raw_execute_request", AsyncMock()) as raw:
        await client._introspect_schema()

    raw.assert_not_awaited()
    assert client._array_fields_cache["User"]["friends"] is True
    assert client._array_fields_cache["User"]["name"] is False
    assert client._field_type_map["Query.user"] == "User"
