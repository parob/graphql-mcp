"""Strawberry + @mcp — basic exposure, plus a WORKAROUND for @mcp.

⚠️  @mcp is NOT native to Strawberry. Strawberry builds its own GraphQL types
and does not carry the @mcp directive onto the underlying graphql-core AST, so
a plain Strawberry schema loses the directive metadata before graphql-mcp ever
sees it. Basic exposure (every field → an MCP tool) works out of the box; @mcp
customization requires one of the workarounds documented in the guide:
https://graphql-mcp.com/strawberry-graphene

Demonstrates, for the type-hint-based Strawberry library:
- Basic exposure (native): every Strawberry field becomes an MCP tool. If you
  don't need @mcp, just pass `strawberry.Schema(...)._schema` to GraphQLMCP.
- @mcp customization (WORKAROUND): rename/describe/hide fields and arguments
  via Strawberry's own `@schema_directive`, then round-trip through SDL.

The workaround shown here (Path A in the guide):

    1. Declare a `@strawberry.schema_directive` named `Mcp`.
    2. Attach it to fields/arguments via `directives=[...]`.
    3. Round-trip the schema through SDL: `build_schema(str(strawberry_schema))`.
       Strawberry prints the directive into the SDL, so graphql-core preserves
       it on the AST where graphql-mcp can read it.
    4. Copy the resolvers across — `build_schema` doesn't carry them.

Caveats: the resolver-copy step is required, and this only covers top-level
query/mutation resolvers. For less ceremony, `apply_mcp()` (Path B in the
guide) attaches the same config directly onto the graphql-core schema — see
library_graphene.py for that approach.
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
