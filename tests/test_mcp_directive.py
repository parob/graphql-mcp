"""Tests for the unified @mcp directive."""
import pytest
import inspect
from typing import Annotated


def _check_graphql_api_directive_support():
    """Check if graphql-api has argument directive support (1.6.0+)."""
    try:
        from graphql_api import GraphQLAPI, field  # noqa: F401
        from graphql_api.directives import SchemaDirective  # noqa: F401
        from graphql_api.mapper import extract_annotated_directives  # noqa: F401
        return True
    except ImportError:
        return False


class TestHiddenArgDirective:
    """Tests for hiding arguments via @mcp(hidden: true)."""

    @pytest.fixture
    def api_with_hidden_args(self):
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api argument directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import mcp

        if mcp is None:
            pytest.skip("mcp directive not available (graphql-api not installed)")

        class TestAPI:
            @field
            def search(
                self,
                query: str,
                internal_flag: Annotated[bool, mcp(hidden=True)] = False,
                debug_mode: Annotated[bool, mcp(hidden=True)] = False,
            ) -> str:
                """Search with hidden args."""
                return f"query={query}, internal={internal_flag}, debug={debug_mode}"

            @field
            def normal_query(self, name: str) -> str:
                """A normal query without hidden args."""
                return f"Hello, {name}!"

        return GraphQLAPI(root_type=TestAPI, directives=[mcp])

    def test_graphql_schema_has_all_args(self, api_with_hidden_args):
        schema = api_with_hidden_args.schema()
        search_field = schema.query_type.fields['search']
        assert 'query' in search_field.args
        assert 'internalFlag' in search_field.args
        assert 'debugMode' in search_field.args

    def test_graphql_schema_has_directive(self, api_with_hidden_args):
        schema = api_with_hidden_args.schema()
        search_field = schema.query_type.fields['search']

        internal_flag_arg = search_field.args['internalFlag']
        query_arg = search_field.args['query']

        internal_directives = getattr(internal_flag_arg, '_applied_directives', [])
        query_directives = getattr(query_arg, '_applied_directives', [])

        assert len(internal_directives) > 0
        assert internal_directives[0].directive.name == 'mcp'
        assert internal_directives[0].args.get('hidden') is True
        assert len(query_directives) == 0

    @pytest.mark.asyncio
    async def test_mcp_tool_hides_args(self, api_with_hidden_args):
        from graphql_mcp import GraphQLMCP

        server = GraphQLMCP.from_api(api_with_hidden_args)
        search_tool = await server.get_tool('search')
        assert search_tool is not None

        sig = inspect.signature(search_tool.fn)
        param_names = list(sig.parameters.keys())

        assert 'query' in param_names
        assert 'internalFlag' not in param_names
        assert 'internal_flag' not in param_names
        assert 'debugMode' not in param_names
        assert 'debug_mode' not in param_names

    @pytest.mark.asyncio
    async def test_normal_query_unchanged(self, api_with_hidden_args):
        from graphql_mcp import GraphQLMCP

        server = GraphQLMCP.from_api(api_with_hidden_args)
        normal_tool = await server.get_tool('normal_query')
        assert normal_tool is not None

        sig = inspect.signature(normal_tool.fn)
        assert 'name' in sig.parameters


class TestHiddenArgValidation:
    def test_hidden_arg_without_default_raises_error_via_directive(self):
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api argument directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        if mcp is None:
            pytest.skip("mcp directive not available")

        class BadAPI:
            @field
            def bad_method(
                self,
                query: str,
                hidden_required: Annotated[str, mcp(hidden=True)]
            ) -> str:
                return query

        api = GraphQLAPI(root_type=BadAPI, directives=[mcp])

        with pytest.raises(ValueError, match="must have defaults"):
            GraphQLMCP.from_api(api)

    def test_hidden_arg_without_default_raises_error_via_sdl(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                badQuery(query: String!, hiddenRequired: String! @mcp(hidden: true)): String
            }
        """)

        with pytest.raises(ValueError, match="must have defaults"):
            GraphQLMCP(schema=schema)


class TestHiddenViaSDL:
    """Tests for @mcp directive via SDL (works with any library)."""

    @pytest.mark.asyncio
    async def test_sdl_directive_hides_arguments(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                search(
                    query: String!
                    internalFlag: Boolean = false @mcp(hidden: true)
                    debugMode: Boolean = false @mcp(hidden: true)
                ): String
            }
        """)

        server = GraphQLMCP(schema=schema)
        search_tool = await server.get_tool('search')
        assert search_tool is not None

        sig = inspect.signature(search_tool.fn)
        param_names = list(sig.parameters.keys())

        assert 'query' in param_names
        assert 'internalFlag' not in param_names
        assert 'debugMode' not in param_names

    def test_sdl_graphql_schema_unchanged(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                search(query: String!, internalFlag: Boolean = false @mcp(hidden: true)): String
            }
        """)

        server = GraphQLMCP(schema=schema)
        assert 'internalFlag' in server.schema.query_type.fields['search'].args


class TestHideField:
    """Tests for @mcp(hidden: true) on FIELD_DEFINITION."""

    @pytest.mark.asyncio
    async def test_sdl_hide_field(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                visible: String
                internalMetrics: String @mcp(hidden: true)
            }
        """)

        server = GraphQLMCP(schema=schema)
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}

        assert 'visible' in tool_names
        assert 'internal_metrics' not in tool_names
        assert 'internalMetrics' not in tool_names

    @pytest.mark.asyncio
    async def test_hide_field_via_graphql_api(self):
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp

        if mcp is None:
            pytest.skip("mcp directive not available")

        class TestAPI:
            @field
            @mcp(hidden=True)
            def internal_metrics(self) -> str:
                return "secret"

            @field
            def public(self, name: str) -> str:
                return f"Hello, {name}"

        api = GraphQLAPI(root_type=TestAPI, directives=[mcp])
        server = GraphQLMCP.from_api(api)
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}

        assert 'public' in tool_names
        assert 'internal_metrics' not in tool_names


class TestRenameTool:
    @pytest.mark.asyncio
    async def test_sdl_rename_tool(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                getUserById(userId: ID!): String @mcp(name: "fetch_user")
            }
        """)

        server = GraphQLMCP(schema=schema)
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}

        assert 'fetch_user' in tool_names
        assert 'get_user_by_id' not in tool_names


class TestRenameArg:
    @pytest.mark.asyncio
    async def test_sdl_rename_arg(self):
        from graphql import build_schema, graphql as graphql_execute

        from graphql_mcp import GraphQLMCP

        # graphql-core build_schema can't resolve fields without resolvers;
        # attach a simple one manually.
        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                getUserById(userId: ID! @mcp(name: "id")): String
            }
        """)
        schema.query_type.fields['getUserById'].resolve = (
            lambda root, info, userId: f"user:{userId}"
        )

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('get_user_by_id')
        assert tool is not None

        sig = inspect.signature(tool.fn)
        param_names = list(sig.parameters.keys())
        assert 'id' in param_names
        assert 'userId' not in param_names

        # Verify outbound GraphQL uses original arg name
        result = await tool.fn(id="42")
        assert result == "user:42"

        # And that calling the raw schema with the original arg name also works
        raw = await graphql_execute(
            schema, "query { getUserById(userId: \"99\") }"
        )
        assert raw.data == {"getUserById": "user:99"}


class TestOverrideFieldDescription:
    @pytest.mark.asyncio
    async def test_sdl_override_field_description(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                "Original GraphQL description"
                greet(name: String!): String @mcp(description: "Override for MCP")
            }
        """)

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('greet')
        assert tool is not None

        # FastMCP exposes the tool's description via the wrapper's docstring.
        assert tool.fn.__doc__ == "Override for MCP"


class TestOverrideArgDescription:
    @pytest.mark.asyncio
    async def test_sdl_override_arg_description(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                greet(name: String! @mcp(description: "User display name")): String
            }
        """)

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('greet')
        assert tool is not None

        # The annotation should be Annotated[str, FieldInfo(description=...)]
        from typing import get_type_hints, get_args
        hints = get_type_hints(tool.fn, include_extras=True)
        annotated_args = get_args(hints['name'])
        # First positional is the type, remaining are metadata
        descriptions = [
            getattr(m, 'description', None) for m in annotated_args[1:]
        ]
        assert "User display name" in descriptions


class TestCombinedOptions:
    @pytest.mark.asyncio
    async def test_sdl_rename_and_describe(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                getUserById(userId: ID!): String
                    @mcp(name: "fetch_user", description: "Fetch a user by ID")
            }
        """)

        server = GraphQLMCP(schema=schema)
        tool = await server.get_tool('fetch_user')
        assert tool is not None
        assert tool.fn.__doc__ == "Fetch a user by ID"


class TestDuplicateToolNames:
    def test_duplicate_renamed_tool_raises(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                first: String @mcp(name: "shared")
                second: String @mcp(name: "shared")
            }
        """)

        with pytest.raises(ValueError, match="Duplicate MCP tool name"):
            GraphQLMCP(schema=schema)


class TestMutationDirective:
    @pytest.mark.asyncio
    async def test_sdl_rename_mutation(self):
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query { ping: String }
            type Mutation {
                createUser(name: String!): String @mcp(name: "make_user")
            }
        """)

        server = GraphQLMCP(schema=schema)
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}

        assert 'make_user' in tool_names
        assert 'create_user' not in tool_names


class TestHelperFunctions:
    def test_to_snake_case(self):
        from graphql_mcp.server import _to_snake_case

        assert _to_snake_case("internalFlag") == "internal_flag"
        assert _to_snake_case("debugMode") == "debug_mode"
        assert _to_snake_case("simple") == "simple"
        assert _to_snake_case("ABC") == "a_b_c"

    def test_get_mcp_config_plain_arg(self):
        from graphql import GraphQLArgument, GraphQLString
        from graphql_mcp.server import _get_mcp_config

        arg = GraphQLArgument(GraphQLString)
        cfg = _get_mcp_config(arg)
        assert cfg.hidden is False
        assert cfg.name is None
        assert cfg.description is None

    def test_is_arg_hidden_plain_arg(self):
        from graphql import GraphQLArgument, GraphQLString
        from graphql_mcp.server import _is_arg_hidden

        arg = GraphQLArgument(GraphQLString)
        assert _is_arg_hidden(arg) is False

    def test_get_mcp_config_with_sdl_directive(self):
        from graphql import build_schema
        from graphql_mcp.server import _get_mcp_config

        schema = build_schema("""
            directive @mcp(
                name: String
                description: String
                hidden: Boolean
            ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

            type Query {
                foo(
                    x: String!
                    y: String = "" @mcp(name: "yy", description: "Y arg", hidden: false)
                    z: String = "" @mcp(hidden: true)
                ): String @mcp(name: "bar")
            }
        """)

        foo_field = schema.query_type.fields['foo']
        field_cfg = _get_mcp_config(foo_field)
        assert field_cfg.name == "bar"
        assert field_cfg.hidden is False

        y_cfg = _get_mcp_config(foo_field.args['y'])
        assert y_cfg.name == "yy"
        assert y_cfg.description == "Y arg"
        assert y_cfg.hidden is False

        z_cfg = _get_mcp_config(foo_field.args['z'])
        assert z_cfg.hidden is True

    def test_get_mcp_config_via_applied_directives(self):
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import mcp
        from graphql_mcp.server import _get_mcp_config

        if mcp is None:
            pytest.skip("mcp directive not available")

        class TestAPI:
            @field
            def test_method(
                self,
                visible: str,
                renamed: Annotated[str, mcp(name="alt")] = "",
                hidden: Annotated[str, mcp(hidden=True)] = "",
            ) -> str:
                return visible

        api = GraphQLAPI(root_type=TestAPI, directives=[mcp])
        schema = api.schema()

        test_field = schema.query_type.fields['testMethod']
        visible_cfg = _get_mcp_config(test_field.args['visible'])
        renamed_cfg = _get_mcp_config(test_field.args['renamed'])
        hidden_cfg = _get_mcp_config(test_field.args['hidden'])

        assert visible_cfg.name is None and visible_cfg.hidden is False
        assert renamed_cfg.name == "alt"
        assert hidden_cfg.hidden is True


class TestDirectiveExport:
    def test_mcp_exported(self):
        from graphql_mcp import mcp

        assert mcp is None or hasattr(mcp, 'directive')

    def test_mcp_is_schema_directive(self):
        try:
            from graphql_api.directives import SchemaDirective
        except ImportError:
            pytest.skip("graphql-api not installed")

        from graphql_mcp import mcp

        assert mcp is not None
        assert isinstance(mcp, SchemaDirective)
        assert mcp.directive.name == 'mcp'

    def test_mcp_hidden_removed(self):
        import graphql_mcp

        # mcp_hidden was removed in favor of the unified `mcp` directive.
        assert not hasattr(graphql_mcp, 'mcp_hidden')
