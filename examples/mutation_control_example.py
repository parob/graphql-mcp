#!/usr/bin/env python3
"""
Example demonstrating mutation control with allow_mutations parameter.

This example shows how to:
- Create servers with mutations enabled/disabled
- Use cases for read-only GraphQL MCP servers
- Security considerations when exposing GraphQL APIs
"""

import asyncio
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument
from graphql_mcp.server import GraphQLMCPServer
from fastmcp.client import Client


def create_blog_schema():
    """Create a sample blog GraphQL schema with queries and mutations."""
    
    # Define the schema with both queries and mutations
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "getPost": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString, description="Post ID")
                    },
                    description="Get a blog post by ID"
                ),
                "listPosts": GraphQLField(
                    GraphQLString,
                    description="List all blog posts"
                ),
                "getAuthor": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString, description="Author ID")
                    },
                    description="Get author information"
                )
            }
        ),
        mutation=GraphQLObjectType(
            "Mutation",
            fields={
                "createPost": GraphQLField(
                    GraphQLString,
                    args={
                        "title": GraphQLArgument(GraphQLString, description="Post title"),
                        "content": GraphQLArgument(GraphQLString, description="Post content"),
                        "authorId": GraphQLArgument(GraphQLString, description="Author ID")
                    },
                    description="Create a new blog post"
                ),
                "updatePost": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString, description="Post ID"),
                        "title": GraphQLArgument(GraphQLString, description="New title"),
                        "content": GraphQLArgument(GraphQLString, description="New content")
                    },
                    description="Update an existing blog post"
                ),
                "deletePost": GraphQLField(
                    GraphQLString,
                    args={
                        "id": GraphQLArgument(GraphQLString, description="Post ID to delete")
                    },
                    description="Delete a blog post"
                )
            }
        )
    )
    
    return schema


async def demo_mutations_enabled():
    """Demonstrate server with mutations enabled (default behavior)."""
    
    print("\n" + "="*50)
    print("DEMO 1: Mutations Enabled (Default)")
    print("="*50)
    
    schema = create_blog_schema()
    
    # Create server with mutations enabled (default)
    server = GraphQLMCPServer.from_schema(
        schema,
        allow_mutations=True,  # This is the default
        name="Full Blog API"
    )
    
    async with Client(server) as client:
        tools = await client.list_tools()
        
        print(f"Total tools available: {len(tools)}")
        print("\nAvailable tools:")
        for tool in tools:
            tool_type = "MUTATION" if any(mut in tool.name for mut in ["create", "update", "delete"]) else "QUERY"
            print(f"  - {tool.name:<15} ({tool_type}): {tool.description}")


async def demo_mutations_disabled():
    """Demonstrate server with mutations disabled for read-only access."""
    
    print("\n" + "="*50)
    print("DEMO 2: Mutations Disabled (Read-Only)")
    print("="*50)
    
    schema = create_blog_schema()
    
    # Create server with mutations disabled
    server = GraphQLMCPServer.from_schema(
        schema,
        allow_mutations=False,  # Disable mutations
        name="Read-Only Blog API"
    )
    
    async with Client(server) as client:
        tools = await client.list_tools()
        
        print(f"Total tools available: {len(tools)}")
        print("\nAvailable tools (read-only):")
        for tool in tools:
            print(f"  - {tool.name:<15} (QUERY): {tool.description}")


async def demo_remote_server_with_mutation_control():
    """Demonstrate remote server with mutation control."""
    
    print("\n" + "="*50)
    print("DEMO 3: Remote Server with Mutation Control")
    print("="*50)
    
    # Example configurations for different use cases
    
    # 1. Full access server (internal use)
    print("\n1. Internal Server (Full Access):")
    print("   - Used by admin tools and internal services")
    print("   - All mutations allowed")
    print("   Configuration:")
    print("   server = GraphQLMCPServer.from_remote_url(")
    print("       url='https://internal-api.company.com/graphql',")
    print("       bearer_token='internal-service-token',")
    print("       allow_mutations=True,  # Allow all operations")
    print("       name='Internal Blog API'")
    print("   )")
    
    # 2. Read-only server (external/public use)
    print("\n2. Public/External Server (Read-Only):")
    print("   - Used by public clients and external integrations")
    print("   - Only read operations allowed for security")
    print("   Configuration:")
    print("   server = GraphQLMCPServer.from_remote_url(")
    print("       url='https://api.company.com/graphql',")
    print("       bearer_token='public-api-token',")
    print("       allow_mutations=False,  # Read-only for security")
    print("       name='Public Blog API'")
    print("   )")
    
    # 3. Analytics/Reporting server (read-only)
    print("\n3. Analytics/Reporting Server (Read-Only):")
    print("   - Used for data analysis and reporting")
    print("   - No write operations needed")
    print("   Configuration:")
    print("   server = GraphQLMCPServer.from_remote_url(")
    print("       url='https://analytics-api.company.com/graphql',")
    print("       bearer_token='analytics-token',")
    print("       allow_mutations=False,  # Analytics doesn't need mutations")
    print("       name='Analytics API'")
    print("   )")


def print_security_considerations():
    """Print security considerations for mutation control."""
    
    print("\n" + "="*50)
    print("SECURITY CONSIDERATIONS")
    print("="*50)
    
    print("""
When to disable mutations (allow_mutations=False):

1. PUBLIC APIS:
   - Exposed to external clients or third parties
   - Prevents accidental or malicious data modification
   - Reduces attack surface

2. READ-ONLY SERVICES:
   - Analytics and reporting tools
   - Data exploration interfaces
   - Monitoring and observability tools

3. UNTRUSTED ENVIRONMENTS:
   - Development/staging environments with production data
   - Shared or multi-tenant environments
   - Client-side applications with limited trust

4. COMPLIANCE REQUIREMENTS:
   - Systems requiring audit trails for all write operations
   - Environments with strict data modification policies
   - Read-only replicas or backup systems

5. INTEGRATION SCENARIOS:
   - External system integrations that only need to read data
   - Webhook endpoints that process but don't modify data
   - Cache warming or pre-loading services

Benefits of mutation control:
- Enhanced security posture
- Clearer API intentions (read vs read/write)
- Reduced accidental data modification
- Easier compliance with data protection regulations
- Better separation of concerns in distributed systems
""")


async def demo_practical_use_cases():
    """Show practical use cases for mutation control."""
    
    print("\n" + "="*50)
    print("PRACTICAL USE CASES")
    print("="*50)
    
    schema = create_blog_schema()
    
    # Use Case 1: Content Management System
    print("\n1. Content Management System:")
    
    # Admin interface - full access
    admin_server = GraphQLMCPServer.from_schema(
        schema,
        allow_mutations=True,
        name="CMS Admin API"
    )
    
    # Public website - read-only
    public_server = GraphQLMCPServer.from_schema(
        schema,
        allow_mutations=False,
        name="Public Website API"
    )
    
    async with Client(admin_server) as admin_client:
        admin_tools = await admin_client.list_tools()
        print(f"   Admin tools: {len(admin_tools)} (includes create/update/delete)")
    
    async with Client(public_server) as public_client:
        public_tools = await public_client.list_tools()
        print(f"   Public tools: {len(public_tools)} (read-only)")
    
    # Use Case 2: Data Pipeline
    print("\n2. Data Pipeline:")
    print("   - ETL processes use read-only APIs to extract data")
    print("   - Prevents accidental modification during data processing")
    print("   - Ensures data integrity in pipeline operations")
    
    # Use Case 3: Multi-environment deployment
    print("\n3. Multi-environment Deployment:")
    print("   - Production: mutations enabled for applications")
    print("   - Staging: mutations disabled when using production data")
    print("   - Development: controlled mutation access")


async def main():
    """Run all demonstrations."""
    
    print("GraphQL MCP Mutation Control Examples")
    print("=" * 50)
    
    # Run demonstrations
    await demo_mutations_enabled()
    await demo_mutations_disabled()
    await demo_remote_server_with_mutation_control()
    
    print_security_considerations()
    
    await demo_practical_use_cases()
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print("""
The allow_mutations parameter provides fine-grained control over which
GraphQL operations are exposed as MCP tools:

• allow_mutations=True (default): Expose all queries and mutations
• allow_mutations=False: Expose only queries (read-only)

This feature enables:
- Enhanced security for public APIs
- Clear separation between read and write operations
- Compliance with data protection requirements
- Better control in multi-environment deployments

Use mutation control to create secure, purpose-built GraphQL MCP interfaces
that match your specific use case and security requirements.
""")


if __name__ == "__main__":
    asyncio.run(main())