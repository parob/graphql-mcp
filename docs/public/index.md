---
title: GraphQL MCP
description: A Python package that turns any GraphQL API into AI-ready MCP tools. Every query becomes a read tool, every mutation becomes a write tool.
layout: home
hero:
  name: GraphQL MCP
  text: Turn any GraphQL schema into MCP tools
  tagline: A Python package that reads your schema and generates AI-ready tools automatically. Every query becomes a read tool. Every mutation becomes a write tool.
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: Live Examples
      link: https://examples.graphql-mcp.com
---

Install graphql-mcp, point it at a graphql-core schema or a remote endpoint, and get a running MCP server. Works with Strawberry, Ariadne, Graphene, graphql-api, or any GraphQL API over HTTP.

## Your schema becomes AI tools

<div class="before-after">
<div class="media-frame">

**Your GraphQL schema**

```graphql
type Query {
  tasks(status: Status, priority: Priority): [Task!]!
  task(id: UUID!): Task
}

type Mutation {
  createTask(title: String!, priority: Priority): Task!
  deleteTask(id: UUID!): Boolean!
}

enum Status { TODO, IN_PROGRESS, DONE }
enum Priority { LOW, MEDIUM, HIGH, CRITICAL }
```

</div>
<div class="media-frame">

**Generated MCP tools**

```text
tasks(status?, priority?) → [Task]
  List all tasks, filtered by status or priority.

task(id) → Task
  Get a single task by ID.

create_task(title, priority?) → Task
  Create a new task.

delete_task(id) → bool
  Delete a task by ID.
```

Types, descriptions, enums, and optionality are all preserved automatically.

</div>
</div>

## Wrap a Python schema

Import your existing Python GraphQL schema and serve it as MCP tools directly — no network hop, no separate server. graphql-mcp reads the graphql-core schema object and generates tools in the same process.

```python
from graphql_mcp import GraphQLMCP

api = ...  # your Python GraphQL schema
server = GraphQLMCP.from_api(api, name="My API")
app = server.http_app()
```

Compatible with any library that produces a graphql-core schema: Strawberry, Ariadne, Graphene, graphql-api.

<a href="/python-libraries">Python library guide &rarr;</a>

## Proxy a remote GraphQL API

Point at any GraphQL endpoint — in any language, on any host — and graphql-mcp introspects the schema over HTTP and generates tools automatically. Queries and mutations are forwarded to the remote server at call time.

```python
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    "https://api.example.com/graphql"
)
app = server.http_app()
```

Requires the remote API to have introspection enabled.

<a href="/existing-apis">Remote API guide &rarr;</a>

<div class="hero-grid">

<a class="hero-card" href="/getting-started">
<h3>Getting Started</h3>
<p>Install, run your first server, open the MCP Inspector.</p>
</a>

<a class="hero-card" href="/python-libraries">
<h3>Python Libraries</h3>
<p>Setup guides for Strawberry, Ariadne, Graphene, and graphql-api.</p>
</a>

<a class="hero-card" href="/existing-apis">
<h3>Remote APIs</h3>
<p>Connect to GitHub, Shopify, Hasura, or any GraphQL endpoint.</p>
</a>

<a class="hero-card" href="/configuration">
<h3>Configuration</h3>
<p>Transports, authentication, mcp_hidden, mutations, middleware.</p>
</a>

</div>
