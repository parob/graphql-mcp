#!/usr/bin/env python3
"""
Example of using graphql-mcp with a remote GraphQL server.

This example shows how to create an MCP server that connects to a remote
GraphQL endpoint and exposes its operations as MCP tools.
"""

import asyncio
from graphql_mcp.server import GraphQLMCPServer


async def main():
    # Example 1: Connect to a public GraphQL API (SpaceX API)
    spacex_server = GraphQLMCPServer.from_remote_url(
        url="https://spacex-production.up.railway.app/",
        name="SpaceX GraphQL API"
    )
    
    # The server can now be used as any other MCP server
    # It will have tools for all queries and mutations from the remote schema
    
    # Example 2: Connect to a GraphQL API with bearer token authentication
    authenticated_server = GraphQLMCPServer.from_remote_url(
        url="https://api.example.com/graphql",
        bearer_token="YOUR_BEARER_TOKEN",  # Simple bearer token auth
        timeout=60,  # Increase timeout for slower endpoints
        name="Authenticated API"
    )
    
    # Example 3: Bearer token with additional headers
    multi_auth_server = GraphQLMCPServer.from_remote_url(
        url="https://api.example.com/graphql",
        bearer_token="YOUR_BEARER_TOKEN",
        headers={
            "X-API-Key": "YOUR_API_KEY",
            "X-Client-Version": "1.0.0"
        },
        timeout=60,
        name="Multi-Auth API"
    )
    
    # Example 4: Read-only server for security
    readonly_server = GraphQLMCPServer.from_remote_url(
        url="https://api.github.com/graphql",
        bearer_token="YOUR_GITHUB_TOKEN",
        allow_mutations=False,  # Only queries, no mutations
        name="Read-Only GitHub API"
    )
    
    # Example 5: Using the server with FastMCP's built-in features
    # You can run it as an HTTP server
    app = spacex_server.http_app()
    
    # Or use it programmatically
    from fastmcp.client import Client
    
    async with Client(spacex_server) as client:
        # List available tools (queries and mutations from the remote schema)
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Example: Call a tool (this would execute against the remote server)
        # Note: Actual tool names depend on the remote schema
        # result = await client.call_tool("launches_past", {"limit": 5})
        # print(f"Result: {result}")


def run_http_server():
    """Run as an HTTP MCP server."""
    import uvicorn
    
    # Create server from remote URL
    server = GraphQLMCPServer.from_remote_url(
        url="https://countries.trevorblades.com/",  # Public countries API
        name="Countries GraphQL"
    )
    
    # Get the HTTP app
    app = server.http_app()
    
    # Run with uvicorn
    print("Starting MCP server for remote GraphQL endpoint...")
    print("The server will expose all queries/mutations from the remote schema as MCP tools")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    # Uncomment one of the following:
    
    # Run the async example
    asyncio.run(main())
    
    # Or run as HTTP server
    # run_http_server()