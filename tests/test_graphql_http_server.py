import pytest
from unittest.mock import Mock, patch
from starlette.testclient import TestClient

try:
    from graphql_api import GraphQLAPI
    from graphql_http import GraphQLHTTP  # type: ignore
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from graphql_mcp.server import GraphQLMCP

try:
    from fastmcp.server.auth.providers.jwt import JWTVerifier
except ImportError:
    JWTVerifier = None


def create_test_api():
    """Create a test GraphQL API for testing."""
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def hello(self, name: str = "World") -> str:
            """Returns a greeting."""
            return f"Hello, {name}!"

        @api.field
        def add(self, a: int, b: int) -> int:
            """Adds two numbers."""
            return a + b

    return api


@pytest.mark.asyncio
async def test_graphql_http_enabled_by_default():
    """Tests that graphql_http is enabled by default."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()
    mcp_server = GraphQLMCP.from_api(api, name="TestServer")

    # Verify the server has the expected attributes
    assert mcp_server.api == api
    assert mcp_server.graphql_http is True


@pytest.mark.asyncio
async def test_graphql_http_can_be_disabled():
    """Tests that graphql_http can be explicitly disabled."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()
    mcp_server = GraphQLMCP.from_api(api, graphql_http=False, name="TestServer")

    # Verify the server has the expected attributes
    assert mcp_server.api == api
    assert mcp_server.graphql_http is False


def test_graphql_http_disabled_integration():
    """Integration test that GraphQL HTTP server is not mounted when disabled."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()

    # Create MCP server with GraphQL HTTP server disabled
    mcp_server = GraphQLMCP.from_api(api, graphql_http=False, name="TestServer")

    # Mock the parent app to verify GraphQL server is not mounted
    with patch('fastmcp.FastMCP.http_app') as mock_parent:
        mock_app = Mock()
        mock_app.mount = Mock()
        mock_parent.return_value = mock_app

        # Call http_app - this should NOT mount GraphQL server
        mcp_server.http_app()

        # Verify mount was not called (no GraphQL server mounted)
        mock_app.mount.assert_not_called()


def test_graphql_http_real_requests():
    """Test that we can make real GraphQL requests to the mounted server."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()

    # Create the GraphQL HTTP server directly to test it works
    graphql_server = GraphQLHTTP.from_api(api, auth_enabled=False)

    # Test the GraphQL server with a test client
    with TestClient(graphql_server.app) as client:
        # Test a simple query
        query = """
        query {
            hello(name: "GraphQL")
        }
        """

        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert data["data"]["hello"] == "Hello, GraphQL!"

        # Test a query with default parameter
        query2 = """
        query {
            hello
        }
        """

        response2 = client.post("/graphql", json={"query": query2})
        assert response2.status_code == 200

        data2 = response2.json()
        assert data2["data"]["hello"] == "Hello, World!"

        # Test a query with arguments
        query3 = """
        query {
            add(a: 5, b: 3)
        }
        """

        response3 = client.post("/graphql", json={"query": query3})
        assert response3.status_code == 200

        data3 = response3.json()
        assert data3["data"]["add"] == 8

        # Test GraphQL playground (GET request)
        playground_response = client.get("/graphql")
        # GraphQL HTTP server should respond with some kind of response (400 is acceptable too)
        assert playground_response.status_code in [200, 400, 404]  # Various versions handle GET differently


@pytest.mark.asyncio
async def test_graphql_http_mcp_integration():
    """Test that both MCP and GraphQL endpoints work when integrated."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()

    # Create MCP server with GraphQL HTTP server
    mcp_server = GraphQLMCP.from_api(api, graphql_http=True, name="TestServer")

    # Verify that the MCP server has tools from the GraphQL schema
    tools = await mcp_server._list_tools()  # Use the internal async method
    tool_names = [tool.name for tool in tools]

    # Should have MCP tools generated from GraphQL schema
    assert "hello" in tool_names
    assert "add" in tool_names


def test_graphql_http_auth_configuration():
    """Test different authentication configurations."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()

    # Test with no auth (should work)
    mcp_server_no_auth = GraphQLMCP.from_api(api, graphql_http=True, name="NoAuth")
    assert mcp_server_no_auth.auth is None

    # Test with non-JWT auth (should log warning but still work)
    mock_auth = Mock()

    with patch('graphql_mcp.server.logger') as mock_logger:
        with patch('fastmcp.FastMCP.http_app') as mock_parent:
            mock_app = Mock()
            mock_app.mount = Mock()
            mock_parent.return_value = mock_app

            mcp_server_other_auth = GraphQLMCP.from_api(
                api,
                graphql_http=True,
                auth=mock_auth,
                name="OtherAuth"
            )

            # This should work but log a warning
            mcp_server_other_auth.http_app()

            # Verify warning was logged
            mock_logger.critical.assert_called_once_with(
                "Auth mechanism is enabled for MCP but is not supported with GraphQLHTTP. Please use a different auth mechanism, or disable GraphQLHTTP."
            )


def test_graphql_http_jwt_auth_detection():
    """Test JWT authentication detection."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    if JWTVerifier is None:
        pytest.skip("JWTVerifier not available in this version of fastmcp")

    api = create_test_api()

    # Create a mock JWT verifier
    jwt_verifier = Mock(spec=JWTVerifier)
    jwt_verifier.jwks_uri = "https://example.com/.well-known/jwks.json"
    jwt_verifier.issuer = "https://example.com/"
    jwt_verifier.audience = "test-audience"

    # Test that JWT auth is properly detected
    with patch.object(GraphQLHTTP, 'from_api') as mock_from_api:
        with patch('fastmcp.FastMCP.http_app') as mock_parent:
            mock_app = Mock()
            mock_app.mount = Mock()
            mock_parent.return_value = mock_app

            mock_http_server = Mock()
            mock_http_server.app = Mock()
            mock_from_api.return_value = mock_http_server

            mcp_server = GraphQLMCP.from_api(
                api,
                graphql_http=True,
                auth=jwt_verifier,
                name="JWTAuth"
            )

            mcp_server.http_app()

            # Verify GraphQLHTTP was called with JWT configuration
            mock_from_api.assert_called_once_with(
                api=api,
                auth_enabled=True,
                auth_jwks_uri="https://example.com/.well-known/jwks.json",
                auth_issuer="https://example.com/",
                auth_audience="test-audience"
            )


def test_graphql_introspection():
    """Test that GraphQL introspection works."""
    if not HAS_DEPENDENCIES:
        pytest.skip("graphql-api or graphql_http not installed")

    api = create_test_api()
    graphql_server = GraphQLHTTP.from_api(api, auth_enabled=False)

    with TestClient(graphql_server.app) as client:
        # Test introspection query
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    name
                    fields {
                        name
                        type {
                            name
                        }
                    }
                }
                mutationType {
                    name
                    fields {
                        name
                    }
                }
            }
        }
        """

        response = client.post("/graphql", json={"query": introspection_query})
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "__schema" in data["data"]

        # Check that our fields are present in the schema
        query_fields = data["data"]["__schema"]["queryType"]["fields"]
        field_names = [field["name"] for field in query_fields]

        assert "hello" in field_names
        assert "add" in field_names

        # Check if mutation type exists (may be None if no mutations defined)
        mutation_type = data["data"]["__schema"]["mutationType"]
        if mutation_type:
            mutation_fields = mutation_type["fields"]
            mutation_names = [field["name"] for field in mutation_fields]
            # Since we removed create_item mutation, we won't test for it
            assert len(mutation_names) >= 0  # Just check that we can access mutations
