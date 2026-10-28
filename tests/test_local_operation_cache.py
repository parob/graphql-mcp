"""Cached tool documents must still execute and coerce each invocation."""

import asyncio
from contextvars import ContextVar
from unittest.mock import patch

import pytest
from graphql import GraphQLError, build_schema

from graphql_mcp import server


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [False, True])
async def test_cached_mutation_executes_with_fresh_variables(nested):
    schema = build_schema("""
        type Query { unused: Int }
        type Mutation { add(amount: Int!, multiplier: Int!): Int! }
    """)
    total = 0

    def add(_root, _info, amount, multiplier):
        nonlocal total
        total += amount * multiplier
        return total

    field = schema.mutation_type.fields["add"]
    field.resolve = add
    tool = (server._create_recursive_tool_function([("add", field)], "mutation", schema)
            if nested else server._create_tool_function("add", field, schema, is_mutation=True))

    with patch.object(server, "parse", wraps=server.parse) as parse, \
            patch.object(server, "validate", wraps=server.validate) as validate:
        assert await tool(amount=2, multiplier=3) == 6
        assert await tool(multiplier=4, amount=3) == 18
        # Coercion still runs on cache hits; invalid values cannot execute.
        with pytest.raises(GraphQLError, match="Int cannot represent"):
            await tool(amount="invalid", multiplier=1)
        assert total == 18
        assert await tool(amount=1, multiplier=1) == 19
        assert parse.call_count == validate.call_count == 1


@pytest.mark.asyncio
async def test_cached_optional_argument_shapes_preserve_omitted_and_null():
    schema = build_schema("type Query { search(term: String, limit: Int = 10): String! }")
    received = []

    def search(_root, _info, **kwargs):
        received.append(kwargs)
        return "ok"

    field = schema.query_type.fields["search"]
    field.resolve = search
    tool = server._create_tool_function("search", field, schema)
    with patch.object(server, "parse", wraps=server.parse) as parse:
        for _ in range(2):
            await tool()
            await tool(term=None)
            await tool(term="hello")
            await tool(limit=2, term="hello")
            await tool(term="world", limit=3)
        assert parse.call_count == 3
    assert received == [
        {"limit": 10}, {"term": None, "limit": 10},
        {"term": "hello", "limit": 10}, {"term": "hello", "limit": 2},
        {"term": "world", "limit": 3},
    ] * 2


@pytest.mark.asyncio
async def test_cached_nested_tool_keeps_concurrent_request_contexts_separate():
    caller = ContextVar("caller")
    schema = build_schema("""
        type Query { account(id: Int!): Account! }
        type Account { echo(value: String!): String! }
    """)
    account = schema.query_type.fields["account"]
    echo = schema.type_map["Account"].fields["echo"]
    account.resolve = lambda _root, _info, id: id

    async def resolve(root, _info, value):
        await asyncio.sleep(0)
        return f"{root}:{caller.get()}:{value}"

    echo.resolve = resolve
    tool = server._create_recursive_tool_function(
        [("account", account), ("echo", echo)], "query", schema)

    async def call(i):
        token = caller.set(f"caller-{i}")
        try:
            return await tool(account_id=i, value=f"value-{i}")
        finally:
            caller.reset(token)

    assert await asyncio.gather(*(call(i) for i in range(20))) == [
        f"{i}:caller-{i}:value-{i}" for i in range(20)
    ]


@pytest.mark.asyncio
async def test_documents_do_not_cross_schema_instances():
    tools = []
    for value in ("first", "second"):
        schema = build_schema("type Query { value: String! }")
        field = schema.query_type.fields["value"]
        field.resolve = lambda _root, _info, value=value: value
        tools.append(server._create_tool_function("value", field, schema))
    for _ in range(2):
        assert [await tool() for tool in tools] == ["first", "second"]


@pytest.mark.asyncio
async def test_argument_shape_cache_is_bounded():
    arguments = ", ".join(f"a{i}: Int" for i in range(8))
    schema = build_schema(f"type Query {{ count({arguments}): Int! }}")
    field = schema.query_type.fields["count"]
    field.resolve = lambda _root, _info, **kwargs: len(kwargs)
    tool = server._create_tool_function("count", field, schema)
    with patch.object(server, "parse", wraps=server.parse) as parse:
        for mask in range(129):
            kwargs = {f"a{i}": i for i in range(8) if mask & (1 << i)}
            assert await tool(**kwargs) == len(kwargs)
        assert await tool() == 0
        # The oldest shape is evicted rather than accumulating indefinitely.
        assert parse.call_count == 130


@pytest.mark.asyncio
async def test_invalid_generated_document_never_executes_or_caches_errors():
    schema = build_schema("type Query { value: String! }")
    calls = []
    field = schema.query_type.fields["value"]
    field.resolve = lambda *_: calls.append("called") or "ok"
    # Exercise validation, even if a future selection builder emits bad GraphQL.
    with patch.object(server, "_build_selection_set", return_value="{ missing }"):
        tool = server._create_tool_function("value", field, schema)
    errors = []
    for _ in range(2):
        with pytest.raises(GraphQLError, match="must not have a selection") as error:
            await tool()
        errors.append(error.value)
    assert calls == []
    assert errors[0] is not errors[1]
