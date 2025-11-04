---
title: "MCP Inspector"
weight: 4
---

# MCP Inspector

GraphQL MCP includes a built-in web-based inspector for testing and debugging your MCP tools.

![MCP Inspector Interface](../../mcp_inspector.png)

## What is the MCP Inspector?

The MCP Inspector is a GraphiQL-integrated interface that lets you:

- 🔍 **Discover Tools** - Browse all available MCP tools generated from your schema
- 🧪 **Test Tools** - Execute tools with custom parameters and see results
- 🔐 **Add Authentication** - Test with Bearer tokens, API keys, or custom headers
- 📊 **Track History** - Review previous tool executions
- 📄 **View Schemas** - Inspect parameter and output schemas for each tool
- ⚡ **Real-time Status** - Monitor connection status and availability

## Enabling the Inspector

Enable the inspector by setting `graphql_http=True` when creating your server:

```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI(root_type=MyAPI)

server = GraphQLMCP.from_api(
    api,
    name="My API",
    graphql_http=True  # This enables both GraphQL and MCP Inspector
)

app = server.http_app()
```

## Accessing the Inspector

Once your server is running, access the inspector by visiting your GraphQL endpoint in a web browser:

```
http://localhost:8000/graphql
```

The inspector interface will automatically appear alongside the GraphiQL interface.

## Using the Inspector

### 1. Discover Available Tools

The left panel shows all MCP tools generated from your GraphQL schema:

- Tool names (converted to snake_case)
- Tool descriptions from GraphQL docstrings
- Parameter information

### 2. Configure Authentication

If your API requires authentication, use the authentication panel:

```
Bearer Token: your_token_here
```

Or add custom headers:

```
X-API-Key: your_key
Authorization: Bearer token
```

### 3. Execute Tools

1. Select a tool from the list
2. Fill in the parameters (JSON format)
3. Click "Execute"
4. View the results in the output panel

Example parameters:

```json
{
  "name": "Alice",
  "age": 30
}
```

### 4. Review Call History

The inspector maintains a history of your tool calls:

- Timestamp of execution
- Tool name and parameters
- Results or errors
- Response time

Click on any previous call to:
- View the full request/response
- Re-execute with the same parameters
- Copy parameters for modification

### 5. Inspect Schemas

Click the schema icon next to any tool to view:

- **Input Schema** - Required and optional parameters with types
- **Output Schema** - Expected return type structure
- **Documentation** - Description from GraphQL schema

## Authentication Testing

The inspector supports various authentication methods:

### Bearer Tokens

```
Bearer Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API Keys

Add as custom header:

```
X-API-Key: your_api_key_here
```

### Custom Headers

Any additional headers your API requires:

```
X-Custom-Auth: value
X-Request-ID: 123
```

## Example Workflow

Here's a typical testing workflow with the inspector:

1. **Start Server** with inspector enabled
   ```python
   server = GraphQLMCP.from_api(api, graphql_http=True)
   app = server.http_app()
   ```

2. **Open Browser** to `http://localhost:8000/graphql`

3. **Browse Tools** in the inspector panel

4. **Add Authentication** if required

5. **Test a Query Tool**
   - Select `get_user`
   - Parameters: `{"id": "123"}`
   - Click Execute
   - View results

6. **Test a Mutation Tool**
   - Select `create_user`
   - Parameters: `{"name": "Alice", "email": "alice@example.com"}`
   - Click Execute
   - Verify creation

7. **Review History** to compare results

8. **Export Parameters** for use in your application

## Inspector vs GraphiQL

The inspector complements GraphiQL:

| Feature | GraphiQL | MCP Inspector |
|---------|----------|---------------|
| **Purpose** | Test GraphQL queries | Test MCP tools |
| **Input Format** | GraphQL query language | JSON parameters |
| **Schema View** | GraphQL SDL | MCP tool schemas |
| **History** | Query history | Tool call history |
| **Use Case** | GraphQL development | MCP integration testing |

You can use both simultaneously to test your API from both perspectives.

## Disabling in Production

For production deployments, disable the GraphQL HTTP endpoint:

```python
server = GraphQLMCP.from_api(
    api,
    graphql_http=False  # No GraphiQL or inspector in production
)
```

This removes both GraphiQL and the MCP Inspector, leaving only the MCP endpoints.

## Debugging Tips

### Tool Not Appearing

- Check that the field has a `@field` decorator
- Ensure the field has a docstring
- Verify mutations are enabled (`allow_mutations=True`)

### Authentication Errors

- Verify token format (include "Bearer " prefix if required)
- Check token hasn't expired
- Ensure auth configuration matches your API

### Type Errors

- Check parameter types match the schema
- Use proper JSON format for complex types
- Review the schema panel for expected types

### Connection Issues

- Verify server is running
- Check the correct port and path
- Look for CORS errors in browser console

## Next Steps

- **[Configuration](configuration/)** - Configure inspector behavior
- **[Examples](examples/)** - See inspector in real workflows
- **[API Reference](api-reference/)** - Learn about MCP tool APIs
