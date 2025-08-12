#!/usr/bin/env python3
"""
Example of using bearer token authentication with graphql-mcp.

This example shows various authentication scenarios including:
- Simple bearer token authentication
- Bearer token with additional headers
- Token refresh callback for automatic token renewal
"""

import asyncio
import os
from datetime import datetime, timedelta
from graphql_mcp.server import GraphQLMCPServer
from graphql_mcp.remote import RemoteGraphQLClient
from fastmcp.client import Client


# Example 1: Simple Bearer Token Authentication
def example_simple_bearer_token():
    """Create a server with simple bearer token authentication."""
    
    # Get token from environment variable or configuration
    bearer_token = os.getenv("GRAPHQL_API_TOKEN", "your-bearer-token-here")
    
    server = GraphQLMCPServer.from_remote_url(
        url="https://api.github.com/graphql",  # GitHub GraphQL API
        bearer_token=bearer_token,
        name="GitHub GraphQL"
    )
    
    return server


# Example 2: Bearer Token with Additional Headers
def example_bearer_with_headers():
    """Create a server with bearer token and additional headers."""
    
    bearer_token = os.getenv("API_BEARER_TOKEN")
    api_key = os.getenv("API_KEY")
    
    server = GraphQLMCPServer.from_remote_url(
        url="https://api.example.com/graphql",
        bearer_token=bearer_token,
        headers={
            "X-API-Key": api_key,
            "X-Client-ID": "mcp-client-v1",
            "X-Request-ID": f"req-{datetime.now().isoformat()}"
        },
        timeout=30,
        name="Multi-Auth API"
    )
    
    return server


# Example 3: Token Refresh Callback
class TokenManager:
    """Manages bearer tokens with automatic refresh."""
    
    def __init__(self, initial_token: str, refresh_url: str = None):
        self.current_token = initial_token
        self.refresh_url = refresh_url
        self.token_expiry = datetime.now() + timedelta(hours=1)
    
    def get_fresh_token(self) -> str:
        """
        Get a fresh token, refreshing if necessary.
        
        In a real implementation, this would:
        1. Check if the current token is expired
        2. Call the refresh endpoint if needed
        3. Update the current token
        4. Return the fresh token
        """
        if datetime.now() >= self.token_expiry:
            # In production, you would call your refresh endpoint here
            # For example:
            # response = requests.post(self.refresh_url, ...)
            # self.current_token = response.json()["access_token"]
            # self.token_expiry = datetime.now() + timedelta(hours=1)
            
            # For demo purposes, we'll just simulate a refresh
            print("Token expired, refreshing...")
            self.current_token = f"refreshed-token-{datetime.now().timestamp()}"
            self.token_expiry = datetime.now() + timedelta(hours=1)
        
        return self.current_token


async def example_with_token_refresh():
    """Create a client with automatic token refresh capability."""
    
    # Initialize token manager
    token_manager = TokenManager(
        initial_token=os.getenv("INITIAL_TOKEN", "initial-bearer-token"),
        refresh_url="https://auth.example.com/refresh"
    )
    
    # Create a client with token refresh callback
    client = RemoteGraphQLClient(
        url="https://api.example.com/graphql",
        bearer_token=token_manager.current_token,
        token_refresh_callback=token_manager.get_fresh_token,
        timeout=30
    )
    
    # Execute queries - token will be automatically refreshed if needed
    async with client:
        result = await client.execute("""
            query GetUserData {
                viewer {
                    login
                    name
                    email
                }
            }
        """)
        print(f"User data: {result}")


# Example 4: Using with Real APIs
async def example_github_graphql():
    """Example using GitHub's GraphQL API with bearer token."""
    
    # You need to create a personal access token at:
    # https://github.com/settings/tokens
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        print("Please set GITHUB_TOKEN environment variable")
        print("Create a token at: https://github.com/settings/tokens")
        return
    
    server = GraphQLMCPServer.from_remote_url(
        url="https://api.github.com/graphql",
        bearer_token=github_token,
        name="GitHub API"
    )
    
    async with Client(server) as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available GitHub GraphQL tools: {len(tools)}")
        
        # Example: Get viewer information
        if "viewer" in [tool.name for tool in tools]:
            result = await client.call_tool("viewer")
            print(f"Viewer info: {result}")


# Example 5: Environment-based Configuration
def create_server_from_env():
    """
    Create a server using environment variables for configuration.
    
    This is a best practice for production deployments.
    """
    
    # Read configuration from environment
    graphql_url = os.getenv("GRAPHQL_ENDPOINT", "https://api.example.com/graphql")
    bearer_token = os.getenv("GRAPHQL_BEARER_TOKEN")
    api_key = os.getenv("GRAPHQL_API_KEY")
    timeout = int(os.getenv("GRAPHQL_TIMEOUT", "30"))
    
    # Build headers dictionary
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    
    # Add any additional headers from environment
    for key, value in os.environ.items():
        if key.startswith("GRAPHQL_HEADER_"):
            header_name = key.replace("GRAPHQL_HEADER_", "").replace("_", "-")
            headers[header_name] = value
    
    # Create the server
    server = GraphQLMCPServer.from_remote_url(
        url=graphql_url,
        bearer_token=bearer_token,
        headers=headers if headers else None,
        timeout=timeout,
        name="Configured API"
    )
    
    return server


async def main():
    """Run examples."""
    
    print("GraphQL MCP Bearer Token Examples")
    print("=" * 40)
    
    # Example 1: Simple bearer token
    print("\n1. Simple Bearer Token:")
    server1 = example_simple_bearer_token()
    print(f"   Created server: {server1}")
    
    # Example 2: Bearer token with headers
    print("\n2. Bearer Token with Additional Headers:")
    server2 = example_bearer_with_headers()
    print(f"   Created server: {server2}")
    
    # Example 3: Token refresh
    print("\n3. Token Refresh Example:")
    # await example_with_token_refresh()
    print("   (Skipped - requires actual API)")
    
    # Example 4: GitHub API (if token is available)
    print("\n4. GitHub GraphQL API:")
    if os.getenv("GITHUB_TOKEN"):
        await example_github_graphql()
    else:
        print("   (Skipped - GITHUB_TOKEN not set)")
    
    # Example 5: Environment-based configuration
    print("\n5. Environment-based Configuration:")
    server5 = create_server_from_env()
    print(f"   Created server from environment: {server5}")


if __name__ == "__main__":
    asyncio.run(main())