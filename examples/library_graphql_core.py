"""graphql-core + @mcp — basic exposure and MCP customization.

Demonstrates, for the reference graphql-core library:
- Basic exposure: every Query/Mutation field becomes an MCP tool.
- The @mcp directive written directly in SDL, which graphql-core preserves on
  the schema AST so graphql-mcp can read it:
    - rename a field's tool  (getUserById → fetch_user)
    - rename + describe an argument  (userId → id)
    - hide an argument from MCP  (debugToken)
    - hide a whole field from MCP  (internalMetrics)

Because graphql-core is the common denominator every other library compiles
down to, the @mcp directive "just works" here with no rebuild step — you only
need to declare the directive in your SDL.
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
