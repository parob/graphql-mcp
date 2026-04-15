---
title: "Strawberry & Graphene"
---

# Strawberry & Graphene

The [`@mcp` directive](/configuration#mcp-directive) relies on graphql-core's `ast_node.directives` or `_applied_directives` to read configuration off a field or argument. Strawberry and Graphene's Python APIs don't populate those attributes by default, so a plain Strawberry/Graphene schema loses directive metadata by the time graphql-mcp sees it.

There are three supported paths to apply `@mcp` in this situation. **They are alternatives — pick one.** They do not stack.

## Picking a path

| Path | Strawberry | Graphene | When to use |
|------|:---:|:---:|------|
| [A. Native Strawberry directive + rebuild](#a-native-strawberry-directive-rebuild) | ✅ | ❌ | You want `@mcp` visible in your schema's SDL and understood by any other tool reading the AST. |
| [B. `apply_mcp()` helper](#b-apply_mcp-helper) | ✅ | ✅ | You want minimal code. Best default for most projects. |
| [C. Full SDL rebuild](#c-full-sdl-rebuild-fallback) | ✅ | ✅ | Fallback for edge cases — avoid unless A and B don't fit. |

You only need one. Mixing them for the same field is fine (idempotent) but pointless.

## A. Native Strawberry directive + rebuild

Strawberry's own `@schema_directive` support *does* round-trip through `str(schema)`, and graphql-core's `build_schema` preserves directives in `ast_node`. So you can declare a Strawberry directive named `mcp`, apply it normally, then rebuild the schema for graphql-mcp.

```python
from typing import Annotated
import strawberry
from strawberry.schema_directive import Location
from graphql import build_schema
from graphql_mcp import GraphQLMCP


@strawberry.schema_directive(
    locations=[Location.FIELD_DEFINITION, Location.ARGUMENT_DEFINITION]
)
class Mcp:
    name: str = ""
    description: str = ""
    hidden: bool = False


@strawberry.type
class Query:
    @strawberry.field(
        directives=[Mcp(name="say_hi", description="Friendly greeting.")]
    )
    def greet(
        self,
        name: Annotated[
            str, strawberry.argument(directives=[Mcp(name="user_name")])
        ],
    ) -> str:
        return f"Hello, {name}!"


sb_schema = strawberry.Schema(query=Query)
# Round-trip through SDL to populate graphql-core's ast_node.directives.
rebuilt = build_schema(str(sb_schema))
# Copy resolvers back across — graphql-core's build_schema doesn't carry them.
for fname, sb_field in sb_schema._schema.query_type.fields.items():
    if fname in rebuilt.query_type.fields:
        rebuilt.query_type.fields[fname].resolve = sb_field.resolve

server = GraphQLMCP(schema=rebuilt)
```

::: info Why the rebuild?
Strawberry stores directive information internally on its own wrapper classes — it doesn't set `ast_node` on the underlying graphql-core fields. `str(sb_schema)` uses Strawberry's printer (which includes the directives), and `build_schema` re-parses that SDL into proper `ast_node.directives`, which graphql-mcp reads.
:::

Graphene does not have equivalent native directive support, so this path doesn't apply to Graphene.

## B. `apply_mcp()` helper

`apply_mcp()` attaches the same directive metadata directly onto graphql-core's field and argument objects — no SDL roundtrip, no resolver copying. Works for Strawberry, Graphene, and any other library whose schema is (or wraps) a graphql-core schema.

::: code-group
```python [Strawberry]
import strawberry
from graphql_mcp import GraphQLMCP, apply_mcp


@strawberry.type
class Query:
    @strawberry.field
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


sb_schema = strawberry.Schema(query=Query)

apply_mcp(
    sb_schema._schema,
    fields={"Query.greet": {
        "name": "say_hi",
        "description": "Friendly greeting.",
    }},
    args={"Query.greet.name": {"name": "user_name"}},
)

server = GraphQLMCP(schema=sb_schema._schema)
```

```python [Graphene]
import graphene
from graphql_mcp import GraphQLMCP, apply_mcp


class Query(graphene.ObjectType):
    greet = graphene.String(name=graphene.String(required=True))

    def resolve_greet(self, info, name):
        return f"Hello, {name}!"


g_schema = graphene.Schema(query=Query)

apply_mcp(
    g_schema.graphql_schema,
    fields={"Query.greet": {"name": "say_hi"}},
    args={"Query.greet.name": {"name": "user_name"}},
)

server = GraphQLMCP(schema=g_schema.graphql_schema)
```
:::

### Path format

- Fields: `"TypeName.fieldName"` — e.g. `"Query.greet"`, `"Mutation.createUser"`.
- Arguments: `"TypeName.fieldName.argName"` — e.g. `"Query.greet.name"`.

Unknown paths raise `ValueError` immediately with a list of valid names — safer than silent no-ops.

### Supported keys

Same three as the SDL directive: `name`, `description`, `hidden`. Any other key raises `ValueError`.

::: warning Caveats for `apply_mcp()`

- **Invisible to other tools.** `apply_mcp` sets a private attribute (`_applied_directives`). Unlike the SDL `@mcp` directive, the configuration **won't appear in `str(schema)`, introspection responses, or federation composition**. If you want the directive to be visible to other consumers, use Path A or Path C.
- **Mutates the schema in place.** Calling `apply_mcp` modifies the `GraphQLSchema` you pass. If you share the same schema object across multiple MCP servers or contexts, they all see the overrides. Configure once at startup.
- **Last-resort semantics.** Prefer native directive paths when the library supports them (graphql-api via `Annotated[..., mcp(...)]`, Strawberry via Path A, SDL via the normal `@mcp` directive). Those survive printing and introspection; this doesn't.
- **Precedence with native directives.** If the same field has *both* a native directive (from SDL or Strawberry) and an `apply_mcp` entry, both are read by `_get_mcp_config`, which takes the first non-null value it sees for each key. Don't rely on the ordering — apply overrides through one mechanism, not two.
- **No schema-level effect.** `apply_mcp` only changes MCP exposure. The GraphQL endpoint itself (introspection, normal queries) is untouched.

:::

## C. Full SDL rebuild (fallback)

Works but involves the most code. Use this only if A and B don't fit.

::: code-group
```python [Strawberry]
import strawberry
from graphql import build_schema, print_schema
from graphql_mcp import GraphQLMCP


@strawberry.type
class Query:
    @strawberry.field
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


sb_schema = strawberry.Schema(query=Query)

MCP_DIRECTIVE = """
directive @mcp(
    name: String
    description: String
    hidden: Boolean
) on FIELD_DEFINITION | ARGUMENT_DEFINITION
"""

# 1. Print the Strawberry schema to SDL and add @mcp where you want it.
sdl = MCP_DIRECTIVE + print_schema(sb_schema._schema).replace(
    "greet(name: String!): String!",
    'greet(name: String! @mcp(name: "user_name")): String! @mcp(name: "say_hi")',
)

# 2. Rebuild with graphql-core.
rebuilt = build_schema(sdl)

# 3. Copy resolvers over from the original schema.
for field_name, sb_field in sb_schema._schema.query_type.fields.items():
    if field_name in rebuilt.query_type.fields:
        rebuilt.query_type.fields[field_name].resolve = sb_field.resolve

server = GraphQLMCP(schema=rebuilt)
```

```python [Graphene]
import graphene
from graphql import build_schema, print_schema
from graphql_mcp import GraphQLMCP


class Query(graphene.ObjectType):
    greet = graphene.String(name=graphene.String(required=True))

    def resolve_greet(self, info, name):
        return f"Hello, {name}!"


g_schema = graphene.Schema(query=Query)
core_schema = g_schema.graphql_schema

MCP_DIRECTIVE = """
directive @mcp(
    name: String
    description: String
    hidden: Boolean
) on FIELD_DEFINITION | ARGUMENT_DEFINITION
"""

sdl = MCP_DIRECTIVE + print_schema(core_schema).replace(
    "greet(name: String!): String",
    'greet(name: String! @mcp(name: "user_name")): String @mcp(name: "say_hi")',
)

rebuilt = build_schema(sdl)
for field_name, g_field in core_schema.query_type.fields.items():
    if field_name in rebuilt.query_type.fields:
        rebuilt.query_type.fields[field_name].resolve = g_field.resolve

server = GraphQLMCP(schema=rebuilt)
```
:::

::: warning Caveats for Path C

- The `.replace(...)` is **fragile**: if the field signature changes (added argument, renamed, type changed), the replacement silently becomes a no-op and your `@mcp` directive quietly stops being applied. Consider asserting the replacement took effect, or use Path B instead.
- Copying resolvers works because Strawberry and Graphene resolvers don't depend on the schema object — but watch for resolvers that close over the original schema (unusual but possible).

:::

## Context-based hiding (no schema changes)

If all you need is `@mcp(hidden: true)` on a single argument that the AI agent shouldn't see, restructure the resolver to read the value from the GraphQL context rather than declaring it as an argument at all. This sidesteps the directive question entirely.

```python
@strawberry.field
def current_user(self, info) -> User:
    # user_id comes from auth middleware / GraphQL context, not an argument.
    user_id = info.context["user_id"]
    return get_user(user_id)
```

No schema gymnastics, no `apply_mcp`, no directive — the argument simply doesn't exist in the public API.
