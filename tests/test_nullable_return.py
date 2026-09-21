"""A tool whose GraphQL field is nullable can answer null.

graphql-api turns `Optional[T]` into a nullable GraphQL type, and the tool's
return annotation used to be the bare `T` — nullability was dropped exactly
where it mattered. FastMCP then declared an output schema that null could
never satisfy, and a resolver returning None came back to the caller as
"Output validation error: outputSchema defined but no structured output
returned" — an error result for what the API defines as a normal answer.
Nested fields and arguments already carried their nullability; the top-level
return was the one place that did not.
"""
import pytest
from fastmcp.client import Client
from pydantic import BaseModel
from typing import Optional

from graphql_mcp.server import GraphQLMCP


class Thing(BaseModel):
    name: str
    size: Optional[int] = None


def _api():
    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def find_thing(self, name: str) -> Optional[Thing]:
            """A lookup that legitimately finds nothing."""
            return Thing(name=name, size=3) if name == "known" else None

        @api.field
        def find_label(self, name: str) -> Optional[str]:
            return name.upper() if name == "known" else None

        @api.field
        def find_things(self, name: str) -> Optional[list[Thing]]:
            return [Thing(name=name)] if name == "known" else None

        @api.field
        def the_thing(self) -> Thing:
            return Thing(name="always")

    return api


@pytest.mark.asyncio
async def test_a_nullable_object_field_returning_none_is_not_an_error():
    async with Client(GraphQLMCP.from_api(_api())) as client:
        result = await client.call_tool("find_thing", {"name": "unknown"}, raise_on_error=False)
    assert not result.is_error, [c.text for c in result.content if hasattr(c, "text")]
    assert result.data is None


@pytest.mark.asyncio
async def test_a_nullable_object_field_still_returns_the_object():
    async with Client(GraphQLMCP.from_api(_api())) as client:
        result = await client.call_tool("find_thing", {"name": "known"})
    assert not result.is_error
    found = result.structured_content
    # FastMCP wraps a nullable return as {"result": …}; either way the object is there.
    if isinstance(found, dict) and "result" in found:
        found = found["result"]
    assert found == {"name": "known", "size": 3}


@pytest.mark.asyncio
async def test_a_nullable_scalar_and_list_returning_none_are_not_errors():
    async with Client(GraphQLMCP.from_api(_api())) as client:
        for tool in ("find_label", "find_things"):
            result = await client.call_tool(tool, {"name": "unknown"}, raise_on_error=False)
            assert not result.is_error, tool
            assert result.data is None, tool


@pytest.mark.asyncio
async def test_a_non_null_object_field_keeps_its_direct_schema():
    """Only nullable returns gain the wrapper: a field declared `-> Thing` is
    still described by the object's own schema, as it always was."""
    async with Client(GraphQLMCP.from_api(_api())) as client:
        tools = {t.name: t for t in await client.list_tools()}
        result = await client.call_tool("the_thing", {})
    assert tools["the_thing"].outputSchema["properties"].keys() >= {"name", "size"}
    assert result.structured_content == {"name": "always", "size": None}


@pytest.mark.asyncio
async def test_a_nullable_return_declares_null_in_its_schema():
    async with Client(GraphQLMCP.from_api(_api())) as client:
        tools = {t.name: t for t in await client.list_tools()}
    schema = tools["find_thing"].outputSchema
    assert schema is not None
    # Wherever the object landed in the schema, null must be admissible next to it.
    result_schema = schema["properties"].get("result", schema)
    assert "anyOf" in result_schema and any(
        item.get("type") == "null" for item in result_schema["anyOf"]
    ), result_schema
