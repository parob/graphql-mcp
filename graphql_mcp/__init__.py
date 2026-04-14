"""GraphQL MCP - Expose GraphQL schemas as MCP tools."""

from graphql import (
    DirectiveLocation,
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLString,
)

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
        },
        description=(
            "Customize how this field or argument is exposed as an MCP tool. "
            "Use `name` to override the MCP-exposed name, `description` to override "
            "the MCP description, and `hidden: true` to skip the field or argument "
            "from MCP registration entirely."
        ),
    )
except ImportError:
    # graphql-api not installed - `mcp` won't be available as a directive builder
    mcp = None  # type: ignore

__all__ = ["GraphQLMCP", "mcp"]
