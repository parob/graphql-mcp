"""
Regression tests for the type-mapping cache key.

The cache that backs ``_map_graphql_type_to_python_type`` used to key object
and input-object types by ``f"{name}_{id(type)}"``. ``id()`` is only unique
among *live* objects, so a garbage-collected GraphQL type can have its memory
address reused by a differently-shaped type with the same name. That produced
a stale cache hit — e.g. a ``User`` model with ``{name, age}`` returned for a
later, unrelated ``User`` with ``{name, nickname}``. The failure was
environment-dependent (it surfaced on CI but not every local run) because it
hinges on the allocator reusing an address.

These tests provoke id reuse deterministically and assert each distinct type
maps to a model with its own fields.
"""
import gc

import pytest
from graphql import (
    GraphQLObjectType,
    GraphQLInputObjectType,
    GraphQLInputField,
    GraphQLField,
    GraphQLString,
    GraphQLInt,
    GraphQLNonNull,
)

from graphql_mcp.server import _map_graphql_type_to_python_type


def _make_user_object(second_field_name, second_field_type):
    return GraphQLObjectType(
        "User",
        {
            "name": GraphQLField(GraphQLNonNull(GraphQLString)),
            second_field_name: GraphQLField(second_field_type),
        },
    )


def _make_user_input(second_field_name, second_field_type):
    return GraphQLInputObjectType(
        "UserInput",
        {
            "name": GraphQLInputField(GraphQLNonNull(GraphQLString)),
            second_field_name: GraphQLInputField(second_field_type),
        },
    )


def _assert_no_collision_on_id_reuse(factory):
    """Build alternating-shaped, same-named types until one reuses a freed id
    with the *other* shape, asserting each maps to a model with its own fields.

    Returns True if the id-reuse condition (the actual bug trigger) was
    observed. CPython's allocator reuses a freed same-size block on the next
    allocation, so this normally happens within a handful of iterations; the
    high cap is just a safety net before we give up.
    """
    # Alternate shapes so a reused id lands on the *other* shape — exactly the
    # condition that produced the stale-cache bug.
    shapes = [("age", GraphQLInt), ("nickname", GraphQLString)]
    seen_ids = {}

    for i in range(2000):
        field_name, field_type = shapes[i % 2]
        obj = factory(field_name, field_type)
        reused = id(obj) in seen_ids and seen_ids[id(obj)] != field_name
        seen_ids[id(obj)] = field_name

        model = _map_graphql_type_to_python_type(obj)
        assert set(model.model_fields) == {"name", field_name}, (
            f"iteration {i}: expected fields {{'name', {field_name!r}}}, "
            f"got {set(model.model_fields)}"
        )
        # Drop references and force collection so the address can be reused.
        del obj, model
        gc.collect()

        if reused:
            # The bug condition has been exercised and the assertion above
            # validated correctness — no need to keep looping.
            return True
    return False


def test_object_type_same_name_different_shape_no_collision():
    """Two same-named object types with different fields must not share a model,
    even when the second reuses the first's (freed) id."""
    if not _assert_no_collision_on_id_reuse(_make_user_object):
        pytest.skip("allocator never reused an id on this platform")


def test_input_type_same_name_different_shape_no_collision():
    """Same as above for input object types (separate cache-key branch)."""
    if not _assert_no_collision_on_id_reuse(_make_user_input):
        pytest.skip("allocator never reused an id on this platform")
