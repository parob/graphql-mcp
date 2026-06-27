"""Regression: a GraphQL field may declare an optional argument (one with a
default) *before* a required one. The tool-wrapper signature is reconstructed
with KEYWORD_ONLY parameters, so this no longer raises the CPython
``ValueError: non-default argument follows default argument`` it used to.

The wrappers are invoked purely by keyword (**kwargs), so keyword-only is the
faithful kind — and it lifts the positional ordering constraint.
"""
import inspect

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from graphql_mcp.server import _create_tool_function


def _build_field():
    """A field whose *optional* arg (``reason``, has a default) is declared
    before its *required* arg (``message``, non-null, no default)."""
    return GraphQLField(
        GraphQLString,
        args={
            "reason": GraphQLArgument(GraphQLString, default_value="audit"),
            "message": GraphQLArgument(GraphQLNonNull(GraphQLString)),
        },
    )


def test_optional_arg_before_required_arg_builds():
    field = _build_field()
    schema = GraphQLSchema(query=GraphQLObjectType("Query", {"send": field}))

    # Previously raised ValueError: non-default argument follows default argument
    wrapper = _create_tool_function("send", field, schema)

    sig = inspect.signature(wrapper)
    assert "reason" in sig.parameters
    assert "message" in sig.parameters

    # Both are keyword-only — that's what makes the ordering legal.
    assert sig.parameters["reason"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["message"].kind is inspect.Parameter.KEYWORD_ONLY

    # Optional/required is still driven by the presence of a default, unchanged.
    assert sig.parameters["reason"].default == "audit"
    assert sig.parameters["message"].default is inspect.Parameter.empty
