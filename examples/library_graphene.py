"""Graphene → MCP tools, customized with the @mcp directive.

Exposes a small "users" API and uses @mcp to rename a tool
(get_user_by_id → fetch_user), rename and describe an argument (user_id → id),
hide an argument (debug_token), and hide a field (internal_metrics).

Note: with Graphene you apply @mcp via `apply_mcp()`, which attaches the config
to the graphql-core schema directly (keyed by "Type.field" / "Type.field.arg").
More in the Strawberry & Graphene guide: https://graphql-mcp.com/strawberry-graphene
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
