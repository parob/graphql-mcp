"""Strawberry → MCP tools, customized with the @mcp directive.

Exposes a small "users" API and uses @mcp to rename a tool
(get_user_by_id → fetch_user), rename and describe an argument (user_id → id),
hide an argument (debug_token), and hide a field (internal_metrics).

Note: with Strawberry you declare @mcp as a `@strawberry.schema_directive` and
round-trip the schema through SDL (`build_schema(str(schema))`) so the directive
reaches the graphql-core AST, then copy resolvers across. Other approaches (e.g.
`apply_mcp()`) are in the Strawberry & Graphene guide:
https://graphql-mcp.com/strawberry-graphene
"""

from typing import Annotated, Optional

import strawberry
from strawberry.schema_directive import Location

from graphql import GraphQLSchema, build_schema

from graphql_mcp.server import GraphQLMCP


@strawberry.schema_directive(
    locations=[Location.FIELD_DEFINITION, Location.ARGUMENT_DEFINITION]
)
class Mcp:
    name: str = ""
    description: str = ""
    hidden: bool = False


_USERS = {"1": "Alice", "2": "Bob"}


@strawberry.type
class Query:

    @strawberry.field
    def list_users(self) -> list[str]:
        """List all user names."""
        return list(_USERS.values())

    @strawberry.field(
        directives=[Mcp(name="fetch_user", description="Fetch a user by ID.")]
    )
    def get_user_by_id(
        self,
        user_id: Annotated[
            str,
            strawberry.argument(
                directives=[Mcp(name="id", description="The user's unique ID.")]
            ),
        ],
        debug_token: Annotated[
            str, strawberry.argument(directives=[Mcp(hidden=True)])
        ] = "",
    ) -> Optional[str]:
        return _USERS.get(user_id)

    @strawberry.field(directives=[Mcp(hidden=True)])
    def internal_metrics(self) -> str:
        return "cpu=0.3"


def to_core_schema(strawberry_schema: strawberry.Schema) -> GraphQLSchema:
    """Round-trip a Strawberry schema to graphql-core, preserving @mcp.

    `str(strawberry_schema)` emits the directive definitions and applications,
    so rebuilding from that SDL keeps them on the AST. Resolvers don't survive
    SDL printing, so copy them back across by field name.
    """
    rebuilt = build_schema(str(strawberry_schema))
    for type_name in ("query_type", "mutation_type"):
        src = getattr(strawberry_schema._schema, type_name)
        dst = getattr(rebuilt, type_name)
        if src is None or dst is None:
            continue
        for field_name, src_field in src.fields.items():
            if field_name in dst.fields:
                dst.fields[field_name].resolve = src_field.resolve
    return rebuilt


schema = to_core_schema(strawberry.Schema(query=Query))
server = GraphQLMCP(schema=schema, name="Users (Strawberry)", graphql_http_kwargs={
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
    uvicorn.run(app, host="0.0.0.0", port=8013)
