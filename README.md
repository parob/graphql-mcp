# graphql-mcp

A library for automatically generating [FastMCP](https://pypi.org/project/fastmcp/) tools from a GraphQL schema.

This allows you to expose your GraphQL API as a set of tools that can be used by other systems, such as AI agents or other services that understand the MCP (Multi-Model-Protocol).

## Features

- **Automatic Tool Generation**: Converts GraphQL queries and mutations into callable Python functions.
- **Type-Safe**: Maps GraphQL scalar types, enums, and input objects to corresponding Python types.
- **`FastMCP` Integration**: Seamlessly adds the generated functions as tools to a `FastMCP` server instance.
- **Modern GraphQL Libraries**: Works with modern, code-first GraphQL libraries like `strawberry-graphql`.
- **Asynchronous Support**: While the tool generation is synchronous, the created tools execute GraphQL queries in a way that can be integrated into asynchronous applications.
- **Remote GraphQL Server Support**: Connect to any remote GraphQL endpoint and automatically generate MCP tools from its schema.
- **Bearer Token Authentication**: Built-in support for bearer token authentication with automatic token refresh capability.
- **Flexible Authentication**: Combine bearer tokens with additional headers for complex authentication scenarios.
- **Bearer Token Forwarding**: Forward MCP client bearer tokens to remote GraphQL servers for seamless authentication.
- **SSL/TLS Configuration**: Configurable SSL certificate verification for development and production environments.
- **Mutation Control**: Optionally disable mutations to create read-only tool interfaces for enhanced security.
- **Advanced Enum Handling**: Intelligent conversion between GraphQL enum names and values with nested structure support.
- **Nested Query Tools**: Automatic generation of MCP tools for nested GraphQL field chains with argument support.
- **Schema Introspection**: Automatic schema analysis for type-aware transformations and validation.
- **Variable Cleaning**: Smart handling of undefined variables and automatic query optimization.
- **Debug Mode**: Comprehensive logging and debugging capabilities for request/response analysis.

## Installation

You can install `graphql-mcp` using pip. To follow the usage example, you'll also need `strawberry-graphql`:

```bash
pip install graphql-mcp "strawberry-graphql[cli]"
```

## Usage with Strawberry

Here's a simple example of how to use `graphql-mcp` to create tools from a `strawberry-graphql` schema.

```python
# example.py
import asyncio
import strawberry
from fastmcp import FastMCP
from graphql_mcp.server import add_tools_from_schema

# 1. Define your GraphQL schema using Strawberry
@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        """Returns a greeting."""
        return f"Hello, {name}!"

@strawberry.type
class Mutation:
    @strawberry.mutation
    def send_message(self, message: str) -> str:
        """Prints a message and returns a confirmation."""
        print(f"Received message: {message}")
        return f"Message '{message}' sent successfully."

# The strawberry.Schema object is compatible with graphql-core's GraphQLSchema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# 2. Create a FastMCP server instance
server = FastMCP(name="MyGraphQLServer")

# 3. Add tools from the schema
# The `strawberry.Schema` object can be passed directly.
add_tools_from_schema(schema, server)

# 4. Use the generated tools
async def main():
    # You can inspect the tools
    print("Available tools:", server.get_tool_names())

    # You can also inspect a specific tool's signature
    print("Tool 'hello' signature:", server.get_tool_signature("hello"))

    # Call a query tool
    result = await server.acall_tool("hello", name="Bob")
    print("Query result:", result)

    # Call a mutation tool
    result = await server.acall_tool("send_message", message="This is a test")
    print("Mutation result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

When you run this script, you will see the following output:

```
Available tools: ['send_message', 'hello']
Tool 'hello' signature: (name: str = 'World') -> str
Query result: Hello, Bob!
Received message: This is a test
Mutation result: Message 'This is a test' sent successfully.
```

## Alternative Usage: `GraphQLMCP`

For convenience, you can also use the `GraphQLMCP` class, which inherits from `FastMCP` and provides class methods to create a server directly from a schema.

### From a `GraphQLSchema` object

You can use `GraphQLMCP.from_schema()` and pass any `graphql-core`-compatible `GraphQLSchema` object. This includes schemas created with `strawberry-graphql`.

### From a Remote GraphQL Server

You can connect to a remote GraphQL endpoint and automatically generate MCP tools from its schema:

```python
# example_remote_server.py
import asyncio
from graphql_mcp.server import GraphQLMCP
from fastmcp.client import Client

# Connect to a remote GraphQL server
server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",  # Public GraphQL API
    name="Countries API"
)

# With bearer token authentication
authenticated_server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="YOUR_BEARER_TOKEN",  # Bearer token authentication
    timeout=60,  # Custom timeout in seconds
    name="Private API"
)

# With bearer token and additional headers
multi_auth_server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="YOUR_BEARER_TOKEN",
    headers={
        "X-API-Key": "YOUR_API_KEY",
        "X-Request-ID": "request-123"
    },
    timeout=60,
    name="Multi-Auth API"
)

# With bearer token forwarding from MCP client
forwarding_server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    forward_bearer_token=True,  # Forward MCP client token to remote server
    timeout=60,
    name="Token Forwarding API"
)

# With SSL verification disabled (for development)
dev_server = GraphQLMCP.from_remote_url(
    url="https://localhost:8000/graphql",
    verify_ssl=False,  # Disable SSL verification
    debug=True,  # Enable debug logging
    name="Development API"
)

# With advanced configuration
advanced_server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="YOUR_BEARER_TOKEN",
    undefined_strategy="remove",  # or "null" - how to handle undefined variables
    debug=True,  # Enable verbose logging
    timeout=30,
    name="Advanced API"
)

# Read-only server (queries only, no mutations)
readonly_server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="YOUR_BEARER_TOKEN",
    allow_mutations=False,  # Disable mutations for security
    name="Read-Only API"
)

# Use the server - all queries/mutations from the remote schema are now MCP tools
async def main():
    async with Client(server) as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")

        # Call a tool (executes against the remote server)
        # The actual tool names depend on the remote schema
        # result = await client.call_tool("countries", {"filter": {"currency": {"eq": "USD"}}})

if __name__ == "__main__":
    asyncio.run(main())
```

```python
# example_from_schema.py
import asyncio
import strawberry
from graphql_mcp.server import GraphQLMCP

# 1. Define your schema (e.g., with Strawberry)
@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

schema = strawberry.Schema(query=Query)

# 2. Create the server from the schema
server = GraphQLMCP.from_schema(schema, name="MyGraphQLServer")

# 3. Create a read-only server (queries only)
readonly_server = GraphQLMCP.from_schema(
    schema,
    allow_mutations=False,  # Disable mutations
    name="ReadOnlyGraphQLServer"
)

# 4. Use the server
async def main():
    print("Available tools:", server.get_tool_names())
    result = await server.acall_tool("hello", name="From Schema")
    print("Query result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

### From a `graphql-api` object

If you are using the `graphql-api` library, you can use the `GraphQLMCP.from_api()` method.

```python
# example_from_api.py
import asyncio
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP, HAS_GRAPHQL_API

# The .from_graphql_api() method is only available if `graphql-api` is installed.
if HAS_GRAPHQL_API:
    # 1. Define your API using `graphql-api`
    class MyAPI:
        @field
        def hello(self, name: str = "World") -> str:
            return f"Hello, {name}!"

    api = GraphQLAPI(roottype=MyAPI)

    # 2. Create the server from the API object
    server = GraphQLMCP.from_graphql_api(api)

    # 3. Use the server
    async def main():
        print("Available tools:", server.get_tool_names())
        result = await server.acall_tool("hello", name="From API")
        print("Query result:", result)

    if __name__ == "__main__":
        asyncio.run(main())
```

## Advanced Features

### Bearer Token Forwarding

When using `forward_bearer_token=True`, the server will automatically forward the MCP client's bearer token to the remote GraphQL server. This enables seamless authentication chains where the MCP client's credentials are passed through to the backend GraphQL API.

```python
# The MCP client's bearer token will be forwarded to the remote GraphQL server
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    forward_bearer_token=True,
    name="Forwarding Server"
)
```

**Security Note**: Only enable bearer token forwarding when you trust the remote GraphQL server with your MCP client's credentials.

### Undefined Variable Handling

GraphQL-MCP provides sophisticated handling of undefined variables through the `undefined_strategy` parameter:

- `"remove"` (default): Removes undefined variables from the query and variable declarations
- `"null"`: Converts undefined values to null

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    undefined_strategy="remove",  # Clean undefined variables
    name="Clean Variables Server"
)
```

### Debug Mode

Enable comprehensive logging to troubleshoot GraphQL requests and responses:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    debug=True,  # Enable verbose logging
    name="Debug Server"
)
```

### SSL Configuration

For development or internal APIs, you can disable SSL certificate verification:

```python
server = GraphQLMCP.from_remote_url(
    url="https://localhost:8000/graphql",
    verify_ssl=False,  # Only for development!
    name="Local Development Server"
)
```

### Nested Query Tools

GraphQL-MCP automatically generates MCP tools for nested GraphQL field chains. For example, if your schema has:

```graphql
type Query {
  user(id: ID!): User
}

type User {
  profile: Profile
}

type Profile {
  settings(category: String): Settings
}
```

The following MCP tools will be generated:
- `user` - Gets a user by ID
- `user_profile` - Gets a user's profile
- `user_profile_settings` - Gets profile settings with optional category filter

### Enum Handling

GraphQL-MCP intelligently handles GraphQL enums:
- **Input**: Accepts both enum values and names as input
- **Output**: Returns enum values for MCP compatibility
- **Schema**: Shows only enum values in MCP tool schemas (Pydantic-compatible)
- **Nested**: Handles enums in complex nested structures and arrays

## How It Works

`graphql-mcp` introspects your GraphQL schema's queries and mutations. For each field, it does the following:

1.  **Creates a Python Function**: A wrapper function is generated that has a signature matching the GraphQL field's arguments.
2.  **Handles Type Conversion**: It maps GraphQL types like `String`, `Int`, `ID`, and custom `Enum` types to their Python equivalents. Input objects are treated as dictionaries.
3.  **Constructs a GraphQL Query**: When the generated function is called, it dynamically constructs the appropriate GraphQL query or mutation string.
4.  **Executes the Query**: It uses `graphql-sync` to execute the query against the schema, passing in the provided arguments as variables.
5.  **Returns the Result**: The data from the GraphQL response is returned.

The tool names are converted from `camelCase` (GraphQL convention) to `snake_case` (Python convention). For example, a mutation `sendMessage` becomes a tool named `send_message`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.