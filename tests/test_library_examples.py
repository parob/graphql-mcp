"""
Tests for GraphQL library examples from README.

This test file ensures that the examples shown in the README work properly
with Strawberry, Ariadne, and Graphene GraphQL libraries.
"""

import json
import pytest
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast

from graphql_mcp.server import GraphQLMCP


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        # New API: result has .content attribute
        return cast(TextContent, result.content[0]).text
    else:
        # Old API: result is already the content list
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_strawberry_example():
    """Test the Strawberry example from the README."""
    try:
        import strawberry
    except ImportError:
        pytest.skip("strawberry not installed")

    @strawberry.type
    class Query:
        @strawberry.field(description="Say hello to someone.")
        def hello(self, name: str = "World") -> str:
            return f"Hello, {name}!"

    schema = strawberry.Schema(query=Query)

    # Expose as MCP tools
    server = GraphQLMCP(schema=schema._schema, name="Strawberry API")

    async with Client(server) as client:
        # Test tool listing
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "hello" in tool_names

        hello_tool = next(t for t in tools if t.name == "hello")
        assert hello_tool.description == "Say hello to someone."

        # Test with default parameter
        result = await client.call_tool("hello", {})
        assert get_result_text(result) == "Hello, World!"

        # Test with custom parameter
        result = await client.call_tool("hello", {"name": "Strawberry"})
        assert get_result_text(result) == "Hello, Strawberry!"


@pytest.mark.asyncio
async def test_ariadne_example():
    """Test the Ariadne example from the README."""
    try:
        from ariadne import make_executable_schema, QueryType
    except ImportError:
        pytest.skip("ariadne not installed")

    type_defs = """
        type Query {
            hello(name: String = "World"): String!
        }
    """

    query = QueryType()

    @query.field("hello")
    def resolve_hello(_, info, name="World"):
        return f"Hello, {name}!"

    schema = make_executable_schema(type_defs, query)

    # Expose as MCP tools
    server = GraphQLMCP(schema=schema, name="Ariadne API")

    async with Client(server) as client:
        # Test tool listing
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "hello" in tool_names

        # Test with default parameter
        result = await client.call_tool("hello", {})
        assert get_result_text(result) == "Hello, World!"

        # Test with custom parameter
        result = await client.call_tool("hello", {"name": "Ariadne"})
        assert get_result_text(result) == "Hello, Ariadne!"


@pytest.mark.asyncio
async def test_graphene_example():
    """Test the Graphene example from the README."""
    try:
        import graphene
    except ImportError:
        pytest.skip("graphene not installed")

    class Query(graphene.ObjectType):
        hello = graphene.String(name=graphene.String(default_value="World"))

        def resolve_hello(self, info, name):
            return f"Hello, {name}!"

    schema = graphene.Schema(query=Query)

    # Expose as MCP tools
    server = GraphQLMCP(schema=schema.graphql_schema, name="Graphene API")

    async with Client(server) as client:
        # Test tool listing
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "hello" in tool_names

        # Test with default parameter
        result = await client.call_tool("hello", {})
        assert get_result_text(result) == "Hello, World!"

        # Test with custom parameter
        result = await client.call_tool("hello", {"name": "Graphene"})
        assert get_result_text(result) == "Hello, Graphene!"


@pytest.mark.asyncio
async def test_strawberry_with_mutations():
    """Test Strawberry with both queries and mutations."""
    try:
        import strawberry
    except ImportError:
        pytest.skip("strawberry not installed")

    # Simple in-memory counter
    counter = {"value": 0}

    @strawberry.type
    class Query:
        @strawberry.field(description="Get the current counter value.")
        def get_counter(self) -> int:
            return counter["value"]

    @strawberry.type
    class Mutation:
        @strawberry.mutation(description="Increment the counter by the given amount.")
        def increment_counter(self, amount: int = 1) -> int:
            counter["value"] += amount
            return counter["value"]

        @strawberry.mutation(description="Reset the counter to zero.")
        def reset_counter(self) -> int:
            counter["value"] = 0
            return counter["value"]

    schema = strawberry.Schema(query=Query, mutation=Mutation)
    server = GraphQLMCP(schema=schema._schema, name="Counter API")

    async with Client(server) as client:
        # Test tool listing - should have query and mutations
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "get_counter" in tool_names
        assert "increment_counter" in tool_names
        assert "reset_counter" in tool_names

        # Reset counter
        result = await client.call_tool("reset_counter", {})
        assert get_result_text(result) == "0"

        # Get initial value
        result = await client.call_tool("get_counter", {})
        assert get_result_text(result) == "0"

        # Increment by default (1)
        result = await client.call_tool("increment_counter", {})
        assert get_result_text(result) == "1"

        # Increment by 5
        result = await client.call_tool("increment_counter", {"amount": 5})
        assert get_result_text(result) == "6"

        # Verify final value
        result = await client.call_tool("get_counter", {})
        assert get_result_text(result) == "6"


@pytest.mark.asyncio
async def test_ariadne_with_complex_types():
    """Test Ariadne with complex object types."""
    try:
        from ariadne import make_executable_schema, QueryType
    except ImportError:
        pytest.skip("ariadne not installed")

    type_defs = """
        type Book {
            id: ID!
            title: String!
            author: String!
            year: Int!
        }

        type Query {
            books: [Book!]!
            book(id: ID!): Book
        }
    """

    books_data = [
        {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien", "year": 1937},
        {"id": "2", "title": "1984", "author": "George Orwell", "year": 1949},
    ]

    query = QueryType()

    @query.field("books")
    def resolve_books(_, info):
        return books_data

    @query.field("book")
    def resolve_book(_, info, id):
        return next((b for b in books_data if b["id"] == id), None)

    schema = make_executable_schema(type_defs, query)
    server = GraphQLMCP(schema=schema, name="Books API")

    async with Client(server) as client:
        # Test listing all books
        result = await client.call_tool("books", {})
        data = json.loads(get_result_text(result))
        assert len(data) == 2
        assert data[0]["title"] == "The Hobbit"
        assert data[0]["year"] == 1937

        # Test getting a specific book
        result = await client.call_tool("book", {"id": "2"})
        data = json.loads(get_result_text(result))
        assert data["title"] == "1984"
        assert data["author"] == "George Orwell"


@pytest.mark.asyncio
async def test_graphene_with_complex_types():
    """Test Graphene with complex object types and arguments."""
    try:
        import graphene
    except ImportError:
        pytest.skip("graphene not installed")

    # In-memory user data
    users_data = {
        "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
        "2": {"id": "2", "name": "Bob", "email": "bob@example.com"},
    }

    class User(graphene.ObjectType):
        id = graphene.ID()
        name = graphene.String()
        email = graphene.String()

    class Query(graphene.ObjectType):
        users = graphene.List(User, description="Get all users")
        user = graphene.Field(User, id=graphene.ID(required=True), description="Get a user by ID")

        def resolve_users(self, info):
            return [User(**u) for u in users_data.values()]

        def resolve_user(self, info, id):
            user_data = users_data.get(id)
            return User(**user_data) if user_data else None

    class Mutation(graphene.ObjectType):
        create_user = graphene.Field(
            User,
            name=graphene.String(required=True),
            email=graphene.String(required=True),
            description="Create a new user"
        )

        def resolve_create_user(self, info, name, email):
            new_id = str(len(users_data) + 1)
            new_user = {"id": new_id, "name": name, "email": email}
            users_data[new_id] = new_user
            return User(**new_user)

    schema = graphene.Schema(query=Query, mutation=Mutation)
    server = GraphQLMCP(schema=schema.graphql_schema, name="Users API")

    async with Client(server) as client:
        # Test listing users
        result = await client.call_tool("users", {})
        data = json.loads(get_result_text(result))
        assert len(data) == 2

        # Test getting specific user
        result = await client.call_tool("user", {"id": "1"})
        data = json.loads(get_result_text(result))
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"

        # Test creating a user
        result = await client.call_tool("create_user", {
            "name": "Charlie",
            "email": "charlie@example.com"
        })
        data = json.loads(get_result_text(result))
        assert data["name"] == "Charlie"
        assert data["email"] == "charlie@example.com"
        assert data["id"] == "3"


@pytest.mark.asyncio
async def test_all_libraries_produce_same_tools():
    """Test that different libraries produce equivalent MCP tools for the same API."""

    # Skip if any library is not installed
    try:
        import strawberry
        from ariadne import make_executable_schema, QueryType
        import graphene
    except ImportError:
        pytest.skip("Not all libraries (strawberry, ariadne, graphene) are installed")

    # Strawberry version
    @strawberry.type
    class StrawberryQuery:
        @strawberry.field(description="Greet someone by name.")
        def greet(self, name: str) -> str:
            return f"Hello, {name}!"

    strawberry_schema = strawberry.Schema(query=StrawberryQuery)
    strawberry_server = GraphQLMCP(schema=strawberry_schema._schema, name="Strawberry")

    # Ariadne version
    ariadne_type_defs = """
        type Query {
            "Greet someone by name."
            greet(name: String!): String!
        }
    """
    ariadne_query = QueryType()

    @ariadne_query.field("greet")
    def ariadne_resolve_greet(_, info, name):
        return f"Hello, {name}!"

    ariadne_schema = make_executable_schema(ariadne_type_defs, ariadne_query)
    ariadne_server = GraphQLMCP(schema=ariadne_schema, name="Ariadne")

    # Graphene version
    class GrapheneQuery(graphene.ObjectType):
        greet = graphene.String(
            name=graphene.String(required=True),
            description="Greet someone by name."
        )

        def resolve_greet(self, info, name):
            return f"Hello, {name}!"

    graphene_schema = graphene.Schema(query=GrapheneQuery)
    graphene_server = GraphQLMCP(schema=graphene_schema.graphql_schema, name="Graphene")

    # Test all three produce the same result
    async with Client(strawberry_server) as client:
        result = await client.call_tool("greet", {"name": "Test"})
        strawberry_result = get_result_text(result)

    async with Client(ariadne_server) as client:
        result = await client.call_tool("greet", {"name": "Test"})
        ariadne_result = get_result_text(result)

    async with Client(graphene_server) as client:
        result = await client.call_tool("greet", {"name": "Test"})
        graphene_result = get_result_text(result)

    # All should produce the same output
    assert strawberry_result == ariadne_result == graphene_result == "Hello, Test!"
