"""Ariadne → MCP tools, customized with the @mcp directive.

Exposes a small "users" API and uses @mcp to rename a tool
(getUserById → fetch_user), rename and describe an argument (userId → id),
hide an argument (debugToken), and hide a field (internalMetrics).

With schema-first Ariadne you declare and apply @mcp inline in your SDL type_defs.
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
