"""Remote API - wraps a public GraphQL API as MCP tools.

Demonstrates:
- GraphQLMCP.from_remote_url() to introspect and wrap any GraphQL endpoint
- Auto-generated MCP tools from a remote schema
- Read-only access (allow_mutations=False)

Uses the public Countries GraphQL API (https://countries.trevorblades.com).
"""

from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    "https://countries.trevorblades.com/graphql",
    allow_mutations=False,
)
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
