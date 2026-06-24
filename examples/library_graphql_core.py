"""graphql-core → MCP tools, customized with the @mcp directive.

Exposes a small "users" API and uses @mcp to rename a tool
(getUserById → fetch_user), rename and describe an argument (userId → id),
hide an argument (debugToken), and hide a field (internalMetrics).

With graphql-core you declare and apply @mcp inline in your SDL.
"""

from graphql import build_schema

from graphql_mcp.server import GraphQLMCP

# Declare the @mcp directive, then use it inline in the schema.
SDL = """
directive @mcp(
    name: String
    description: String
    hidden: Boolean
) on FIELD_DEFINITION | ARGUMENT_DEFINITION

type Query {
    "List all user names."
    listUsers: [String!]!

    getUserById(
        userId: ID! @mcp(name: "id", description: "The user's unique ID.")
        debugToken: String = "" @mcp(hidden: true)
    ): String @mcp(name: "fetch_user", description: "Fetch a user by ID.")

    internalMetrics: String @mcp(hidden: true)
}
"""

_USERS = {"1": "Alice", "2": "Bob"}

schema = build_schema(SDL)

# Attach resolvers to the graphql-core schema.
schema.query_type.fields["listUsers"].resolve = (
    lambda root, info: list(_USERS.values())
)
schema.query_type.fields["getUserById"].resolve = (
    lambda root, info, userId, debugToken="": _USERS.get(userId)
)
schema.query_type.fields["internalMetrics"].resolve = (
    lambda root, info: "cpu=0.3"
)

server = GraphQLMCP(schema=schema, name="Users (graphql-core)", graphql_http_kwargs={
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
    uvicorn.run(app, host="0.0.0.0", port=8011)
