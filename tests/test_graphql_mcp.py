import json
import pytest
import enum

from pydantic import BaseModel
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast

from graphql_api import field
from graphql_mcp.server import add_tools_from_schema, GraphQLMCP


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        # New API: result has .content attribute
        return cast(TextContent, result.content[0]).text
    else:
        # Old API: result is already the content list
        return cast(TextContent, result[0]).text


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

    # Ensure the schema actually mapped the argument to a GraphQL Enum
    try:
        from graphql import GraphQLEnumType, get_named_type
        arg_type = get_named_type(schema.query_type.fields["echoPreference"].args["key"].type)  # type: ignore[attr-defined]
        if not isinstance(arg_type, GraphQLEnumType):
            pytest.skip("PreferenceKey was not mapped to a GraphQL Enum by graphql-api; cannot assert instance coercion")
    except Exception:
        pass

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test query
        result = await client.call_tool("hello", {"name": "World"})
        assert get_result_text(result) == "Hello, World"

        # Test mutation
        result = await client.call_tool("add", {"a": 5, "b": 3})
        assert get_result_text(result) == "8"

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
        data = json.loads(get_result_text(result))
        assert data["name"] == "Douglas Adams"
        assert data["book"]["title"] == "The Hitchhiker's Guide to the Galaxy"


@pytest.mark.asyncio
async def test_from_graphql_schema_nested_mutation():
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

        @api.field(mutable=True)
        def set_title(self, title: str) -> str:
            return "Title set to " + title

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def book(self) -> Book:
            return Book()

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("book_set_title", {"title": "Test"})
        data = get_result_text(result)
        assert data == "Title set to Test"


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
        data = json.loads(get_result_text(result))
        assert len(data) == 2
        assert data[0]["name"] == "Task 1"

        # 2. Test query with arguments
        result = await client.call_tool("item", {"id": 1})
        data = json.loads(get_result_text(result))
        assert data["name"] == "Task 1"
        assert data["status"] == "PENDING"

        # 3. Test mutation
        result = await client.call_tool("update_item_status", {"id": 1, "status": "COMPLETED"})
        data = json.loads(get_result_text(result))
        assert data["status"] == "COMPLETED"

        # 4. Test enum argument
        result = await client.call_tool("filter_items", {"completed": True, "status": "COMPLETED"})
        data = json.loads(get_result_text(result))
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
        assert get_result_text(result_existing) == "existing"

        result_new = await client.call_tool("new_tool", {})
        assert get_result_text(result_new) == "new"


@pytest.mark.asyncio
async def test_from_schema_class_method():
    """
    Tests the GraphQLMCP.from_schema class method.
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

    mcp_server = GraphQLMCP.from_schema(schema, name="TestServer")
    assert isinstance(mcp_server, FastMCP)
    assert mcp_server.name == "TestServer"

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert "hello" in [t.name for t in tools]

        result = await client.call_tool("hello", {})
        assert get_result_text(result) == "world"


@pytest.mark.asyncio
async def test_from_graphql_api_class_method():
    """
    Tests the GraphQLMCP.from_graphql_api class method.
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

    mcp_server = GraphQLMCP.from_api(api, name="TestFromAPI")
    assert isinstance(mcp_server, FastMCP)
    assert mcp_server.name == "TestFromAPI"

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert "hello_from_api" in [t.name for t in tools]

        result = await client.call_tool("hello_from_api", {"name": "Works"})
        assert get_result_text(result) == "Hello, Works"


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
        assert get_result_text(result) == "Hello, core"

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
        data = json.loads(get_result_text(result))
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
        data = json.loads(get_result_text(result))
        assert data["name"] == "A Pydantic Item"
        assert data["price"] == 42.0
        assert data["isOffer"] is True


@pytest.mark.asyncio
async def test_deep_nested_mutation():
    """Validates tools generated for mutations nested three levels deep."""

    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type
    class Post:
        def __init__(self):
            self._title = "Original"

        @api.field
        def title(self) -> str:
            return self._title

        @api.field(mutable=True)
        def update_title(self, new_title: str) -> str:
            self._title = new_title
            return self._title

    @api.type
    class User:
        @api.field
        def posts(self) -> Post:
            return Post()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def user(self) -> User:
            return User()

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("user_posts_update_title", {"newTitle": "Updated"})
        assert get_result_text(result) == "Updated"


@pytest.mark.asyncio
async def test_deep_nested_query_with_args():
    """Validates tools generated for deep nested queries with arguments."""

    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type
    class CalculatorLevel2:
        @api.field
        def add(self, a: int, b: int) -> int:
            return a + b

    @api.type
    class CalculatorLevel1:
        @api.field
        def calc2(self) -> CalculatorLevel2:
            return CalculatorLevel2()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def calc1(self) -> CalculatorLevel1:
            return CalculatorLevel1()

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("calc1_calc2_add", {"a": 10, "b": 20})
        data = json.loads(get_result_text(result))
        assert data == 30


@pytest.mark.asyncio
async def test_from_graphql_schema_async_field():
    """
    Tests the schema mapping with an async field.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        async def hello_async(self, name: str) -> str:
            """Returns a greeting asynchronously."""
            import asyncio
            await asyncio.sleep(0.01)
            return f"Hello, {name}"

    schema, _ = api.build_schema()

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        result = await client.call_tool("hello_async", {"name": "World"})
        assert get_result_text(result) == "Hello, World"


@pytest.mark.asyncio
async def test_enum_argument_mcp_vs_graphql_mapping():
    """
    Reproduces that GraphQL-generated tools deliver enum args as strings while
    a directly-registered MCP tool with Enum annotation receives an Enum.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class PreferenceKey(enum.Enum):
        AI_MODEL = "a"
        TOOLS_ENABLED = "b"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
            # Returns whether we actually received the Enum instance
            return isinstance(key, PreferenceKey)

    mcp_server = GraphQLMCP(api=api)

    # Add a direct MCP tool that expects the Enum annotation
    @mcp_server.tool
    def set_preference(key: PreferenceKey, value: str) -> bool:
        return isinstance(key, PreferenceKey)

    async with Client(mcp_server) as client:
        # GraphQL-generated tool: currently gets a string for the enum
        r1 = await client.call_tool("set_preference_test", {"key": "a", "value": "x"})
        assert get_result_text(r1).lower() == "true"

        # Direct MCP tool: pass the enum VALUE; FastMCP should coerce to Enum instance
        r2 = await client.call_tool("set_preference", {"key": "a", "value": "x"})
        assert get_result_text(r2).lower() == "true"


@pytest.mark.asyncio
async def test_string_enum_argument_mcp_vs_graphql_mapping():
    """
    Reproduces that GraphQL-generated tools deliver enum args as strings while
    a directly-registered MCP tool with Enum annotation receives an Enum.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class PreferenceKey(str, enum.Enum):
        AI_MODEL = "a"
        TOOLS_ENABLED = "b"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
            # Returns whether we actually received the Enum instance
            return isinstance(key, PreferenceKey)

    mcp_server = GraphQLMCP(api=api)

    # Add a direct MCP tool that expects the Enum annotation
    @mcp_server.tool
    def set_preference(key: PreferenceKey, value: str) -> bool:
        return isinstance(key, PreferenceKey)

    async with Client(mcp_server) as client:
        # GraphQL-generated tool: currently gets a string for the enum
        r1 = await client.call_tool("set_preference_test", {"key": "a", "value": "x"})
        assert get_result_text(r1).lower() == "true"

        # Direct MCP tool: pass the enum VALUE; FastMCP should coerce to Enum instance
        r2 = await client.call_tool("set_preference", {"key": "a", "value": "x"})
        assert get_result_text(r2).lower() == "true"


@pytest.mark.asyncio
async def test_int_enum_argument_mcp_vs_graphql_mapping():
    """
    Reproduces that GraphQL-generated tools deliver enum args as strings while
    a directly-registered MCP tool with Enum annotation receives an Enum.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class PreferenceKey(enum.Enum):
        AI_MODEL = 1
        TOOLS_ENABLED = 2

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
            # Returns whether we actually received the Enum instance
            return isinstance(key, PreferenceKey)

    mcp_server = GraphQLMCP(api=api)

    # Add a direct MCP tool that expects the Enum annotation
    @mcp_server.tool
    def set_preference(key: PreferenceKey, value: str) -> bool:
        return isinstance(key, PreferenceKey)

    async with Client(mcp_server) as client:
        # GraphQL-generated tool: currently gets a string for the enum
        r1 = await client.call_tool("set_preference_test", {"key": 1, "value": "x"})
        assert get_result_text(r1).lower() == "true"

        # Direct MCP tool: pass the enum VALUE; FastMCP should coerce to Enum instance
        r2 = await client.call_tool("set_preference", {"key": 1, "value": "x"})
        assert get_result_text(r2).lower() == "true"


@pytest.mark.asyncio
async def test_dict_mcp_vs_graphql_mapping():
    """
    Reproduces that GraphQL-generated tools deliver enum args as strings while
    a directly-registered MCP tool with Enum annotation receives an Enum.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_preference_gql(self) -> dict:
            # Returns whether we actually received the Enum instance
            return {"key": "ai_model", "value": "x"}

    mcp_server = GraphQLMCP(api=api)

    # Add a direct MCP tool that expects the Enum annotation
    @mcp_server.tool
    def get_preference() -> dict:
        return {"key": "ai_model", "value": "x"}

    async with Client(mcp_server) as client:
        # GraphQL-generated tool: currently gets a string for the enum
        r1 = await client.call_tool("get_preference_gql", {})
        assert get_result_text(r1) == '{"key": "ai_model", "value": "x"}'

        # Direct MCP tool: pass the enum VALUE; FastMCP should coerce to Enum instance
        r2 = await client.call_tool("get_preference", {})
        # Normalize JSON format - FastMCP may use pretty-printing
        import json
        result_text = get_result_text(r2)
        expected_data = {"key": "ai_model", "value": "x"}
        actual_data = json.loads(result_text)
        assert actual_data == expected_data


@pytest.mark.asyncio
async def test_enum_argument_core_accepts_string():
    """
    Tests that a GraphQL enum argument (string-valued) can be passed as a plain string.
    """
    from graphql import (
        GraphQLSchema,
        GraphQLObjectType,
        GraphQLField,
        GraphQLArgument,
        GraphQLEnumType,
        GraphQLString,
    )

    # Define a string-valued enum in GraphQL Core
    StatusEnum = GraphQLEnumType(
        name="Status",
        values={
            "PENDING": "PENDING",
            "COMPLETED": "COMPLETED",
        },
    )

    # Resolver echoes back the enum value it receives
    def resolve_echo_status(root, info, status):
        return status

    query_type = GraphQLObjectType(
        name="Query",
        fields={
            "echoStatus": GraphQLField(
                GraphQLString,
                args={"status": GraphQLArgument(StatusEnum)},
                resolve=resolve_echo_status,
            )
        },
    )

    schema = GraphQLSchema(query=query_type)

    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Pass the enum as a plain string; GraphQL should accept it via variables
        result = await client.call_tool("echo_status", {"status": "COMPLETED"})
        assert get_result_text(result) == "COMPLETED"
