---
title: Authentication
weight: 3
---

# Authentication

GraphQL MCP supports various authentication methods to secure your MCP tools and GraphQL endpoints.

## Bearer Token Authentication

The simplest form of authentication uses bearer tokens:

```python
from graphql_mcp.server import GraphQLMCP

# Connect to authenticated API
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="your_bearer_token",
    name="Authenticated API"
)
```

## JWT Authentication

For more advanced use cases, you can use JWT authentication with a custom verifier:

```python
from graphql_mcp.server import GraphQLMCP
from your_auth_module import jwt_verifier

server = GraphQLMCP.from_api(
    api,
    name="Secure API",
    auth=jwt_verifier  # Custom JWT verification function
)
```

## Custom Headers

Pass custom authentication headers to remote APIs:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    headers={
        "Authorization": "Bearer token",
        "X-API-Key": "your_api_key",
        "X-Custom-Auth": "custom_value"
    },
    name="Custom Auth API"
)
```

## Authentication in MCP Inspector

When using the MCP Inspector with authentication enabled:

1. Navigate to your server in a web browser
2. Click on the "Authentication" tab
3. Enter your bearer token or credentials
4. Test your tools with authentication

The inspector will include your authentication headers in all tool calls.

## Best Practices

### Environment Variables

Store sensitive tokens in environment variables:

```python
import os
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url=os.environ["GRAPHQL_URL"],
    bearer_token=os.environ["GRAPHQL_TOKEN"],
    name="Secure API"
)
```

### Token Rotation

Implement token rotation for long-running services:

```python
import os
from datetime import datetime, timedelta

def get_fresh_token():
    # Your token refresh logic
    return os.environ["GRAPHQL_TOKEN"]

server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token=get_fresh_token(),
    name="API"
)
```

### Production Security

For production deployments:

1. Always use HTTPS
2. Store credentials securely (e.g., secrets manager)
3. Implement rate limiting
4. Use strong authentication (JWT preferred)
5. Validate and sanitize all inputs

## Next Steps

- Learn about [configuration options](configuration/)
- Explore [testing strategies](testing/)
- See [examples](examples/)
