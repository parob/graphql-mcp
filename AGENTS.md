# GraphQL-MCP

> Compatibility note: `AGENTS.md` and `CLAUDE.md` are both supported in this repo.
> Keep these files identical. Any change in one must be mirrored in the other.

MCP server framework built on GraphQL — automatically exposes GraphQL operations as MCP tools. Published on [PyPI](https://pypi.org/project/graphql-mcp/). Works with any Python GraphQL library (Strawberry, Ariadne, Graphene, graphql-api, graphql-core).

## Project Structure

| Directory | Description |
|-----------|-------------|
| `graphql_mcp/` | Main package source |
| `tests/` | Test suite (51 files, pytest) |
| `docs/` | Documentation |
| `examples/` | Example server implementations |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run flake8 graphql_mcp tests
```

## Key Patterns

- `GraphQLMCP.from_api(api)` for local schemas, `.from_remote_url(url)` for existing APIs
- Auto-converts each Query field → read tool, each Mutation field → write tool (if `allow_mutations=True`)
- Tool names use snake_case (converted from camelCase field names)
- Unified `@mcp` directive customizes how fields/arguments are exposed (`name`, `description`, `hidden`) — replaces the previous `@mcpHidden`
- HTTP app: `server.http_app(transport="streamable-http", stateless_http=True)`
- Built on `fastmcp` (>=3.0, <4)

## Releasing

See the ecosystem-level `CLAUDE.md` in the parent workspace for the full release process. In short:

```bash
# Ensure CI is green on main, then:
git tag X.Y.Z
git push origin X.Y.Z
```

CI publishes to PyPI and creates a GitHub Release automatically.
