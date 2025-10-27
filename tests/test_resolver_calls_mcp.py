"""
Test resolvers that try to interact with MCP during execution.

This tests the scenario where a GraphQL resolver (tool implementation)
tries to call other MCP tools or list tools.
"""
import asyncio
import pytest
from fastmcp.client import Client

try:
    from graphql_api import GraphQLAPI
    HAS_GRAPHQL_API = True
except ImportError:
    HAS_GRAPHQL_API = False

from graphql_mcp.server import GraphQLMCP


def get_result_text(result):
    """Helper to extract text from result."""
    if hasattr(result, 'content'):
        return result.content[0].text
    else:
        return result[0].text


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_resolver_that_needs_schema_introspection():
    """
    Test a resolver that might trigger schema introspection during execution.
    """
    api = GraphQLAPI()

    call_count = {"value": 0}

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def increment_and_reflect(self) -> dict:
            """
            Increments a counter and returns metadata.
            This simulates a resolver that might inspect its own schema.
            """
            call_count["value"] += 1
            # In a real scenario, this might try to introspect the schema
            # or check available tools
            return {
                "count": call_count["value"],
                "type": "reflected"
            }

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Call the tool multiple times concurrently
        tasks = [
            client.call_tool("increment_and_reflect", {})
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert call_count["value"] == 10

        print("✅ Resolver with introspection-like behavior works")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_tool_creation():
    """
    Test creating multiple GraphQLMCP instances concurrently.
    This stresses the type mapping cache during initialization.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def test_tool(self, x: int) -> int:
            """Test tool."""
            return x

    async def create_and_list():
        """Create a server and list its tools."""
        server = GraphQLMCP.from_api(api, name="TestAPI")
        async with Client(server) as client:
            tools = await client.list_tools()
            return [t.name for t in tools]

    # Create multiple servers concurrently
    tasks = [create_and_list() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # All should have the same tools
    first = sorted(results[0])
    for result in results[1:]:
        assert sorted(result) == first

    print("✅ Concurrent server creation works")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_tool_that_uses_complex_return_type():
    """
    Test that calling a tool with a complex return type doesn't deadlock
    if the type mapping happens during call.
    """
    from pydantic import BaseModel

    api = GraphQLAPI()

    class ComplexResult(BaseModel):
        id: int
        data: dict
        items: list[str]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_complex_result(self, id: int) -> ComplexResult:
            """Returns complex result."""
            return ComplexResult(
                id=id,
                data={"key": "value"},
                items=["item1", "item2"]
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Call concurrently
        tasks = [
            client.call_tool("get_complex_result", {"id": i})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10

        print("✅ Complex return types work during concurrent calls")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_list_tools_immediately_after_creation():
    """
    Test listing tools immediately after server creation.
    This ensures type mapping completes properly during init.
    """
    from pydantic import BaseModel

    api = GraphQLAPI()

    class Data(BaseModel):
        value: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_data(self) -> Data:
            """Gets data."""
            return Data(value="test")

    # Create server
    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    # Immediately list tools from multiple clients
    async def immediate_list():
        async with Client(mcp_server) as client:
            return await client.list_tools()

    tasks = [immediate_list() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All should be identical
    first = sorted([t.name for t in results[0]])
    for result in results[1:]:
        tools = sorted([t.name for t in result])
        assert tools == first

    print("✅ Immediate list_tools after creation works")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_mixed_operations_on_new_server():
    """
    Test mixed operations (list_tools and tool calls) on a freshly created server.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def compute(self, x: int) -> int:
            """Compute."""
            return x * 2

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Mix list_tools and tool calls immediately
        tasks = []
        for i in range(20):
            if i % 2 == 0:
                tasks.append(client.list_tools())
            else:
                tasks.append(client.call_tool("compute", {"x": i}))

        results = await asyncio.gather(*tasks)
        assert len(results) == 20

        print("✅ Mixed operations on new server work")
