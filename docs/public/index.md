---
title: GraphQL MCP
description: Instantly expose any GraphQL API as MCP tools for AI agents and LLMs.
layout: home
hero:
  name: GraphQL MCP
  text: Any GraphQL API → MCP Tools
  tagline: Expose your GraphQL queries and mutations as MCP tools for AI agents. Works with Strawberry, Ariadne, Graphene, graphql-api, or any remote endpoint.
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: API Reference
      link: /api-reference
---

## How it works

<div class="arch-flow">
  <div class="arch-node">
    <div class="arch-icon arch-icon-outline">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
    </div>
    <div class="arch-text">
      <span class="arch-label">Your GraphQL Schema</span>
      <span class="arch-desc">Any graphql-core schema — Strawberry, Ariadne, Graphene, graphql-api, or a remote endpoint.</span>
    </div>
  </div>
  <div class="arch-connector"></div>
  <div class="arch-node">
    <div class="arch-icon arch-icon-brand">
      <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
    </div>
    <div class="arch-text">
      <span class="arch-label">GraphQL MCP</span>
      <span class="arch-desc">Analyzes your schema — queries become read tools, mutations become write tools. Types, enums, and descriptions are preserved.</span>
    </div>
  </div>
  <div class="arch-connector"></div>
  <div class="arch-node">
    <div class="arch-icon arch-icon-outline">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
    </div>
    <div class="arch-text">
      <span class="arch-label">MCP Tools</span>
      <span class="arch-desc">search_users(query, limit) · create_post(title, body) · get_analytics(range) — ready for any AI agent.</span>
    </div>
  </div>
  <div class="arch-connector"></div>
  <div class="arch-node">
    <div class="arch-icon arch-icon-blue">
      <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
    </div>
    <div class="arch-text">
      <span class="arch-label">AI Agents</span>
      <span class="arch-desc">Claude, ChatGPT, Cursor, or any MCP-compatible client calls your tools over HTTP, SSE, or streamable-HTTP.</span>
    </div>
  </div>
</div>

## Before & after

<div class="before-after">
<div class="media-frame">

**Without GraphQL MCP** — define every tool by hand

```python
@tool
def search_users(query: str, limit: int = 10):
    """Search for users by name or email."""
    # build GraphQL query string
    # execute against schema
    # parse and return results
    ...

@tool
def create_post(title: str, body: str):
    """Create a new blog post."""
    # build mutation string
    # execute against schema
    # parse and return results
    ...

# repeat for every field...
```

</div>
<div class="media-frame">

**With GraphQL MCP** — tools generated automatically

```python
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_api(api, name="My API")
app = server.http_app()
```

Every query and mutation in your schema is now an MCP tool — with types, descriptions, and validation preserved. No boilerplate.

</div>
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
