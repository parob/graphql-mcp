"""Ariadne + @mcp — basic exposure and MCP customization.

Demonstrates, for the schema-first Ariadne library:
- Basic exposure: every Query/Mutation field becomes an MCP tool.
- The @mcp directive written directly in the SDL `type_defs`, which Ariadne
  preserves on the schema AST so graphql-mcp can read it:
    - rename a field's tool  (getUserById → fetch_user)
    - rename + describe an argument  (userId → id)
    - hide an argument from MCP  (debugToken)
    - hide a whole field from MCP  (internalMetrics)

Because Ariadne is schema-first, the @mcp directive works natively — just
declare it in your SDL and apply it inline. No rebuild step required.
"""

from ariadne import QueryType, make_executable_schema

from graphql_mcp.server import GraphQLMCP

type_defs = """
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

query = QueryType()


@query.field("listUsers")
def resolve_list_users(_, info):
    return list(_USERS.values())


@query.field("getUserById")
def resolve_get_user_by_id(_, info, userId, debugToken=""):
    return _USERS.get(userId)


@query.field("internalMetrics")
def resolve_internal_metrics(_, info):
    return "cpu=0.3"


schema = make_executable_schema(type_defs, query)
server = GraphQLMCP(schema=schema, name="Users (Ariadne)", graphql_http_kwargs={
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
    uvicorn.run(app, host="0.0.0.0", port=8012)
