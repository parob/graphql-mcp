"""Graphene + @mcp — basic exposure, plus a WORKAROUND for @mcp.

⚠️  @mcp is NOT native to Graphene. Graphene can't express directives in
Python at all, so a plain Graphene schema carries no @mcp metadata for
graphql-mcp to read. Basic exposure (every field → an MCP tool) works out of
the box; @mcp customization requires the workaround below. See the guide:
https://graphql-mcp.com/strawberry-graphene

Demonstrates, for the code-first Graphene library:
- Basic exposure (native): every Query/Mutation field becomes an MCP tool. If
  you don't need @mcp, just pass `graphene.Schema(...).graphql_schema` to
  GraphQLMCP.
- @mcp customization (WORKAROUND): rename/describe/hide fields and arguments
  via `apply_mcp()` (Path B in the guide).

Why `apply_mcp` rather than an SDL round-trip? Printing-then-rebuilding the SDL
would drop Graphene's camelCase→snake_case argument mapping (`out_name`),
breaking resolvers. `apply_mcp` attaches the @mcp configuration directly onto
the existing graphql-core schema, keyed by `"Type.field"` / `"Type.field.arg"`,
so nothing is rebuilt and the mapping is preserved.

Caveat: `apply_mcp` config is private metadata — it shapes MCP exposure but is
invisible to GraphQL introspection and `str(schema)`. That's fine for MCP, but
don't rely on it being visible to other schema consumers.
"""

import graphene

from graphql_mcp import GraphQLMCP, apply_mcp

_USERS = {"1": "Alice", "2": "Bob"}


class Query(graphene.ObjectType):
    list_users = graphene.List(
        graphene.NonNull(graphene.String), required=True,
        description="List all user names.",
    )
    get_user_by_id = graphene.String(
        user_id=graphene.ID(required=True),
        debug_token=graphene.String(default_value=""),
    )
    internal_metrics = graphene.String()

    def resolve_list_users(root, info):
        return list(_USERS.values())

    def resolve_get_user_by_id(root, info, user_id, debug_token=""):
        return _USERS.get(user_id)

    def resolve_internal_metrics(root, info):
        return "cpu=0.3"


# Graphene exposes Python snake_case names as camelCase in the schema, so the
# apply_mcp paths use the GraphQL (camelCase) names.
schema = graphene.Schema(query=Query).graphql_schema
apply_mcp(
    schema,
    fields={
        "Query.getUserById": {"name": "fetch_user", "description": "Fetch a user by ID."},
        "Query.internalMetrics": {"hidden": True},
    },
    args={
        "Query.getUserById.userId": {"name": "id", "description": "The user's unique ID."},
        "Query.getUserById.debugToken": {"hidden": True},
    },
)

server = GraphQLMCP(schema=schema, name="Users (Graphene)", graphql_http_kwargs={
    "graphiql_example_query": """\
{
  listUsers

  # Exposed to MCP as the "fetch_user" tool, with arg "id".
  getUserById(userId: "1")
}""",
})
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8014)
