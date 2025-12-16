"""Tests for MCP-hidden arguments feature using @mcpHidden directive."""
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


class TestMcpHiddenDirective:
    """Tests for the @mcpHidden directive with graphql-api."""

    @pytest.fixture
    def api_with_hidden_args(self):
        """Create a test API with hidden arguments using directive."""
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api argument directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import mcp_hidden

        if mcp_hidden is None:
            pytest.skip("mcp_hidden directive not available (graphql-api not installed)")

        class TestAPI:
            @field
            def search(
                self,
                query: str,
                internal_flag: Annotated[bool, mcp_hidden] = False,
                debug_mode: Annotated[bool, mcp_hidden] = False
            ) -> str:
                """Search with hidden args."""
                return f"query={query}, internal={internal_flag}, debug={debug_mode}"

            @field
            def normal_query(self, name: str) -> str:
                """A normal query without hidden args."""
                return f"Hello, {name}!"

        # Register the mcp_hidden directive with the API
        return GraphQLAPI(root_type=TestAPI, directives=[mcp_hidden])

    def test_graphql_schema_has_all_args(self, api_with_hidden_args):
        """GraphQL schema should still contain hidden arguments."""
        schema = api_with_hidden_args.schema()

        # Get the search field
        search_field = schema.query_type.fields['search']

        # All args should be present in GraphQL schema
        assert 'query' in search_field.args
        assert 'internalFlag' in search_field.args  # camelCase in GraphQL
        assert 'debugMode' in search_field.args

    def test_graphql_schema_has_directive(self, api_with_hidden_args):
        """GraphQL schema should show @mcpHidden directive on hidden arguments."""
        schema = api_with_hidden_args.schema()

        # Get the search field
        search_field = schema.query_type.fields['search']

        # Check that hidden args have the directive
        internal_flag_arg = search_field.args['internalFlag']
        debug_mode_arg = search_field.args['debugMode']
        query_arg = search_field.args['query']

        # Hidden args should have _applied_directives
        internal_directives = getattr(internal_flag_arg, '_applied_directives', [])
        debug_directives = getattr(debug_mode_arg, '_applied_directives', [])
        query_directives = getattr(query_arg, '_applied_directives', [])

        assert len(internal_directives) > 0, "internalFlag should have directive"
        assert len(debug_directives) > 0, "debugMode should have directive"
        assert len(query_directives) == 0, "query should not have directive"

        # Verify directive name
        assert internal_directives[0].directive.name == 'mcpHidden'
        assert debug_directives[0].directive.name == 'mcpHidden'

    def test_mcp_tool_hides_args(self, api_with_hidden_args):
        """MCP tool should not expose hidden arguments."""
        from graphql_mcp import GraphQLMCP

        mcp = GraphQLMCP.from_api(api_with_hidden_args)

        # Get the tool function for search
        search_tool = None
        for tool_name, tool_info in mcp._tool_manager._tools.items():
            if tool_name == 'search':
                search_tool = tool_info
                break

        assert search_tool is not None, "search tool should exist"

        # Get the function signature
        func = search_tool.fn
        sig = inspect.signature(func)

        # Check parameters
        param_names = list(sig.parameters.keys())

        # 'query' should be present
        assert 'query' in param_names, "query should be visible"

        # Hidden args should NOT be present
        assert 'internalFlag' not in param_names, "internalFlag should be hidden"
        assert 'internal_flag' not in param_names, "internal_flag should be hidden"
        assert 'debugMode' not in param_names, "debugMode should be hidden"
        assert 'debug_mode' not in param_names, "debug_mode should be hidden"

    def test_normal_query_unchanged(self, api_with_hidden_args):
        """Queries without @mcpHidden should work normally."""
        from graphql_mcp import GraphQLMCP

        mcp = GraphQLMCP.from_api(api_with_hidden_args)

        # Get the normal_query tool
        normal_tool = None
        for tool_name, tool_info in mcp._tool_manager._tools.items():
            if tool_name == 'normal_query':
                normal_tool = tool_info
                break

        assert normal_tool is not None, "normal_query tool should exist"

        # Get the function signature
        func = normal_tool.fn
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        assert 'name' in param_names, "name should be visible"


class TestMcpHiddenValidation:
    """Tests for validation of hidden arguments."""

    def test_hidden_arg_without_default_raises_error_via_directive(self):
        """Hidden argument without default should raise ValueError (via directive)."""
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api argument directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import GraphQLMCP, mcp_hidden

        if mcp_hidden is None:
            pytest.skip("mcp_hidden directive not available")

        class BadAPI:
            @field
            def bad_method(
                self,
                query: str,
                hidden_required: Annotated[str, mcp_hidden]  # No default! Should raise error
            ) -> str:
                return query

        api = GraphQLAPI(root_type=BadAPI, directives=[mcp_hidden])

        with pytest.raises(ValueError, match="must have defaults"):
            GraphQLMCP.from_api(api)

    def test_hidden_arg_without_default_raises_error_via_sdl(self):
        """Hidden argument without default via SDL should raise ValueError."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        # Schema with hidden arg that has no default
        schema = build_schema("""
            directive @mcpHidden on ARGUMENT_DEFINITION

            type Query {
                badQuery(query: String!, hiddenRequired: String! @mcpHidden): String
            }
        """)

        with pytest.raises(ValueError, match="must have defaults"):
            GraphQLMCP(schema=schema)


class TestHiddenArgsSDLDirective:
    """Tests for @mcpHidden directive via SDL (works with any library)."""

    def test_sdl_directive_hides_arguments(self):
        """@mcpHidden directive in SDL should hide arguments from MCP tools."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        # Define schema with @mcpHidden directive in SDL
        # This works with any library that builds from SDL
        schema = build_schema("""
            directive @mcpHidden on ARGUMENT_DEFINITION

            type Query {
                search(
                    query: String!
                    internalFlag: Boolean = false @mcpHidden
                    debugMode: Boolean = false @mcpHidden
                ): String
            }
        """)

        mcp = GraphQLMCP(schema=schema)

        # Get the search tool
        search_tool = None
        for tool_name, tool_info in mcp._tool_manager._tools.items():
            if tool_name == 'search':
                search_tool = tool_info
                break

        assert search_tool is not None, "search tool should exist"

        # Get the function signature
        func = search_tool.fn
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # 'query' should be visible
        assert 'query' in param_names, "query should be visible"

        # Hidden args should NOT be present (directive is in ast_node.directives)
        assert 'internalFlag' not in param_names, "internalFlag should be hidden via SDL directive"
        assert 'debugMode' not in param_names, "debugMode should be hidden via SDL directive"

    def test_sdl_graphql_schema_unchanged(self):
        """GraphQL schema should still have all arguments even when hidden from MCP."""
        from graphql import build_schema
        from graphql_mcp import GraphQLMCP

        schema = build_schema("""
            directive @mcpHidden on ARGUMENT_DEFINITION

            type Query {
                search(query: String!, internalFlag: Boolean = false @mcpHidden): String
            }
        """)

        mcp = GraphQLMCP(schema=schema)

        # GraphQL schema should still have the hidden arg
        assert 'internalFlag' in mcp.schema.query_type.fields['search'].args


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_to_snake_case(self):
        """Test snake_case conversion."""
        from graphql_mcp.server import _to_snake_case

        assert _to_snake_case("internalFlag") == "internal_flag"
        assert _to_snake_case("debugMode") == "debug_mode"
        assert _to_snake_case("simple") == "simple"
        assert _to_snake_case("ABC") == "a_b_c"

    def test_is_arg_hidden_plain_arg(self):
        """Test _is_arg_hidden returns False for plain arguments."""
        from graphql import GraphQLArgument, GraphQLString
        from graphql_mcp.server import _is_arg_hidden

        # Create a plain argument (no directive)
        arg = GraphQLArgument(GraphQLString)

        # Should not be hidden
        assert _is_arg_hidden(arg) is False

    def test_is_arg_hidden_with_directive(self):
        """Test _is_arg_hidden detects directive on argument."""
        if not _check_graphql_api_directive_support():
            pytest.skip("graphql-api argument directive support not available")

        from graphql_api import GraphQLAPI, field
        from graphql_mcp import mcp_hidden
        from graphql_mcp.server import _is_arg_hidden

        if mcp_hidden is None:
            pytest.skip("mcp_hidden directive not available")

        class TestAPI:
            @field
            def test_method(
                self,
                visible: str,
                hidden: Annotated[str, mcp_hidden] = ""
            ) -> str:
                return visible

        api = GraphQLAPI(root_type=TestAPI, directives=[mcp_hidden])
        schema = api.schema()

        # Get the arguments
        test_field = schema.query_type.fields['testMethod']
        visible_arg = test_field.args['visible']
        hidden_arg = test_field.args['hidden']

        # Test detection
        assert _is_arg_hidden(visible_arg) is False
        assert _is_arg_hidden(hidden_arg) is True

    def test_is_arg_hidden_with_sdl_directive(self):
        """Test _is_arg_hidden detects SDL directive on argument."""
        from graphql import build_schema
        from graphql_mcp.server import _is_arg_hidden

        schema = build_schema("""
            directive @mcpHidden on ARGUMENT_DEFINITION

            type Query {
                search(visible: String!, hidden: String = "" @mcpHidden): String
            }
        """)

        search_field = schema.query_type.fields['search']
        visible_arg = search_field.args['visible']
        hidden_arg = search_field.args['hidden']

        # Test detection
        assert _is_arg_hidden(visible_arg) is False
        assert _is_arg_hidden(hidden_arg) is True


class TestMcpHiddenDirectiveExport:
    """Tests for the mcp_hidden directive export."""

    def test_mcp_hidden_exported(self):
        """mcp_hidden should be exported from graphql_mcp."""
        from graphql_mcp import mcp_hidden

        # Should be available (None if graphql-api not installed)
        # Just verify we can import it
        assert mcp_hidden is None or hasattr(mcp_hidden, 'directive')

    def test_mcp_hidden_is_schema_directive(self):
        """mcp_hidden should be a SchemaDirective when graphql-api is installed."""
        try:
            from graphql_api.directives import SchemaDirective
        except ImportError:
            pytest.skip("graphql-api not installed")

        from graphql_mcp import mcp_hidden

        assert mcp_hidden is not None
        assert isinstance(mcp_hidden, SchemaDirective)
        assert mcp_hidden.directive.name == 'mcpHidden'
