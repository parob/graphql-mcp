"""graphql-api → MCP tools, customized with the @mcp directive.

Exposes a small "users" API and uses @mcp to rename a tool
(get_user_by_id → fetch_user), rename and describe an argument (user_id → id),
hide an argument (debug_token), and hide a field (internal_metrics).

With graphql-api you apply @mcp directly: as a decorator on fields and inside
Annotated[...] on arguments (and pass directives=[mcp] to GraphQLAPI).
"""

from typing import Annotated, Optional

from graphql_api import GraphQLAPI, field

from graphql_mcp import GraphQLMCP, mcp

# Tiny in-memory "database".
_USERS = {"1": "Alice", "2": "Bob"}


class UsersAPI:

    @field
    def list_users(self) -> list[str]:
        """List all user names."""
        return list(_USERS.values())

    @field
    @mcp(name="fetch_user", description="Fetch a user by ID.")
    def get_user_by_id(
        self,
        user_id: Annotated[str, mcp(name="id", description="The user's unique ID.")],
        # Hidden from MCP, but still usable via the GraphQL API directly.
        debug_token: Annotated[str, mcp(hidden=True)] = "",
    ) -> Optional[str]:
        return _USERS.get(user_id)

    @field
    @mcp(hidden=True)
    def internal_metrics(self) -> str:
        """Internal diagnostics — hidden from MCP via @mcp(hidden=True)."""
        return "cpu=0.3"


api = GraphQLAPI(root_type=UsersAPI, directives=[mcp])
server = GraphQLMCP.from_api(api, graphql_http_kwargs={
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
    uvicorn.run(app, host="0.0.0.0", port=8010)
