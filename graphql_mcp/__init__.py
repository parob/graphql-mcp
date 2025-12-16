"""GraphQL MCP - Expose GraphQL schemas as MCP tools."""

from graphql import DirectiveLocation

from graphql_mcp.server import GraphQLMCP

# Import SchemaDirective from graphql-api if available
try:
    from graphql_api.directives import SchemaDirective

    # Define the mcp_hidden directive for marking arguments as hidden from MCP
    mcp_hidden = SchemaDirective(
        name="mcpHidden",
        locations=[DirectiveLocation.ARGUMENT_DEFINITION],
        description="Marks an argument as hidden from MCP tools. "
                    "The argument remains visible in the GraphQL schema but "
                    "will not be exposed as an MCP tool parameter."
    )
except ImportError:
    # graphql-api not installed - mcp_hidden won't be available as a directive
    mcp_hidden = None  # type: ignore

__all__ = ["GraphQLMCP", "mcp_hidden"]
