"""Tests for graphql-mcp example servers.

Verifies each example's MCP tools and GraphQL HTTP endpoint work correctly.
"""

import json
from typing import cast

import httpx
import pytest
from fastmcp.client import Client
from mcp.types import TextContent


def get_result_text(result):
    """Helper to get text from result, handling different FastMCP API versions."""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


# ===========================================================
# Hello World
# ===========================================================


class TestHelloWorld:

    @pytest.fixture
    def server(self):
        from hello_world import server
        return server

    async def test_tool_exists(self, server):
        async with Client(server) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools} == {"hello"}

    async def test_hello_default(self, server):
        async with Client(server) as client:
            result = await client.call_tool("hello", {})
            assert get_result_text(result) == "Hello, World!"

    async def test_hello_custom_name(self, server):
        async with Client(server) as client:
            result = await client.call_tool("hello", {"name": "MCP"})
            assert get_result_text(result) == "Hello, MCP!"

    async def test_graphql_http(self):
        from hello_world import app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/graphql", json={"query": "{ hello }"})
            assert resp.status_code == 200
            assert resp.json()["data"]["hello"] == "Hello, World!"


# ===========================================================
# Task Manager
# ===========================================================


class TestTaskManager:

    @pytest.fixture
    def server(self):
        from task_manager import server
        return server

    async def test_tools_exist(self, server):
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert {"tasks", "task", "create_task", "update_status", "delete_task"} <= names

    async def test_list_tasks(self, server):
        async with Client(server) as client:
            result = await client.call_tool("tasks", {})
            data = json.loads(get_result_text(result))
            assert len(data) >= 4

    async def test_filter_by_status(self, server):
        async with Client(server) as client:
            result = await client.call_tool("tasks", {"status": "TODO"})
            data = json.loads(get_result_text(result))
            assert all(t["status"] == "TODO" for t in data)
            assert len(data) >= 1

    async def test_create_and_get_task(self, server):
        async with Client(server) as client:
            create_result = await client.call_tool("create_task", {
                "title": "Test Task",
                "description": "Created by test",
                "priority": "HIGH",
            })
            created = json.loads(get_result_text(create_result))
            assert created["title"] == "Test Task"
            assert "id" in created

            get_result = await client.call_tool("task", {"id": created["id"]})
            fetched = json.loads(get_result_text(get_result))
            assert fetched["title"] == "Test Task"

    async def test_graphql_http(self):
        from task_manager import app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/graphql", json={
                "query": "{ tasks { title status } }"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["tasks"]) >= 4


# ===========================================================
# Nested API
# ===========================================================


class TestNestedAPI:

    @pytest.fixture
    def server(self):
        from nested_api import server
        return server

    async def test_tools_exist(self, server):
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "categories" in names
            assert "category" in names
            assert "category_articles" in names  # nested tool
            assert "add_article" in names

    async def test_hidden_arg_not_exposed(self, server):
        """@mcpHidden argument should not appear in the MCP tool schema."""
        async with Client(server) as client:
            tools = await client.list_tools()
            articles_tool = next(t for t in tools if t.name == "category_articles")
            props = articles_tool.inputSchema.get("properties", {})
            assert "internal_score" not in props
            assert "internalScore" not in props

    async def test_list_categories(self, server):
        async with Client(server) as client:
            result = await client.call_tool("categories", {})
            data = json.loads(get_result_text(result))
            assert "python" in data
            assert "graphql" in data
            assert "mcp" in data

    async def test_get_category(self, server):
        async with Client(server) as client:
            result = await client.call_tool("category", {"name": "python"})
            data = json.loads(get_result_text(result))
            assert data["name"] == "python"
            assert data["articleCount"] == 2

    async def test_nested_tool_call(self, server):
        async with Client(server) as client:
            # Parent args are prefixed: category(name) → category_name
            result = await client.call_tool("category_articles", {
                "category_name": "python",
            })
            data = json.loads(get_result_text(result))
            assert isinstance(data, list)
            assert len(data) == 2
            assert any(a["title"] == "Async Python Patterns" for a in data)

    async def test_nested_tool_with_filter(self, server):
        async with Client(server) as client:
            # Parent args prefixed, leaf args keep their name
            result = await client.call_tool("category_articles", {
                "category_name": "python",
                "tag": "async",
            })
            data = json.loads(get_result_text(result))
            assert len(data) == 1
            assert data[0]["title"] == "Async Python Patterns"

    async def test_add_article_mutation(self, server):
        async with Client(server) as client:
            result = await client.call_tool("add_article", {
                "category": "testing",
                "title": "Test Article",
                "body": "Created by test",
                "tags": ["test"],
            })
            data = json.loads(get_result_text(result))
            assert data["title"] == "Test Article"
            assert "id" in data

    async def test_graphql_http(self):
        from nested_api import app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/graphql", json={
                "query": "{ categories }"
            })
            assert resp.status_code == 200
            assert "python" in resp.json()["data"]["categories"]


# ===========================================================
# Remote API
# ===========================================================


class TestRemoteAPI:

    @pytest.fixture
    def server(self):
        from remote_api import server
        return server

    async def test_tools_exist(self, server):
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "countries" in names

    async def test_countries_query(self, server):
        async with Client(server) as client:
            result = await client.call_tool("countries", {})
            data = json.loads(get_result_text(result))
            assert len(data) > 0
            assert "name" in data[0]


# ===========================================================
# Combined App
# ===========================================================


class TestCombinedApp:

    async def test_index_page(self):
        from app import app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "text/html" in resp.headers["content-type"]
            assert "/hello-world" in resp.text
            assert "/task-manager" in resp.text
            assert "/nested-api" in resp.text
            assert "/remote-api" in resp.text
