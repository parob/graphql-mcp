"""
End-to-end tests for the @mcp directive across GraphQL libraries and code paths.

Covers:
- FastMCP Client end-to-end: renamed tool, renamed arg (with translation),
  hidden tool, hidden arg, description overrides.
- Ariadne (SDL-built schema) with @mcp directives.
- Strawberry + Graphene: directives aren't carried through to the
  graphql-core AST, so @mcp has no effect — this is the documented limitation
  from docs/public/configuration.md. We assert the no-op behavior so we notice
  if upstream ever starts propagating them.
- Remote path via a fake RemoteGraphQLClient: name/description/hidden applied
  to a manually-built schema, confirming the outbound GraphQL query uses the
  original arg name even when the MCP-side arg is renamed.
"""
import inspect
from typing import Annotated, Any, Dict, Optional, cast

import pytest
from fastmcp.client import Client
from mcp.types import TextContent


MCP_DIRECTIVE_SDL = """
    directive @mcp(
        name: String
        description: String
        hidden: Boolean
    ) on FIELD_DEFINITION | ARGUMENT_DEFINITION
"""


def get_result_text(result):
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    return cast(TextContent, result[0]).text


# ---------------------------------------------------------------------------
# End-to-end FastMCP Client tests (SDL schema with resolvers)
# ---------------------------------------------------------------------------


class TestEndToEndClient:
    @pytest.mark.asyncio
    async def test_client_sees_renamed_tool(self):
        """FastMCP Client lists a renamed tool under the new name."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                getUserById(userId: ID!): String @mcp(name: "fetch_user")
            }
        """)
        schema.query_type.fields['getUserById'].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'fetch_user' in names
            assert 'get_user_by_id' not in names

            result = await client.call_tool('fetch_user', {'userId': '42'})
            assert get_result_text(result) == 'user:42'

    @pytest.mark.asyncio
    async def test_client_sees_renamed_arg_and_translates(self):
        """Calling a tool with a renamed arg hits the GraphQL backend under
        the original arg name."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                getUserById(userId: ID! @mcp(name: "id")): String
            }
        """)
        schema.query_type.fields['getUserById'].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == 'get_user_by_id')
            props = tool.inputSchema.get('properties', {})
            assert 'id' in props
            assert 'userId' not in props

            result = await client.call_tool('get_user_by_id', {'id': '99'})
            assert get_result_text(result) == 'user:99'

    @pytest.mark.asyncio
    async def test_client_does_not_see_hidden_tool(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                visible: String
                internalMetrics: String @mcp(hidden: true)
            }
        """)
        schema.query_type.fields['visible'].resolve = lambda *a, **k: "ok"

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'visible' in names
            assert 'internal_metrics' not in names
            assert 'internalMetrics' not in names

            # Attempting to call a hidden tool raises.
            with pytest.raises(Exception):
                await client.call_tool('internal_metrics', {})

    @pytest.mark.asyncio
    async def test_client_does_not_see_hidden_arg(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                search(
                    query: String!
                    debugToken: String = "" @mcp(hidden: true)
                ): String
            }
        """)
        schema.query_type.fields['search'].resolve = (
            lambda root, info, query, debugToken="": f"{query}|{debugToken}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == 'search')
            props = tool.inputSchema.get('properties', {})
            assert 'query' in props
            assert 'debugToken' not in props
            assert 'debug_token' not in props

            result = await client.call_tool('search', {'query': 'hi'})
            assert get_result_text(result) == 'hi|'

    @pytest.mark.asyncio
    async def test_client_sees_field_description_override(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                "Original GraphQL description"
                greet(name: String!): String @mcp(description: "Override for MCP")
            }
        """)
        schema.query_type.fields['greet'].resolve = (
            lambda root, info, name: f"hi {name}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == 'greet')
            assert tool.description == 'Override for MCP'

    @pytest.mark.asyncio
    async def test_client_sees_arg_description_override(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                greet(name: String! @mcp(description: "User display name")): String
            }
        """)
        schema.query_type.fields['greet'].resolve = (
            lambda root, info, name: f"hi {name}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == 'greet')
            name_prop = tool.inputSchema.get('properties', {}).get('name', {})
            assert name_prop.get('description') == 'User display name'

    @pytest.mark.asyncio
    async def test_client_renamed_mutation(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query { ping: String }
            type Mutation {
                createUser(name: String!): String @mcp(name: "make_user")
            }
        """)
        schema.query_type.fields['ping'].resolve = lambda *a, **k: "pong"
        schema.mutation_type.fields['createUser'].resolve = (
            lambda root, info, name: f"created:{name}"
        )

        server = GraphQLMCP(schema=schema, name="Test")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'make_user' in names
            assert 'create_user' not in names

            result = await client.call_tool('make_user', {'name': 'Alice'})
            assert get_result_text(result) == 'created:Alice'


# ---------------------------------------------------------------------------
# Ariadne end-to-end
# ---------------------------------------------------------------------------


class TestAriadneDirective:
    @pytest.mark.asyncio
    async def test_ariadne_rename_and_hide(self):
        try:
            from ariadne import make_executable_schema, QueryType
        except ImportError:
            pytest.skip("ariadne not installed")

        from graphql_mcp import GraphQLMCP

        type_defs = MCP_DIRECTIVE_SDL + """
            type Query {
                search(
                    query: String!
                    internalFlag: Boolean = false @mcp(hidden: true)
                ): String @mcp(name: "find", description: "Search the catalog.")

                getUserById(userId: ID! @mcp(name: "id")): String
            }
        """

        query = QueryType()

        @query.field("search")
        def resolve_search(_, info, query, internalFlag=False):
            return f"q={query}|flag={internalFlag}"

        @query.field("getUserById")
        def resolve_user(_, info, userId):
            return f"user:{userId}"

        schema = make_executable_schema(type_defs, query)
        server = GraphQLMCP(schema=schema, name="Ariadne")

        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'find' in names
            assert 'search' not in names
            assert 'get_user_by_id' in names

            find_tool = next(t for t in tools if t.name == 'find')
            assert find_tool.description == 'Search the catalog.'
            props = find_tool.inputSchema.get('properties', {})
            assert 'query' in props
            assert 'internalFlag' not in props
            assert 'internal_flag' not in props

            user_tool = next(t for t in tools if t.name == 'get_user_by_id')
            user_props = user_tool.inputSchema.get('properties', {})
            assert 'id' in user_props
            assert 'userId' not in user_props

            result = await client.call_tool('find', {'query': 'hello'})
            assert get_result_text(result) == 'q=hello|flag=False'

            result = await client.call_tool('get_user_by_id', {'id': '7'})
            assert get_result_text(result) == 'user:7'


# ---------------------------------------------------------------------------
# Strawberry / Graphene — directives don't propagate (documented limitation)
# ---------------------------------------------------------------------------


class TestStrawberryNoOp:
    """Strawberry's Python API doesn't round-trip the @mcp directive to the
    graphql-core argument's ast_node. We document this limitation in
    docs/public/configuration.md. This test guards that the code still works
    (no-op) and flags the day upstream starts propagating directives."""

    @pytest.mark.asyncio
    async def test_strawberry_schema_ignores_python_directives_silently(self):
        try:
            import strawberry
        except ImportError:
            pytest.skip("strawberry not installed")

        from graphql_mcp import GraphQLMCP

        @strawberry.type
        class Query:
            @strawberry.field
            def hello(self, name: str = "World") -> str:
                return f"Hello, {name}!"

        schema = strawberry.Schema(query=Query)
        # No @mcp directive available via Strawberry Python API — tool should
        # simply register under the default snake_case name with no overrides.
        server = GraphQLMCP(schema=schema._schema, name="Strawberry")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'hello' in names

    @pytest.mark.asyncio
    async def test_strawberry_workaround_rebuild_and_copy_resolvers(self):
        """Workaround A from docs/public/configuration.md:

            1. Print the Strawberry schema to SDL.
            2. Prepend the @mcp directive definition and patch the directive
               onto the fields/args you care about.
            3. Rebuild with graphql.build_schema.
            4. Copy the resolvers across from the Strawberry schema.
        """
        try:
            import strawberry
        except ImportError:
            pytest.skip("strawberry not installed")

        from graphql import build_schema, print_schema
        from graphql_mcp import GraphQLMCP

        @strawberry.type
        class Query:
            @strawberry.field
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

        sb_schema = strawberry.Schema(query=Query)

        # 1+2. SDL with the @mcp directive prepended + applied inline.
        sdl = MCP_DIRECTIVE_SDL + print_schema(sb_schema._schema).replace(
            "greet(name: String!): String!",
            'greet(name: String! @mcp(name: "user_name")): String!'
            ' @mcp(name: "say_hi", description: "Friendly greeting.")',
        )

        # 3. Rebuild with graphql-core.
        rebuilt = build_schema(sdl)

        # 4. Copy resolvers from the Strawberry schema.
        for field_name, sb_field in sb_schema._schema.query_type.fields.items():
            if field_name in rebuilt.query_type.fields:
                rebuilt.query_type.fields[field_name].resolve = sb_field.resolve

        server = GraphQLMCP(schema=rebuilt, name="Strawberry-rebuilt")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'say_hi' in names
            assert 'greet' not in names

            tool = next(t for t in tools if t.name == 'say_hi')
            assert tool.description == "Friendly greeting."
            props = tool.inputSchema.get('properties', {})
            assert 'user_name' in props
            assert 'name' not in props

            result = await client.call_tool('say_hi', {'user_name': 'World'})
            assert get_result_text(result) == 'Hello, World!'

    @pytest.mark.asyncio
    async def test_strawberry_native_schema_directive_via_sdl_rebuild(self):
        """Strawberry's own @schema_directive support round-trips through
        ``str(schema)`` → ``build_schema``. No string manipulation needed."""
        try:
            import strawberry
            from strawberry.schema_directive import Location
        except ImportError:
            pytest.skip("strawberry not installed")

        from typing import Annotated
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
        # The key move: str(sb_schema) includes the directive definitions.
        rebuilt = build_schema(str(sb_schema))
        for fname, sb_field in sb_schema._schema.query_type.fields.items():
            if fname in rebuilt.query_type.fields:
                rebuilt.query_type.fields[fname].resolve = sb_field.resolve

        server = GraphQLMCP(schema=rebuilt, name="Strawberry-native")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'say_hi' in names
            assert 'greet' not in names

            tool = next(t for t in tools if t.name == 'say_hi')
            assert tool.description == 'Friendly greeting.'
            props = tool.inputSchema.get('properties', {})
            assert 'user_name' in props
            assert 'name' not in props

            result = await client.call_tool('say_hi', {'user_name': 'Native'})
            assert get_result_text(result) == 'Hello, Native!'

    @pytest.mark.asyncio
    async def test_strawberry_workaround_via_ariadne(self):
        """Workaround B from docs/public/configuration.md:

            1. Print the Strawberry schema to SDL.
            2. Prepend the @mcp directive definition and patch the directive
               onto the fields/args you care about.
            3. Hand the SDL + Ariadne resolvers to make_executable_schema.
        """
        try:
            import strawberry
            from ariadne import QueryType, make_executable_schema
        except ImportError:
            pytest.skip("strawberry or ariadne not installed")

        from graphql import print_schema
        from graphql_mcp import GraphQLMCP

        @strawberry.type
        class Query:
            @strawberry.field
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

        sb_schema = strawberry.Schema(query=Query)

        type_defs = MCP_DIRECTIVE_SDL + print_schema(sb_schema._schema).replace(
            "greet(name: String!): String!",
            'greet(name: String! @mcp(name: "user_name")): String!'
            ' @mcp(name: "say_hi")',
        )

        q = QueryType()

        @q.field("greet")
        def resolve_greet(_, info, name):
            return f"Hello, {name}!"

        schema = make_executable_schema(type_defs, q)

        server = GraphQLMCP(schema=schema, name="Strawberry-via-Ariadne")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'say_hi' in names
            assert 'greet' not in names

            result = await client.call_tool('say_hi', {'user_name': 'Ariadne'})
            assert get_result_text(result) == 'Hello, Ariadne!'


class TestGrapheneNoOp:
    @pytest.mark.asyncio
    async def test_graphene_schema_no_directive_support(self):
        try:
            import graphene
        except ImportError:
            pytest.skip("graphene not installed")

        from graphql_mcp import GraphQLMCP

        class Query(graphene.ObjectType):
            hello = graphene.String(name=graphene.String(default_value="World"))

            def resolve_hello(self, info, name):
                return f"Hello, {name}!"

        schema = graphene.Schema(query=Query)
        server = GraphQLMCP(schema=schema.graphql_schema, name="Graphene")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'hello' in names

    @pytest.mark.asyncio
    async def test_graphene_workaround_rebuild_and_copy_resolvers(self):
        """Workaround A applied to a Graphene schema."""
        try:
            import graphene
        except ImportError:
            pytest.skip("graphene not installed")

        from graphql import build_schema, print_schema
        from graphql_mcp import GraphQLMCP

        class Query(graphene.ObjectType):
            greet = graphene.String(name=graphene.String(required=True))

            def resolve_greet(self, info, name):
                return f"Hello, {name}!"

        g_schema = graphene.Schema(query=Query)
        core_schema = g_schema.graphql_schema

        sdl = MCP_DIRECTIVE_SDL + print_schema(core_schema).replace(
            "greet(name: String!): String",
            'greet(name: String! @mcp(name: "user_name")): String'
            ' @mcp(name: "say_hi")',
        )

        rebuilt = build_schema(sdl)
        for field_name, g_field in core_schema.query_type.fields.items():
            if field_name in rebuilt.query_type.fields:
                rebuilt.query_type.fields[field_name].resolve = g_field.resolve

        server = GraphQLMCP(schema=rebuilt, name="Graphene-rebuilt")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'say_hi' in names
            assert 'greet' not in names

            tool = next(t for t in tools if t.name == 'say_hi')
            props = tool.inputSchema.get('properties', {})
            assert 'user_name' in props
            assert 'name' not in props

            result = await client.call_tool('say_hi', {'user_name': 'World'})
            assert get_result_text(result) == 'Hello, World!'

    @pytest.mark.asyncio
    async def test_graphene_workaround_via_ariadne(self):
        """Workaround B applied to a Graphene schema."""
        try:
            import graphene
            from ariadne import QueryType, make_executable_schema
        except ImportError:
            pytest.skip("graphene or ariadne not installed")

        from graphql import print_schema
        from graphql_mcp import GraphQLMCP

        class Query(graphene.ObjectType):
            greet = graphene.String(name=graphene.String(required=True))

            def resolve_greet(self, info, name):
                return f"Hello, {name}!"

        g_schema = graphene.Schema(query=Query)
        type_defs = MCP_DIRECTIVE_SDL + print_schema(g_schema.graphql_schema).replace(
            "greet(name: String!): String",
            'greet(name: String! @mcp(name: "user_name")): String'
            ' @mcp(name: "say_hi")',
        )

        q = QueryType()

        @q.field("greet")
        def resolve_greet(_, info, name):
            return f"Hello, {name}!"

        schema = make_executable_schema(type_defs, q)
        server = GraphQLMCP(schema=schema, name="Graphene-via-Ariadne")
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'say_hi' in names

            result = await client.call_tool('say_hi', {'user_name': 'Graphene'})
            assert get_result_text(result) == 'Hello, Graphene!'


# ---------------------------------------------------------------------------
# graphql-api end-to-end (the tightest integration)
# ---------------------------------------------------------------------------


def _check_graphql_api_directive_support():
    try:
        from graphql_api import GraphQLAPI, field  # noqa: F401
        from graphql_api.directives import SchemaDirective  # noqa: F401
        return True
    except ImportError:
        return False


class TestGraphQLApiDirective:
    @pytest.mark.asyncio
    async def test_graphql_api_full_rename_describe_hide(self):
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        if mcp is None:
            pytest.skip("mcp directive not available")

        class TestAPI:
            @field
            @mcp(name="fetch_user", description="Fetch a user by ID.")
            def get_user_by_id(
                self,
                user_id: Annotated[str, mcp(name="id", description="User UUID")],
                debug_token: Annotated[str, mcp(hidden=True)] = "",
            ) -> str:
                return f"user:{user_id}|{debug_token}"

            @field
            @mcp(hidden=True)
            def internal_metrics(self) -> str:
                return "secret"

            @field
            def public(self, name: str) -> str:
                return f"hi {name}"

        api = GraphQLAPI(root_type=TestAPI, directives=[mcp])
        server = GraphQLMCP.from_api(api)

        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'fetch_user' in names
            assert 'get_user_by_id' not in names
            assert 'internal_metrics' not in names
            assert 'public' in names

            fetch_user = next(t for t in tools if t.name == 'fetch_user')
            assert fetch_user.description == 'Fetch a user by ID.'
            props = fetch_user.inputSchema.get('properties', {})
            assert 'id' in props
            assert props['id'].get('description') == 'User UUID'
            assert 'userId' not in props
            assert 'debugToken' not in props
            assert 'debug_token' not in props

            # Outbound call uses the original GraphQL arg name userId
            # (hidden debugToken falls back to its default "").
            result = await client.call_tool('fetch_user', {'id': 'abc'})
            assert get_result_text(result) == 'user:abc|'


# ---------------------------------------------------------------------------
# Remote path (with a fake RemoteGraphQLClient)
# ---------------------------------------------------------------------------


class _FakeRemoteClient:
    """Captures the outbound GraphQL query + variables without hitting the
    network, and returns canned results keyed by the top-level field name."""

    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        self.calls: list[Dict[str, Any]] = []

    async def execute_with_token(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        bearer_token_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.calls.append({
            "query": query,
            "variables": variables or {},
            "bearer_token_override": bearer_token_override,
        })
        # Return all canned responses; the wrapper picks out its own field.
        return self.responses


class TestRemotePath:
    """@mcp applied to a schema passed into add_tools_from_schema_with_remote
    should affect tool registration the same way as the local path. The
    outbound GraphQL query must still use the original arg name."""

    @pytest.mark.asyncio
    async def test_remote_rename_and_arg_translation(self):
        from graphql import build_schema
        from fastmcp import FastMCP

        from graphql_mcp.server import add_tools_from_schema_with_remote

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                getUserById(userId: ID! @mcp(name: "id")): String
                    @mcp(name: "fetch_user", description: "Fetch a user.")
                internalMetrics: String @mcp(hidden: true)
            }
        """)

        fake = _FakeRemoteClient(
            responses={"getUserById": "user:42"},
        )
        server = FastMCP(name="Test-Remote")
        add_tools_from_schema_with_remote(schema, server, fake, allow_mutations=False)

        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'fetch_user' in names
            assert 'get_user_by_id' not in names
            assert 'internal_metrics' not in names

            fetch = next(t for t in tools if t.name == 'fetch_user')
            assert fetch.description == 'Fetch a user.'
            props = fetch.inputSchema.get('properties', {})
            assert 'id' in props
            assert 'userId' not in props

            result = await client.call_tool('fetch_user', {'id': '42'})
            assert get_result_text(result) == 'user:42'

        # Inspect the outbound query: variable declaration + usage must use
        # the original GraphQL arg name (userId), and variables dict must
        # carry the same key.
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert '$userId' in call['query']
        assert 'userId: $userId' in call['query']
        assert '$id' not in call['query']
        assert call['variables'] == {'userId': '42'}

    @pytest.mark.asyncio
    async def test_remote_hidden_field_not_registered(self):
        from graphql import build_schema
        from fastmcp import FastMCP

        from graphql_mcp.server import add_tools_from_schema_with_remote

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                visible: String
                secret: String @mcp(hidden: true)
            }
        """)

        fake = _FakeRemoteClient(responses={"visible": "ok"})
        server = FastMCP(name="Test-Remote")
        add_tools_from_schema_with_remote(schema, server, fake, allow_mutations=False)

        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert 'visible' in names
            assert 'secret' not in names

    @pytest.mark.asyncio
    async def test_remote_duplicate_rename_raises(self):
        from graphql import build_schema
        from fastmcp import FastMCP

        from graphql_mcp.server import add_tools_from_schema_with_remote

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                a: String @mcp(name: "shared")
                b: String @mcp(name: "shared")
            }
        """)

        fake = _FakeRemoteClient(responses={})
        server = FastMCP(name="Test-Remote")
        with pytest.raises(ValueError, match="Duplicate MCP tool name"):
            add_tools_from_schema_with_remote(
                schema, server, fake, allow_mutations=False
            )


# ---------------------------------------------------------------------------
# Signature-level verification
# ---------------------------------------------------------------------------


class TestSignatureLevel:
    """Belt-and-braces checks directly against the generated wrapper's
    inspect.Signature, independent of FastMCP's schema generation."""

    @pytest.mark.asyncio
    async def test_wrapper_signature_uses_renamed_arg(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                getUserById(userId: ID! @mcp(name: "id")): String
            }
        """)
        schema.query_type.fields['getUserById'].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('get_user_by_id')
        sig = inspect.signature(tool.fn)
        assert 'id' in sig.parameters
        assert 'userId' not in sig.parameters

    @pytest.mark.asyncio
    async def test_wrapper_signature_excludes_hidden_arg(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema(MCP_DIRECTIVE_SDL + """
            type Query {
                search(query: String!, debugToken: String = "" @mcp(hidden: true)): String
            }
        """)
        schema.query_type.fields['search'].resolve = (
            lambda root, info, query, debugToken="": query
        )

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('search')
        sig = inspect.signature(tool.fn)
        assert 'query' in sig.parameters
        assert 'debugToken' not in sig.parameters
        assert 'debug_token' not in sig.parameters
