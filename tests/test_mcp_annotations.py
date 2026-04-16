"""Tests for MCP tool annotation hints via the @mcp directive.

Covers:
- Inference defaults (queries → readOnly=True, mutations → spec defaults).
- Explicit overrides via @mcp SDL, @mcp(...) Python decorator, and apply_mcp.
- End-to-end: annotations surface on the MCP tool listing.
- Interaction cases (user-set readOnly + destructive both go through verbatim).
- Nested tools inherit from the leaf field.
- Remote path parity.
"""
import pytest
from fastmcp.client import Client


MCP_DIRECTIVE_SDL = """
    directive @mcp(
        name: String
        description: String
        hidden: Boolean
        readOnly: Boolean
        destructive: Boolean
        idempotent: Boolean
        openWorld: Boolean
    ) on FIELD_DEFINITION | ARGUMENT_DEFINITION
"""


async def _annotations_for(server, tool_name):
    async with Client(server) as client:
        tools = await client.list_tools()
        t = next(t for t in tools if t.name == tool_name)
        return t.annotations


# ---------------------------------------------------------------------------
# Inference defaults
# ---------------------------------------------------------------------------


class TestInferenceDefaults:
    @pytest.mark.asyncio
    async def test_query_defaults_to_read_only(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("type Query { ping: String }")
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "ping")
        assert a.readOnlyHint is True
        # Other hints remain unset (clients fall back to spec defaults).
        assert a.destructiveHint is None
        assert a.idempotentHint is None
        assert a.openWorldHint is None

    @pytest.mark.asyncio
    async def test_mutation_has_no_inferred_hints(self):
        """Spec defaults already match mutation semantics, so we set nothing."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            type Query { ping: String }
            type Mutation { doStuff: String }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "do_stuff")
        assert a.readOnlyHint is None
        assert a.destructiveHint is None
        assert a.idempotentHint is None
        assert a.openWorldHint is None


# ---------------------------------------------------------------------------
# SDL overrides
# ---------------------------------------------------------------------------


class TestSdlOverrides:
    @pytest.mark.asyncio
    async def test_query_with_side_effect_read_only_false(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                user(id: ID!): String @mcp(
                    readOnly: false,
                    destructive: false,
                    idempotent: true
                )
            }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "user")
        assert a.readOnlyHint is False
        assert a.destructiveHint is False
        assert a.idempotentHint is True

    @pytest.mark.asyncio
    async def test_idempotent_mutation(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query { ping: String }
            type Mutation {
                setStatus(id: ID!, status: String!): String @mcp(idempotent: true)
            }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "set_status")
        assert a.idempotentHint is True
        # readOnly is not forced on mutations.
        assert a.readOnlyHint is None
        # destructive left to spec default.
        assert a.destructiveHint is None

    @pytest.mark.asyncio
    async def test_non_destructive_mutation(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query { ping: String }
            type Mutation {
                addComment(postId: ID!, body: String!): String
                    @mcp(destructive: false)
            }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "add_comment")
        assert a.destructiveHint is False

    @pytest.mark.asyncio
    async def test_open_world_override(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                localProduct(id: ID!): String @mcp(openWorld: false)
                webSearch(query: String!): String @mcp(openWorld: true)
            }
        """)
        server = GraphQLMCP(schema=schema)

        local = await _annotations_for(server, "local_product")
        remote = await _annotations_for(server, "web_search")
        assert local.openWorldHint is False
        assert remote.openWorldHint is True

    @pytest.mark.asyncio
    async def test_all_four_hints_together(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query { ping: String }
            type Mutation {
                doThing: String @mcp(
                    readOnly: false,
                    destructive: true,
                    idempotent: false,
                    openWorld: true
                )
            }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "do_thing")
        assert a.readOnlyHint is False
        assert a.destructiveHint is True
        assert a.idempotentHint is False
        assert a.openWorldHint is True


# ---------------------------------------------------------------------------
# "Contradiction" behaviour — we respect user input verbatim.
# ---------------------------------------------------------------------------


class TestNoSilentDrops:
    @pytest.mark.asyncio
    async def test_read_only_plus_destructive_both_sent(self):
        """Per the MCP spec, `destructive` is meaningful only when
        `readOnly == false`. We still send both — no silent dropping."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                weird: String @mcp(readOnly: true, destructive: true)
            }
        """)
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "weird")
        assert a.readOnlyHint is True
        assert a.destructiveHint is True


# ---------------------------------------------------------------------------
# Python `mcp(...)` decorator (graphql-api)
# ---------------------------------------------------------------------------


def _has_graphql_api():
    try:
        from graphql_api import GraphQLAPI, field  # noqa: F401
        from graphql_mcp import mcp
        return mcp is not None
    except ImportError:
        return False


class TestPythonDecorator:
    @pytest.mark.asyncio
    async def test_snake_case_kwargs(self):
        if not _has_graphql_api():
            pytest.skip("graphql-api not installed")
        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        class API:
            @field
            @mcp(read_only=False, destructive=False, idempotent=True)
            def user(self, id: str) -> str:
                """Logs an access event when reading."""
                return f"user:{id}"

        api = GraphQLAPI(root_type=API, directives=[mcp])
        server = GraphQLMCP.from_api(api)

        a = await _annotations_for(server, "user")
        assert a.readOnlyHint is False
        assert a.destructiveHint is False
        assert a.idempotentHint is True

    @pytest.mark.asyncio
    async def test_camel_case_kwargs_also_work(self):
        if not _has_graphql_api():
            pytest.skip("graphql-api not installed")
        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        class API:
            @field
            @mcp(readOnly=False, openWorld=False)
            def user(self, id: str) -> str:
                return f"user:{id}"

        api = GraphQLAPI(root_type=API, directives=[mcp])
        server = GraphQLMCP.from_api(api)

        a = await _annotations_for(server, "user")
        assert a.readOnlyHint is False
        assert a.openWorldHint is False


# ---------------------------------------------------------------------------
# apply_mcp
# ---------------------------------------------------------------------------


class TestApplyMcp:
    @pytest.mark.asyncio
    async def test_apply_mcp_snake_case(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("type Query { ping: String }")
        apply_mcp(schema, fields={
            "Query.ping": {
                "read_only": False,
                "destructive": False,
                "idempotent": True,
            }
        })
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "ping")
        assert a.readOnlyHint is False
        assert a.destructiveHint is False
        assert a.idempotentHint is True

    @pytest.mark.asyncio
    async def test_apply_mcp_camel_case_aliases(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("type Query { ping: String }")
        apply_mcp(schema, fields={
            "Query.ping": {"readOnly": False, "openWorld": False}
        })
        server = GraphQLMCP(schema=schema)

        a = await _annotations_for(server, "ping")
        assert a.readOnlyHint is False
        assert a.openWorldHint is False


# ---------------------------------------------------------------------------
# Nested tools inherit from the leaf field.
# ---------------------------------------------------------------------------


class TestNestedInheritsFromLeaf:
    @pytest.mark.asyncio
    async def test_nested_query_leaf_read_only_false(self):
        if not _has_graphql_api():
            pytest.skip("graphql-api not installed")
        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        class User:
            def __init__(self, uid: str):
                self.uid = uid

            @field
            @mcp(read_only=False, destructive=False, idempotent=True)
            def audit(self, kind: str) -> str:
                """Records an audit event. Not a pure read."""
                return f"audit:{self.uid}:{kind}"

        class Query:
            @field
            def user(self, id: str) -> User:
                return User(id)

        api = GraphQLAPI(query_type=Query, directives=[mcp])
        server = GraphQLMCP.from_api(api)

        # Nested tool is named user_audit (path-derived).
        a = await _annotations_for(server, "user_audit")
        assert a.readOnlyHint is False
        assert a.destructiveHint is False
        assert a.idempotentHint is True


# ---------------------------------------------------------------------------
# Remote path
# ---------------------------------------------------------------------------


class _FakeRemoteClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def execute_with_token(self, query, variables=None, bearer_token_override=None):
        self.calls.append({"query": query, "variables": variables or {}})
        return self.responses


class TestRemotePath:
    @pytest.mark.asyncio
    async def test_remote_query_gets_read_only_inference(self):
        from graphql import build_schema
        from fastmcp import FastMCP
        from graphql_mcp.server import add_tools_from_schema_with_remote

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                lookup(id: ID!): String @mcp(openWorld: true)
            }
        """)
        fake = _FakeRemoteClient(responses={"lookup": "ok"})
        server = FastMCP(name="remote")
        add_tools_from_schema_with_remote(schema, server, fake, allow_mutations=False)

        a = await _annotations_for(server, "lookup")
        # Query inference still applies to the remote path.
        assert a.readOnlyHint is True
        assert a.openWorldHint is True
