"""Programmatic alternative to the ``@mcp`` SDL directive.

``apply_mcp()`` attaches the same metadata that an SDL ``@mcp(...)``
directive would produce, directly onto a graphql-core schema's field and
argument objects. It's intended for GraphQL libraries (notably Graphene)
whose Python APIs don't propagate directive information through to
graphql-core, and as a shorter alternative to the full SDL-rebuild
workaround.

**Use this as a last resort.** When your library supports native
directives (graphql-api via ``Annotated[..., mcp(...)]``, Strawberry via
``@strawberry.schema_directive``, or any library that lets you declare
directives inline in SDL), prefer those — they're visible in the schema
and survive printing, introspection, and composition. ``apply_mcp()`` is
a private attribute on graphql-core objects; no other tool will see it.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from graphql import GraphQLSchema


_ALLOWED_KEYS = frozenset({"name", "description", "hidden"})


@dataclass(frozen=True)
class _SyntheticDirective:
    name: str


@dataclass(frozen=True)
class _SyntheticAppliedDirective:
    directive: _SyntheticDirective
    args: Dict[str, Any]


_MCP_DIRECTIVE = _SyntheticDirective(name="mcp")


def _validate_config(path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        raise TypeError(
            f"apply_mcp config for '{path}' must be a dict, "
            f"got {type(cfg).__name__}"
        )
    unknown = set(cfg) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"Unknown @mcp keys for '{path}': {sorted(unknown)}. "
            f"Supported keys: {sorted(_ALLOWED_KEYS)}"
        )
    return cfg


def _attach(node: Any, cfg: Dict[str, Any]) -> None:
    # Preserve any existing applied directives; replace the @mcp entry if one
    # is already there, otherwise append a new one.
    existing = list(getattr(node, "_applied_directives", []) or [])
    existing = [
        d for d in existing
        if getattr(getattr(d, "directive", None), "name", None) != "mcp"
    ]
    existing.append(_SyntheticAppliedDirective(
        directive=_MCP_DIRECTIVE,
        args=dict(cfg),
    ))
    node._applied_directives = existing


def _lookup_field(schema: GraphQLSchema, path: str) -> Any:
    parts = path.split(".")
    if len(parts) != 2:
        raise ValueError(
            f"Field path '{path}' must be 'TypeName.fieldName'"
        )
    type_name, field_name = parts
    gql_type = schema.type_map.get(type_name)
    if gql_type is None or not hasattr(gql_type, "fields"):
        raise ValueError(
            f"Type '{type_name}' not found in schema "
            f"(from apply_mcp path '{path}')"
        )
    field = gql_type.fields.get(field_name)
    if field is None:
        raise ValueError(
            f"Field '{field_name}' not found on type '{type_name}' "
            f"(from apply_mcp path '{path}'). "
            f"Available: {sorted(gql_type.fields)}"
        )
    return field


def _lookup_arg(schema: GraphQLSchema, path: str) -> Any:
    parts = path.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Argument path '{path}' must be 'TypeName.fieldName.argName'"
        )
    type_name, field_name, arg_name = parts
    field = _lookup_field(schema, f"{type_name}.{field_name}")
    arg = field.args.get(arg_name)
    if arg is None:
        raise ValueError(
            f"Argument '{arg_name}' not found on {type_name}.{field_name} "
            f"(from apply_mcp path '{path}'). "
            f"Available: {sorted(field.args)}"
        )
    return arg


def apply_mcp(
    schema: GraphQLSchema,
    *,
    fields: Optional[Dict[str, Dict[str, Any]]] = None,
    args: Optional[Dict[str, Dict[str, Any]]] = None,
) -> GraphQLSchema:
    """Attach ``@mcp`` directive configuration to a graphql-core schema programmatically.

    Args:
        schema: A graphql-core ``GraphQLSchema``. Mutated in place.
        fields: Mapping from ``"TypeName.fieldName"`` to a dict with any of
            ``name`` (``str``), ``description`` (``str``), ``hidden`` (``bool``).
        args: Mapping from ``"TypeName.fieldName.argName"`` to the same dict
            shape.

    Returns:
        The same schema, for chaining.

    Raises:
        ValueError: If a path doesn't resolve to a field/argument in the
            schema, or contains unknown config keys.

    Example:

        >>> import strawberry
        >>> from graphql_mcp import GraphQLMCP, apply_mcp
        >>>
        >>> @strawberry.type
        ... class Query:
        ...     @strawberry.field
        ...     def greet(self, name: str) -> str:
        ...         return f"Hello, {name}!"
        >>>
        >>> sb_schema = strawberry.Schema(query=Query)
        >>> apply_mcp(
        ...     sb_schema._schema,
        ...     fields={"Query.greet": {"name": "say_hi"}},
        ...     args={"Query.greet.name": {"name": "user_name"}},
        ... )                                               # doctest: +SKIP
        >>> server = GraphQLMCP(schema=sb_schema._schema)   # doctest: +SKIP
    """
    for path, cfg in (fields or {}).items():
        cfg = _validate_config(path, cfg)
        node = _lookup_field(schema, path)
        _attach(node, cfg)
    for path, cfg in (args or {}).items():
        cfg = _validate_config(path, cfg)
        node = _lookup_arg(schema, path)
        _attach(node, cfg)
    return schema
