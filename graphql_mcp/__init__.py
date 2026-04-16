"""GraphQL MCP - Expose GraphQL schemas as MCP tools."""

from graphql import (
    DirectiveLocation,
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLString,
)

from graphql_mcp.overrides import apply_mcp
from graphql_mcp.server import GraphQLMCP

# Import SchemaDirective from graphql-api if available
try:
    from graphql_api.directives import SchemaDirective

    # Unified @mcp directive for customizing how fields and arguments
    # are exposed as MCP tools.
    mcp = SchemaDirective(
        name="mcp",
        locations=[
            DirectiveLocation.FIELD_DEFINITION,
            DirectiveLocation.ARGUMENT_DEFINITION,
        ],
        args={
            "name": GraphQLArgument(GraphQLString),
            "description": GraphQLArgument(GraphQLString),
            "hidden": GraphQLArgument(GraphQLBoolean),
            # MCP tool annotation hints (see spec). Defaults are inferred:
            # queries default to readOnly: true; mutations use spec defaults.
            "readOnly": GraphQLArgument(GraphQLBoolean),
            "destructive": GraphQLArgument(GraphQLBoolean),
            "idempotent": GraphQLArgument(GraphQLBoolean),
            "openWorld": GraphQLArgument(GraphQLBoolean),
        },
        description=(
            "Customize how this field or argument is exposed as an MCP tool. "
            "`name` / `description` override the MCP-exposed name and description; "
            "`hidden: true` skips MCP registration; "
            "`readOnly` / `destructive` / `idempotent` / `openWorld` set MCP tool "
            "annotation hints (`destructive` and `idempotent` are meaningful only "
            "when `readOnly: false`)."
        ),
    )
except ImportError:
    # graphql-api not installed - `mcp` won't be available as a directive builder
    mcp = None  # type: ignore

__all__ = ["GraphQLMCP", "apply_mcp", "mcp"]
