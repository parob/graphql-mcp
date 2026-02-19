---
title: GraphQL MCP
description: Turn your GraphQL API into AI-ready tools. Every query becomes a read tool, every mutation becomes a write tool.
layout: home
hero:
  name: GraphQL MCP
  text: Turn your GraphQL API into AI-ready tools
  tagline: Every query becomes a read tool. Every mutation becomes a write tool. Claude, ChatGPT, Cursor, and any MCP client can call them instantly.
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: API Reference
      link: /api-reference
---

MCP (Model Context Protocol) lets AI agents call external tools. GraphQL MCP reads your schema and generates those tools automatically — no boilerplate, no manual definitions.

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

## Set up in 3 lines

<div class="media-frame">

```python
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_api(api, name="Task Manager")
app = server.http_app()
```

Or connect to any remote GraphQL endpoint:

```python
server = GraphQLMCP.from_remote_url("https://api.example.com/graphql")
app = server.http_app()
```

</div>

## Works with

<p>
<span class="note-chip">Strawberry</span>
<span class="note-chip">Ariadne</span>
<span class="note-chip">Graphene</span>
<span class="note-chip">graphql-api</span>
<span class="note-chip">Any graphql-core schema</span>
<span class="note-chip">Remote GraphQL endpoints</span>
</p>

<div class="hero-grid">

<a class="hero-card" href="/local-apis">
<h3>Local APIs</h3>
<p>Use graphql-mcp with your own GraphQL schema — Strawberry, Ariadne, Graphene, or graphql-api.</p>
</a>

<a class="hero-card" href="/remote-apis">
<h3>Remote APIs</h3>
<p>Connect to GitHub, Shopify, Hasura, or any existing GraphQL endpoint.</p>
</a>

<a class="hero-card" href="/customization">
<h3>Customization</h3>
<p>mcp_hidden, auth, mutations, middleware — configure how tools are generated and served.</p>
</a>

<a class="hero-card" href="/testing">
<h3>Testing</h3>
<p>Built-in MCP Inspector for browsing, testing, and debugging your tools in the browser.</p>
</a>

</div>
