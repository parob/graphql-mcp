"""Graphene + @mcp — basic exposure and MCP customization.

Demonstrates, for the code-first Graphene library:
- Basic exposure: every Query/Mutation field becomes an MCP tool. If you don't
  need @mcp customization, just pass `graphene.Schema(...).graphql_schema`
  straight to GraphQLMCP.
- The @mcp directive applied programmatically with `apply_mcp`, because
  Graphene has no native directive support:
    - rename a field's tool  (getUserById → fetch_user)
    - rename + describe an argument  (userId → id)
    - hide an argument from MCP  (debugToken)
    - hide a whole field from MCP  (internalMetrics)

Graphene can't express directives in Python, and printing-then-rebuilding the
SDL would drop Graphene's camelCase→snake_case argument mapping. `apply_mcp`
avoids both problems: it attaches the @mcp configuration directly onto the
existing graphql-core schema, keyed by `"Type.field"` / `"Type.field.arg"`.
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
