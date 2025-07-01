import enum
import inspect
import re
import uuid
import json

from datetime import date, datetime
from typing import Any, Callable, Literal, Tuple

from fastmcp import FastMCP

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware import Middleware as ASGIMiddleware
from fastmcp.server.http import (
    StarletteWithLifespan
)

from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLSchema,
    GraphQLString,
    GraphQLInt,
    GraphQLFloat,
    GraphQLBoolean,
    GraphQLID,
    get_named_type,
    graphql_sync,
    is_leaf_type,
    GraphQLObjectType,
)


class GraphQLMCPServer(FastMCP):  # type: ignore

    @classmethod
    def from_schema(cls, graphql_schema: GraphQLSchema, *args, **kwargs):
        mcp = FastMCP(*args, **kwargs)
        add_tools_from_schema(graphql_schema, mcp)
        return mcp

    def http_app(
        self,
        path: str | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
        transport: Literal["http", "streamable-http", "sse"] = "http",
        **kwargs
    ) -> StarletteWithLifespan:
        app = super().http_app(path, middleware, json_response, stateless_http, transport, **kwargs)
        app.add_middleware(MCPRedirectMiddleware)
        return app


try:
    from graphql_api import GraphQLAPI
    from graphql_api.types import (
        GraphQLUUID,
        GraphQLDateTime,
        GraphQLDate,
        GraphQLJSON,
        GraphQLBytes,
    )

    HAS_GRAPHQL_API = True

    class GraphQLMCPServer(GraphQLMCPServer):

        @classmethod
        def from_api(cls, api: GraphQLAPI, *args, **kwargs):
            mcp = GraphQLMCPServer(*args, **kwargs)
            add_tools_from_schema(api.build_schema()[0], mcp)
            return mcp


except ImportError:
    HAS_GRAPHQL_API = False
    GraphQLUUID = object()
    GraphQLDateTime = object()
    GraphQLDate = object()
    GraphQLJSON = object()
    GraphQLBytes = object()


def _map_graphql_type_to_python_type(graphql_type: Any) -> Any:
    """
    Maps a GraphQL type to a Python type for function signatures.
    """
    if isinstance(graphql_type, GraphQLNonNull):
        return _map_graphql_type_to_python_type(graphql_type.of_type)
    if isinstance(graphql_type, GraphQLList):
        return list[_map_graphql_type_to_python_type(graphql_type.of_type)]

    # Scalar types
    if graphql_type is GraphQLString:
        return str
    if graphql_type is GraphQLInt:
        return int
    if graphql_type is GraphQLFloat:
        return float
    if graphql_type is GraphQLBoolean:
        return bool
    if graphql_type is GraphQLID:
        return str

    if HAS_GRAPHQL_API:
        if graphql_type is GraphQLUUID:
            return uuid.UUID
        if graphql_type is GraphQLDateTime:
            return datetime
        if graphql_type is GraphQLDate:
            return date
        if graphql_type is GraphQLJSON:
            return Any
        if graphql_type is GraphQLBytes:
            return bytes

    if isinstance(graphql_type, GraphQLEnumType):
        # Create a Python enum from the GraphQL enum
        return enum.Enum(
            graphql_type.name,
            {k: v.value for k, v in graphql_type.values.items()},
        )

    if isinstance(graphql_type, GraphQLInputObjectType):
        # This is complex. For now, we'll treat it as a dict.
        # fastmcp can handle pydantic models or dataclasses.
        # We might need to generate them on the fly.
        return dict

    return Any


def _to_snake_case(name: str) -> str:
    """Converts a camelCase string to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _get_graphql_type_name(graphql_type: Any) -> str:
    """
    Gets the name of a GraphQL type for use in a query string.
    """
    if isinstance(graphql_type, GraphQLNonNull):
        return f"{_get_graphql_type_name(graphql_type.of_type)}!"
    if isinstance(graphql_type, GraphQLList):
        return f"[{_get_graphql_type_name(graphql_type.of_type)}]"
    return graphql_type.name


def _build_selection_set(graphql_type: Any, max_depth: int = 2, depth: int = 0) -> str:
    """
    Builds a selection set for a GraphQL type.
    Only includes scalar fields.
    """
    if depth >= max_depth:
        return ""

    named_type = get_named_type(graphql_type)
    if is_leaf_type(named_type):
        return ""

    selections = []
    if hasattr(named_type, "fields"):
        for field_name, field_def in named_type.fields.items():
            field_named_type = get_named_type(field_def.type)
            if is_leaf_type(field_named_type):
                selections.append(field_name)
            else:
                nested_selection = _build_selection_set(
                    field_def.type, max_depth=max_depth, depth=depth + 1
                )
                if nested_selection:
                    selections.append(f"{field_name} {nested_selection}")

    if not selections:
        # If no leaf fields, maybe it's an object with no scalar fields.
        # What to do here? Can't return an empty object.
        # Maybe just return __typename as a default.
        return "{ __typename }"

    return f"{{ {', '.join(selections)} }}"


def _add_tools_from_fields(
    server: FastMCP,
    schema: GraphQLSchema,
    fields: dict[str, Any],
    is_mutation: bool,
):
    """Internal helper to add tools from a dictionary of fields."""
    for field_name, field in fields.items():
        snake_case_name = _to_snake_case(field_name)
        tool_func = _create_tool_function(
            field_name, field, schema, is_mutation=is_mutation
        )
        tool_decorator = server.tool(name=snake_case_name)
        tool_decorator(tool_func)


def add_query_tools_from_schema(server: FastMCP, schema: GraphQLSchema):
    """Adds tools to a FastMCP server from the query fields of a GraphQL schema."""
    if schema.query_type:
        _add_tools_from_fields(
            server, schema, schema.query_type.fields, is_mutation=False
        )


def add_mutation_tools_from_schema(server: FastMCP, schema: GraphQLSchema):
    """Adds tools to a FastMCP server from the mutation fields of a GraphQL schema."""
    if schema.mutation_type:
        _add_tools_from_fields(
            server, schema, schema.mutation_type.fields, is_mutation=True
        )


def add_tools_from_schema(
    schema: GraphQLSchema, server: FastMCP | None = None
) -> FastMCP:
    """
    Populates a FastMCP server with tools generated from a GraphQLSchema.

    If a server instance is not provided, a new one will be created.
    Processes mutations first, then queries, so that queries will overwrite
    any mutations with the same name.

    :param schema: The GraphQLSchema to map.
    :param server: An optional existing FastMCP server instance to add tools to.
    :return: The populated FastMCP server instance.
    """
    if server is None:
        server_name = "GraphQL"
        if schema.query_type and schema.query_type.name:
            server_name = schema.query_type.name
        server = FastMCP(name=server_name)

    # Process mutations first, so that queries can overwrite them if a name collision occurs.
    add_mutation_tools_from_schema(server, schema)
    add_query_tools_from_schema(server, schema)

    # After top-level queries and mutations, add tools for nested mutations
    _add_nested_tools_from_schema(server, schema)

    return server


def _create_tool_function(
    field_name: str,
    field: GraphQLField,
    schema: GraphQLSchema,
    is_mutation: bool = False,
) -> Callable:
    """
    Creates a function that can be decorated as a fastmcp tool.
    """
    parameters = []
    arg_defs = []
    annotations = {}
    for arg_name, arg_def in field.args.items():
        arg_def: GraphQLArgument
        python_type = _map_graphql_type_to_python_type(arg_def.type)
        annotations[arg_name] = python_type
        default = (
            arg_def.default_value
            if arg_def.default_value is not inspect.Parameter.empty
            else inspect.Parameter.empty
        )
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        parameters.append(
            inspect.Parameter(arg_name, kind, default=default, annotation=python_type)
        )
        arg_defs.append(f"${arg_name}: {_get_graphql_type_name(arg_def.type)}")

    def wrapper(**kwargs):
        # Convert enums to their values for graphql_sync
        processed_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                processed_kwargs[k] = v.value
            elif hasattr(v, "model_dump"):  # Check for Pydantic model
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                # graphql-api expects a JSON string for dict inputs
                processed_kwargs[k] = json.dumps(v)
            else:
                processed_kwargs[k] = v

        operation_type = "mutation" if is_mutation else "query"
        arg_str = ", ".join(f"{name}: ${name}" for name in kwargs)
        selection_set = _build_selection_set(field.type)

        query_str = f"{operation_type} ({', '.join(arg_defs)}) {{ {field_name}({arg_str}) {selection_set} }}"
        if not arg_defs:
            query_str = f"{operation_type} {{ {field_name} {selection_set} }}"

        # Execute the query
        result = graphql_sync(schema, query_str, variable_values=processed_kwargs)

        if result.errors:
            # For simplicity, just raise the first error
            raise result.errors[0]

        if result.data:
            return result.data.get(field_name)

        return None

    wrapper.__signature__ = inspect.Signature(parameters)
    wrapper.__doc__ = field.description
    wrapper.__name__ = _to_snake_case(field_name)
    wrapper.__annotations__ = annotations

    return wrapper


class MCPRedirectMiddleware:
    def __init__(
        self,
        app: ASGIApp
    ) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            path = scope['path']
            # If the request path ends with '/mcp' but does not already have the
            # trailing slash, rewrite it so downstream routing sees the
            # canonical path with the slash.
            if path.endswith('/mcp') and not path.endswith('/mcp/'):
                new_path = path + '/'
                scope['path'] = new_path
                if 'raw_path' in scope:
                    scope['raw_path'] = new_path.encode()
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Recursive nested tool generation (any depth)
# ---------------------------------------------------------------------------


def _create_recursive_tool_function(
    path: list[tuple[str, GraphQLField]],
    operation_type: str,
    schema: GraphQLSchema,
) -> Tuple[str, Callable]:
    """Builds a FastMCP tool that resolves an arbitrarily deep field chain."""

    # Collect parameters & GraphQL variable definitions
    parameters: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    arg_defs: list[str] = []

    for idx, (field_name, field_def) in enumerate(path):
        for arg_name, arg_def in field_def.args.items():
            # Use plain arg name for the leaf field to match expectations; prefix for others.
            var_name = arg_name if idx == len(path) - 1 else f"{field_name}_{arg_name}"
            python_type = _map_graphql_type_to_python_type(arg_def.type)
            annotations[var_name] = python_type
            default = (
                arg_def.default_value
                if arg_def.default_value is not inspect.Parameter.empty
                else inspect.Parameter.empty
            )
            parameters.append(
                inspect.Parameter(
                    var_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=python_type,
                )
            )
            arg_defs.append(f"${var_name}: {_get_graphql_type_name(arg_def.type)}")

    # Build nested call string
    def _build_call(index: int) -> str:
        field_name, field_def = path[index]
        # Build argument string for this field
        if field_def.args:
            arg_str_parts = []
            for arg in field_def.args.keys():
                var_name = arg if index == len(path) - 1 else f"{field_name}_{arg}"
                arg_str_parts.append(f"{arg}: ${var_name}")
            arg_str = ", ".join(arg_str_parts)
            call = f"{field_name}({arg_str})"
        else:
            call = field_name

        # If leaf
        if index == len(path) - 1:
            selection_set = _build_selection_set(field_def.type)
            return f"{call} {selection_set}"

        # Otherwise recurse
        return f"{call} {{ {_build_call(index + 1)} }}"

    graphql_body = _build_call(0)

    arg_def_str = ", ".join(arg_defs)
    operation_header = (
        f"{operation_type} ({arg_def_str})" if arg_def_str else operation_type
    )
    query_str = f"{operation_header} {{ {graphql_body} }}"

    # Tool wrapper
    def wrapper(**kwargs):
        processed_kwargs: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                processed_kwargs[k] = v.value
            elif hasattr(v, "model_dump"):
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                processed_kwargs[k] = json.dumps(v)
            else:
                processed_kwargs[k] = v

        result = graphql_sync(schema, query_str, variable_values=processed_kwargs)

        if result.errors:
            raise result.errors[0]

        # Walk down the path to extract the nested value
        data_cursor = result.data
        for field_name, _ in path:
            if data_cursor is None:
                break
            data_cursor = data_cursor.get(field_name) if isinstance(data_cursor, dict) else None

        # Serialize scalars to JSON strings so FastMCP emits TextContent with valid JSON
        if isinstance(data_cursor, (dict, list)):
            return data_cursor
        return json.dumps(data_cursor)

    tool_name = _to_snake_case("_".join(name for name, _ in path))
    wrapper.__signature__ = inspect.Signature(parameters)
    wrapper.__doc__ = path[-1][1].description
    wrapper.__name__ = tool_name
    wrapper.__annotations__ = annotations

    return tool_name, wrapper


def _add_nested_tools_from_schema(server: FastMCP, schema: GraphQLSchema):
    """Recursively registers tools for any nested field chain that includes arguments."""

    visited_types: set[str] = set()

    def recurse(parent_type, operation_type: str, path: list[tuple[str, GraphQLField]]):
        type_name = parent_type.name if hasattr(parent_type, "name") else None
        if type_name and type_name in visited_types:
            return
        if type_name:
            visited_types.add(type_name)

        for field_name, field_def in parent_type.fields.items():
            named_type = get_named_type(field_def.type)
            new_path = path + [(field_name, field_def)]

            if len(new_path) > 1 and field_def.args:
                # Register tool for paths with depth >=2
                tool_name, tool_func = _create_recursive_tool_function(new_path, operation_type, schema)
                server.tool(name=tool_name)(tool_func)

            if isinstance(named_type, GraphQLObjectType):
                recurse(named_type, operation_type, new_path)

    # Start from both query and mutation roots
    if schema.query_type:
        recurse(schema.query_type, "query", [])
    if schema.mutation_type:
        recurse(schema.mutation_type, "mutation", [])
