---
title: "Deployment"
---

# Deployment

Production configuration and deployment patterns for GraphQL MCP servers.

## Production Settings

```python
import uvicorn
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_api(
    api,
    name="Production API",
    graphql_http=False,  # Disable GraphiQL in production
    allow_mutations=True,
    auth=jwt_verifier    # Always use authentication
)

app = server.http_app(
    transport="streamable-http",
    stateless_http=True  # Required for load balancing
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="info"
    )
```

Key settings:
- **`graphql_http=False`** — Disable GraphiQL and MCP Inspector in production
- **`stateless_http=True`** — No session state, safe for multiple workers and load balancers
- **`transport="streamable-http"`** — HTTP with streaming support

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
```

requirements.txt:

```txt
graphql-mcp
graphql-api
uvicorn
```

Build and run:

```bash
docker build -t graphql-mcp-server .
docker run -p 8000:8000 \
  -e GRAPHQL_URL=https://api.example.com/graphql \
  -e GRAPHQL_TOKEN=your_token \
  graphql-mcp-server
```

## Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: graphql-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: graphql-mcp
  template:
    metadata:
      labels:
        app: graphql-mcp
    spec:
      containers:
      - name: graphql-mcp
        image: your-registry/graphql-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: GRAPHQL_URL
          valueFrom:
            secretKeyRef:
              name: graphql-secrets
              key: url
        - name: GRAPHQL_TOKEN
          valueFrom:
            secretKeyRef:
              name: graphql-secrets
              key: token
---
apiVersion: v1
kind: Service
metadata:
  name: graphql-mcp
spec:
  selector:
    app: graphql-mcp
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

Use `stateless_http=True` in your server code when running with multiple replicas.

## Serverless (AWS Lambda)

Deploy to AWS Lambda using [Mangum](https://mangum.io/):

```python
from mangum import Mangum
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_api(api, name="Lambda API")
app = server.http_app(stateless_http=True)

handler = Mangum(app)
```

## Next Steps

- **[Customization](/customization)** — Auth, middleware, lifespan management
- **[API Reference](/api-reference)** — Full `http_app` parameter reference
