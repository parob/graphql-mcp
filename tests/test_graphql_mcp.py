import json
import pytest
import enum

from pydantic import BaseModel
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast

from graphql_api import field
from graphql_mcp.server import add_tools_from_schema, GraphQLMCPServer


@pytest.mark.asyncio
async def test_from_graphql_schema():
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def hello(self, name: str) -> str:
            """Returns a greeting."""
            return f"Hello, {name}"

        @api.field(mutable=True)
        def add(self, a: int, b: int) -> int:
            """Adds two numbers."""
            return a + b

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test query
        result = await client.call_tool("hello", {"name": "World"})
        assert cast(TextContent, result[0]).text == "Hello, World"

        # Test mutation
        result = await client.call_tool("add", {"a": 5, "b": 3})
        assert cast(TextContent, result[0]).text == "8"

        # Test tool listing
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "hello" in tool_names
        assert "add" in tool_names

        hello_tool = next(t for t in tools if t.name == "hello")
        assert hello_tool.description == "Returns a greeting."

        add_tool = next(t for t in tools if t.name == "add")
        assert add_tool.description == "Adds two numbers."


@pytest.mark.asyncio
async def test_from_graphql_schema_nested():
    """
    Tests the schema mapping with a nested object type.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")
    api = GraphQLAPI()

    @api.type
    class Book:
        @api.field
        def title(self) -> str:
            return "The Hitchhiker's Guide to the Galaxy"

    @api.type
    class Author:
        @api.field
        def name(self) -> str:
            return "Douglas Adams"

        @api.field
        def book(self) -> Book:
            return Book()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def author(self) -> Author:
            return Author()

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("author", {})
        data = json.loads(cast(TextContent, result[0]).text)
        assert data["name"] == "Douglas Adams"
        assert data["book"]["title"] == "The Hitchhiker's Guide to the Galaxy"


@pytest.mark.asyncio
async def test_from_graphql_schema_advanced():
    """
    Tests more advanced schema features like enums, lists, and mutations on data.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")
    api = GraphQLAPI()

    class Status(enum.Enum):
        PENDING = "PENDING"
        COMPLETED = "COMPLETED"

    # In-memory "database"
    items_db = {
        1: {"id": 1, "name": "Task 1", "completed": False, "status": Status.PENDING},
        2: {"id": 2, "name": "Task 2", "completed": True, "status": Status.COMPLETED},
    }

    @api.type
    class Item:
        def __init__(self, **data):
            self._data = data

        @api.field
        def id(self) -> int:
            return self._data["id"]

        @api.field
        def name(self) -> str:
            return self._data["name"]

        @api.field
        def completed(self) -> bool:
            return self._data["completed"]

        @api.field
        def status(self) -> Status:
            return self._data["status"]

        @api.field(mutable=True)
        def rename(self, new_name: str) -> 'Item':
            """Updates the status of an item."""
            self._data["name"] = new_name
            return self

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def items(self) -> list[Item]:
            """Returns all items."""
            return [Item(**item_data) for item_data in items_db.values()]

        @api.field
        def item(self, id: int) -> Item | None:
            """Returns a single item by ID."""
            if id in items_db:
                return Item(**items_db[id])
            return None

        @api.field
        def filter_items(
            self, completed: bool, status: str | None = None
        ) -> list[Item]:
            """Filters items by completion status and optionally by enum status."""
            filtered_data = [
                i for i in items_db.values() if i["completed"] == completed
            ]
            if status:
                filtered_data = [
                    i for i in filtered_data if i["status"].value == status
                ]
            return [Item(**i) for i in filtered_data]

        @api.field(mutable=True)
        def update_item_status(self, id: int, status: str) -> Item:
            """Updates the status of an item."""
            if id not in items_db:
                raise ValueError(f"Item with ID {id} not found.")
            items_db[id]["status"] = Status(status)
            return Item(**items_db[id])

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # 1. Test list return
        result = await client.call_tool("items", {})
        data = json.loads(cast(TextContent, result[0]).text)
        assert len(data) == 2
        assert data[0]["name"] == "Task 1"

        # 2. Test query with arguments
        result = await client.call_tool("item", {"id": 1})
        data = json.loads(cast(TextContent, result[0]).text)
        assert data["name"] == "Task 1"
        assert data["status"] == "PENDING"

        # 3. Test mutation
        result = await client.call_tool("update_item_status", {"id": 1, "status": "COMPLETED"})
        data = json.loads(cast(TextContent, result[0]).text)
        assert data["status"] == "COMPLETED"

        # 4. Test enum argument
        result = await client.call_tool("filter_items", {"completed": True, "status": "COMPLETED"})
        data = json.loads(cast(TextContent, result[0]).text)
        if isinstance(data, dict):
            data = [data]
        assert len(data) == 1
        assert data[0]["name"] == "Task 2"

        # 5. Verify that mutations on nested objects are NOT exposed as top-level tools.
        # The `graphql-api` library only creates top-level mutations from methods
        # on the class marked `is_root_type=True`. The `rename` method on the
        # `Item` type is therefore not mapped to a top-level mutation.
        all_tools = await client.list_tools()
        assert "rename" not in [tool.name for tool in all_tools]
        assert "rename_item" not in [tool.name for tool in all_tools]


@pytest.mark.asyncio
async def test_from_graphql_schema_with_existing_server():
    """
    Tests that the schema mapping can be applied to an existing FastMCP server.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def new_tool(self) -> str:
            return "new"

    schema, _ = api.build_schema()

    # 1. Create a server with a pre-existing tool
    mcp_server = FastMCP()

    @mcp_server.tool
    def existing_tool() -> str:
        """An existing tool."""
        return "existing"

    # 2. Populate the server from the schema
    add_tools_from_schema(schema, server=mcp_server)

    # 3. Verify both the old and new tools exist
    async with Client(mcp_server) as client:
        all_tools = await client.list_tools()
        tool_names = [tool.name for tool in all_tools]
        assert "existing_tool" in tool_names
        assert "new_tool" in tool_names

        # 4. Verify both tools are callable
        result_existing = await client.call_tool("existing_tool", {})
        assert cast(TextContent, result_existing[0]).text == "existing"

        result_new = await client.call_tool("new_tool", {})
        assert cast(TextContent, result_new[0]).text == "new"


@pytest.mark.asyncio
async def test_from_schema_class_method():
    """
    Tests the GraphQLMCPServer.from_schema class method.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def hello(self) -> str:
            return "world"

    schema, _ = api.build_schema()

    mcp_server = GraphQLMCPServer.from_schema(schema, name="TestServer")
    assert isinstance(mcp_server, FastMCP)
    assert mcp_server.name == "TestServer"

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert "hello" in [t.name for t in tools]

        result = await client.call_tool("hello", {})
        assert cast(TextContent, result[0]).text == "world"


@pytest.mark.asyncio
async def test_from_graphql_api_class_method():
    """
    Tests the GraphQLMCPServer.from_graphql_api class method.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api is not installed")

    class MyAPI:

        @field
        def hello_from_api(self, name: str = "Test") -> str:
            return f"Hello, {name}"

    api = GraphQLAPI(root_type=MyAPI)

    mcp_server = GraphQLMCPServer.from_api(api, name="TestFromAPI")
    assert isinstance(mcp_server, FastMCP)
    assert mcp_server.name == "TestFromAPI"

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert "hello_from_api" in [t.name for t in tools]

        result = await client.call_tool("hello_from_api", {"name": "Works"})
        assert cast(TextContent, result[0]).text == "Hello, Works"


@pytest.mark.asyncio
async def test_from_graphql_schema_core_only():
    """
    Tests that the schema mapping works with a schema built using only graphql-core.
    """
    from graphql import (
        GraphQLSchema,
        GraphQLObjectType,
        GraphQLField,
        GraphQLString,
        GraphQLArgument,
    )

    def resolve_hello(root, info, name="world"):
        return f"Hello, {name}"

    query_type = GraphQLObjectType(
        name="Query",
        fields={
            "hello": GraphQLField(
                GraphQLString,
                args={"name": GraphQLArgument(GraphQLString, default_value="world")},
                resolve=resolve_hello,
            )
        },
    )

    schema = GraphQLSchema(query=query_type)

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test query
        result = await client.call_tool("hello", {"name": "core"})
        assert cast(TextContent, result[0]).text == "Hello, core"

        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "hello"


@pytest.mark.asyncio
async def test_error_handling():
    """Tests that GraphQL errors are raised as exceptions."""
    from graphql import (
        GraphQLSchema,
        GraphQLObjectType,
        GraphQLField,
        GraphQLString,
    )
    from fastmcp.exceptions import ToolError

    def resolve_error(root, info):
        raise ValueError("This is a test error")

    query_type = GraphQLObjectType(
        name="Query",
        fields={
            "error_field": GraphQLField(
                GraphQLString,
                resolve=resolve_error,
            )
        },
    )
    schema = GraphQLSchema(query=query_type)
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        with pytest.raises(ToolError, match="This is a test error"):
            await client.call_tool("error_field", {})


@pytest.mark.asyncio
async def test_from_graphql_schema_with_pydantic_input():
    """
    Tests that a mutation with a pydantic model as input is correctly handled.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class CreateItemInput(BaseModel):
        name: str
        price: float

    @api.type
    class Item:
        @api.field
        def name(self) -> str:
            return "Test Item"

        @api.field
        def price(self) -> float:
            return 12.34

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_item(self, input: dict) -> Item:
            """Creates an item."""
            # In a real scenario, you'd use the input to create the item.
            # Here we just return a dummy item to verify the tool call.
            if isinstance(input, str):
                input = json.loads(input)
            assert input["name"] == "My Pydantic Item"
            assert input["price"] == 99.99
            return Item()

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        input_data = CreateItemInput(name="My Pydantic Item", price=99.99)
        result = await client.call_tool("create_item", {"input": input_data})
        data = json.loads(cast(TextContent, result[0]).text)
        assert data["name"] == "Test Item"
        assert data["price"] == 12.34


@pytest.mark.asyncio
async def test_from_graphql_schema_with_pydantic_output():
    """
    Tests that a query that returns a pydantic model is correctly handled.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ItemOutput(BaseModel):
        name: str
        price: float
        is_offer: bool = False

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_item(self) -> ItemOutput:
            """Gets an item."""
            return ItemOutput(name="A Pydantic Item", price=42.0, is_offer=True)

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("get_item", {})
        data = json.loads(cast(TextContent, result[0]).text)
        assert data["name"] == "A Pydantic Item"
        assert data["price"] == 42.0
        assert data["isOffer"] is True
