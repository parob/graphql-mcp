"""Tests for ``apply_mcp()`` — the programmatic alternative to the @mcp SDL
directive. Mirrors the coverage of ``test_mcp_directive.py`` but applies
configuration through the Python API rather than SDL."""
import inspect
import pytest
from fastmcp.client import Client
from typing import cast
from mcp.types import TextContent


def get_result_text(result):
    if hasattr(result, "content"):
        return cast(TextContent, result.content[0]).text
    return cast(TextContent, result[0]).text


# ---------------------------------------------------------------------------
# Unit tests: synthetic applied directive is read the same way as real ones.
# ---------------------------------------------------------------------------


class TestReaderInterop:
    """apply_mcp attaches a ``_applied_directives`` entry that must be read
    identically to the real graphql-api ``AppliedDirective`` entries by
    ``_get_mcp_config``."""

    def test_attaches_field_config(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp
        from graphql_mcp.server import _get_mcp_config

        schema = build_schema("type Query { greet(name: String!): String }")
        apply_mcp(
            schema,
            fields={"Query.greet": {
                "name": "say_hi",
                "description": "Friendly greet",
            }},
        )

        cfg = _get_mcp_config(schema.query_type.fields["greet"])
        assert cfg.name == "say_hi"
        assert cfg.description == "Friendly greet"
        assert cfg.hidden is False

    def test_attaches_arg_config(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp
        from graphql_mcp.server import _get_mcp_config

        schema = build_schema("type Query { greet(name: String!): String }")
        apply_mcp(
            schema,
            args={"Query.greet.name": {"name": "user_name"}},
        )

        cfg = _get_mcp_config(schema.query_type.fields["greet"].args["name"])
        assert cfg.name == "user_name"

    def test_hidden_flag(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp
        from graphql_mcp.server import _get_mcp_config

        schema = build_schema("type Query { secret: String visible: String }")
        apply_mcp(schema, fields={"Query.secret": {"hidden": True}})

        assert _get_mcp_config(schema.query_type.fields["secret"]).hidden is True
        assert _get_mcp_config(schema.query_type.fields["visible"]).hidden is False

    def test_idempotent_replaces_not_stacks(self):
        """Calling apply_mcp twice should overwrite the previous @mcp entry
        rather than stack — otherwise the 'first wins' precedence in
        _get_mcp_config would silently keep stale config."""
        from graphql import build_schema
        from graphql_mcp import apply_mcp
        from graphql_mcp.server import _get_mcp_config

        schema = build_schema("type Query { greet(name: String!): String }")
        apply_mcp(schema, fields={"Query.greet": {"name": "first"}})
        apply_mcp(schema, fields={"Query.greet": {"name": "second"}})

        cfg = _get_mcp_config(schema.query_type.fields["greet"])
        assert cfg.name == "second"

        # Only one @mcp entry should be on the field.
        applied = schema.query_type.fields["greet"]._applied_directives
        mcp_entries = [d for d in applied if d.directive.name == "mcp"]
        assert len(mcp_entries) == 1

    def test_preserves_unrelated_applied_directives(self):
        """apply_mcp must not clobber directive entries from other sources
        (e.g. graphql-api's own AppliedDirective for unrelated directives)."""
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet(name: String!): String }")
        greet = schema.query_type.fields["greet"]

        # Simulate an unrelated directive entry already on the field.
        class Fake:
            name = "deprecated"
        greet._applied_directives = [type("D", (), {"directive": Fake(), "args": {}})()]

        apply_mcp(schema, fields={"Query.greet": {"name": "say_hi"}})

        names = [d.directive.name for d in greet._applied_directives]
        assert "deprecated" in names
        assert "mcp" in names


# ---------------------------------------------------------------------------
# End-to-end: FastMCP Client sees the applied overrides.
# ---------------------------------------------------------------------------


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_rename_field_and_arg_via_apply_mcp(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("""
            type Query {
                getUserById(userId: ID!): String
            }
        """)
        schema.query_type.fields["getUserById"].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )
        apply_mcp(
            schema,
            fields={"Query.getUserById": {
                "name": "fetch_user",
                "description": "Fetch a user by ID.",
            }},
            args={"Query.getUserById.userId": {"name": "id"}},
        )

        server = GraphQLMCP(schema=schema)
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "fetch_user" in names
            assert "get_user_by_id" not in names

            tool = next(t for t in tools if t.name == "fetch_user")
            assert tool.description == "Fetch a user by ID."
            props = tool.inputSchema.get("properties", {})
            assert "id" in props
            assert "userId" not in props

            result = await client.call_tool("fetch_user", {"id": "42"})
            assert get_result_text(result) == "user:42"

    @pytest.mark.asyncio
    async def test_hide_field_via_apply_mcp(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("""
            type Query {
                visible: String
                internalMetrics: String
            }
        """)
        schema.query_type.fields["visible"].resolve = lambda *a, **k: "ok"
        apply_mcp(schema, fields={"Query.internalMetrics": {"hidden": True}})

        server = GraphQLMCP(schema=schema)
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "visible" in names
            assert "internal_metrics" not in names

    @pytest.mark.asyncio
    async def test_hide_arg_must_have_default(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("""
            type Query {
                search(query: String!, debugToken: String!): String
            }
        """)
        # Hiding a required arg with no default should raise at registration.
        apply_mcp(schema, args={"Query.search.debugToken": {"hidden": True}})

        with pytest.raises(ValueError, match="must have defaults"):
            GraphQLMCP(schema=schema)

    @pytest.mark.asyncio
    async def test_strawberry_end_to_end(self):
        """The headline use case: make @mcp work on a real Strawberry schema
        without SDL gymnastics."""
        try:
            import strawberry
        except ImportError:
            pytest.skip("strawberry not installed")

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
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "say_hi" in names
            assert "greet" not in names

            tool = next(t for t in tools if t.name == "say_hi")
            assert tool.description == "Friendly greeting."
            props = tool.inputSchema.get("properties", {})
            assert "user_name" in props
            assert "name" not in props

            result = await client.call_tool("say_hi", {"user_name": "World"})
            assert get_result_text(result) == "Hello, World!"

    @pytest.mark.asyncio
    async def test_graphene_end_to_end(self):
        try:
            import graphene
        except ImportError:
            pytest.skip("graphene not installed")

        from graphql_mcp import GraphQLMCP, apply_mcp

        class Query(graphene.ObjectType):
            greet = graphene.String(name=graphene.String(required=True))

            def resolve_greet(self, info, name):
                return f"Hello, {name}!"

        g_schema = graphene.Schema(query=Query)
        # Graphene uses the Query class name as the type name by default.
        apply_mcp(
            g_schema.graphql_schema,
            fields={"Query.greet": {"name": "say_hi"}},
            args={"Query.greet.name": {"name": "user_name"}},
        )

        server = GraphQLMCP(schema=g_schema.graphql_schema)
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "say_hi" in names

            result = await client.call_tool("say_hi", {"user_name": "Graphene"})
            assert get_result_text(result) == "Hello, Graphene!"


# ---------------------------------------------------------------------------
# Validation: strict errors on bad paths / unknown keys.
# ---------------------------------------------------------------------------


class TestValidation:
    def test_unknown_type_raises(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet: String }")
        with pytest.raises(ValueError, match="Type 'NoSuchType' not found"):
            apply_mcp(schema, fields={"NoSuchType.greet": {"name": "x"}})

    def test_unknown_field_raises_with_suggestion(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet: String farewell: String }")
        with pytest.raises(ValueError, match="Field 'hi' not found"):
            apply_mcp(schema, fields={"Query.hi": {"name": "x"}})

    def test_unknown_arg_raises_with_suggestion(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet(name: String!): String }")
        with pytest.raises(ValueError, match="Argument 'nickname' not found"):
            apply_mcp(schema, args={"Query.greet.nickname": {"name": "x"}})

    def test_unknown_config_key_raises(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet: String }")
        with pytest.raises(ValueError, match="Unknown @mcp keys"):
            apply_mcp(schema, fields={"Query.greet": {"renamed": "x"}})

    def test_bad_path_format_for_field(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet: String }")
        with pytest.raises(ValueError, match="must be 'TypeName.fieldName'"):
            apply_mcp(schema, fields={"greet": {"name": "x"}})

    def test_bad_path_format_for_arg(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet(name: String!): String }")
        with pytest.raises(
            ValueError, match="must be 'TypeName.fieldName.argName'"
        ):
            apply_mcp(schema, args={"Query.greet": {"name": "x"}})

    def test_non_dict_config_raises(self):
        from graphql import build_schema
        from graphql_mcp import apply_mcp

        schema = build_schema("type Query { greet: String }")
        with pytest.raises(TypeError, match="must be a dict"):
            apply_mcp(schema, fields={"Query.greet": "say_hi"})  # type: ignore


# ---------------------------------------------------------------------------
# Signature-level sanity check.
# ---------------------------------------------------------------------------


class TestSignatureLevel:
    @pytest.mark.asyncio
    async def test_wrapper_translates_renamed_arg_back_to_graphql(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP, apply_mcp

        schema = build_schema("""
            type Query { getUserById(userId: ID!): String }
        """)
        schema.query_type.fields["getUserById"].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )
        apply_mcp(schema, args={"Query.getUserById.userId": {"name": "id"}})

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool("get_user_by_id")
        sig = inspect.signature(tool.fn)
        assert "id" in sig.parameters
        assert "userId" not in sig.parameters
