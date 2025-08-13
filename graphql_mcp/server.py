import enum
import inspect
import re
import uuid
import json
import logging

from datetime import date, datetime
from typing import Any, Callable, Literal, Tuple, Optional, Dict

from fastmcp import FastMCP, Context

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware import Middleware as ASGIMiddleware
from fastmcp.server.http import (
    StarletteWithLifespan
)

try:
    from fastmcp.server.auth.providers.bearer import BearerAuthProvider as JWTVerifier
except ImportError:
    try:
        from fastmcp.server.auth.providers.jwt import JWTVerifier
    except ImportError:
        JWTVerifier = None

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
    graphql,
    is_leaf_type,
    GraphQLObjectType,
)

from .remote import RemoteGraphQLClient


logger = logging.getLogger(__name__)


def _extract_bearer_token_from_context(ctx: Optional[Context]) -> Optional[str]:
    """
    Extract bearer token from MCP request context for REMOTE server forwarding.

    This function is only used when forwarding bearer tokens to remote GraphQL servers.
    For local GraphQL schema execution, token context is automatically available
    through FastMCP and no extraction/forwarding is needed.

    Args:
        ctx: FastMCP Context object

    Returns:
        Bearer token string if found, None otherwise
    """
    if not ctx:
        return None

    try:
        request = ctx.get_http_request()
        if request and hasattr(request, 'headers'):
            auth_header = request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                return auth_header[7:]  # Remove 'Bearer ' prefix
    except Exception as e:
        logger.debug(f"Failed to extract bearer token from context: {e}")

    return None


class GraphQLMCPServer(FastMCP):  # type: ignore

    @classmethod
    def from_schema(cls, graphql_schema: GraphQLSchema, allow_mutations: bool = True, *args, **kwargs):
        """
        Create a GraphQLMCPServer from a LOCAL GraphQL schema.

        This method creates tools that execute GraphQL operations directly against the
        provided schema. Bearer token authentication is handled automatically through
        the FastMCP Context object - no token forwarding configuration is needed.

        Args:
            graphql_schema: The GraphQL schema to expose as MCP tools
            allow_mutations: Whether to expose mutations as tools (default: True)
            *args: Additional arguments to pass to FastMCP
            **kwargs: Additional keyword arguments to pass to FastMCP

        Returns:
            GraphQLMCPServer: A server instance with tools generated from the schema

        Note:
            For remote GraphQL servers, use `from_remote_url()` instead, which provides
            the `forward_bearer_token` option for token forwarding scenarios.
        """
        # Create a FastMCP instance and add tools from schema
        instance = FastMCP(*args, **kwargs)
        add_tools_from_schema(graphql_schema, instance, allow_mutations=allow_mutations)
        return instance

    @classmethod
    def from_remote_url(
        cls,
        url: str,
        bearer_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        allow_mutations: bool = True,
        forward_bearer_token: bool = False,
        *args,
        **kwargs
    ):
        """
        Create a GraphQLMCPServer from a remote GraphQL endpoint.

        Args:
            url: The GraphQL endpoint URL
            bearer_token: Optional Bearer token for authentication
            headers: Optional additional headers to include in requests
            timeout: Request timeout in seconds
            allow_mutations: Whether to expose mutations as tools (default: True)
            forward_bearer_token: Whether to forward bearer tokens from MCP requests
                to the remote GraphQL server (default: False).

                IMPORTANT: This parameter is ONLY relevant for remote GraphQL servers.
                For local schemas (using `from_schema()`), bearer token context is
                automatically available through FastMCP's Context object.

                SECURITY WARNING: When enabled, bearer tokens from incoming MCP requests
                will be forwarded to the remote GraphQL server. This means:
                - Client authentication tokens will be shared with the remote server
                - The remote server will have access to the original client's credentials
                - Only enable this if you trust the remote GraphQL server completely
                - Consider the security implications of token forwarding in your deployment

            *args: Additional arguments to pass to FastMCP
            **kwargs: Additional keyword arguments to pass to FastMCP

        Returns:
            GraphQLMCPServer: A server instance with tools generated from the remote schema

        Security Considerations:
            - When forward_bearer_token=True, ensure the remote GraphQL server is trusted
            - Use HTTPS for the remote URL to protect tokens in transit
            - Consider implementing token validation or transformation before forwarding
            - Monitor access logs for both the MCP server and remote GraphQL server
        """
        from .remote import fetch_remote_schema_sync, RemoteGraphQLClient

        # Prepare headers with bearer token if provided
        request_headers = headers.copy() if headers else {}
        if bearer_token:
            request_headers["Authorization"] = f"Bearer {bearer_token}"

        # Fetch the schema from the remote server
        schema = fetch_remote_schema_sync(url, request_headers, timeout)

        # Create a FastMCP server instance
        instance = FastMCP(*args, **kwargs)

        # Create a remote client for executing queries
        client = RemoteGraphQLClient(url, request_headers, timeout, bearer_token=bearer_token)

        # Add tools from schema with remote client
        add_tools_from_schema_with_remote(schema, instance, client, allow_mutations=allow_mutations, forward_bearer_token=forward_bearer_token)

        return instance

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
        def from_api(cls, api: GraphQLAPI, graphql_http_server: bool = True, allow_mutations: bool = True, *args, **kwargs):
            mcp = GraphQLMCPServer(api=api, graphql_http_server=graphql_http_server, allow_mutations=allow_mutations, *args, **kwargs)
            return mcp

        def __init__(self, api: GraphQLAPI, graphql_http_server: bool = True, allow_mutations: bool = True, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.api = api
            self.graphql_http_server = graphql_http_server
            add_tools_from_schema(api.build_schema()[0], self, allow_mutations=allow_mutations)

        def http_app(self, *args, **kwargs):
            app = super().http_app(*args, **kwargs)
            if self.graphql_http_server:
                from graphql_http_server import GraphQLHTTPServer  # type: ignore

                if JWTVerifier and isinstance(self.auth, JWTVerifier):
                    graphql_app = GraphQLHTTPServer.from_api(
                        api=self.api,
                        auth_enabled=True,
                        auth_jwks_uri=self.auth.jwks_uri,
                        auth_issuer=self.auth.issuer,
                        auth_audience=self.auth.audience
                    ).app
                else:
                    graphql_app = GraphQLHTTPServer.from_api(
                        api=self.api,
                        auth_enabled=False,
                    ).app
                    if self.auth:
                        logger.critical("Auth mechanism is enabled for MCP but is not supported with GraphQLHTTPServer. Please use a different auth mechanism, or disable GraphQLHTTPServer.")

                app.mount("/", graphql_app)
            return app


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
        # Use the original Python enum for proper schema generation
        if hasattr(graphql_type, 'enum_type') and graphql_type.enum_type:  # type: ignore
            return graphql_type.enum_type  # type: ignore

        # Otherwise, create a Python enum class dynamically from the GraphQL enum
        enum_members = {
            name: value.value if value.value is not None else name
            for name, value in graphql_type.values.items()
        }
        DynamicEnum = enum.Enum(
            graphql_type.name,
            enum_members,
            type=str
        )
        return DynamicEnum

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
    schema: GraphQLSchema,
    server: FastMCP | None = None,
    allow_mutations: bool = True
) -> FastMCP:
    """
    Populates a FastMCP server with tools for LOCAL GraphQL schema execution.

    This function creates tools that execute GraphQL operations directly against
    the provided schema. Bearer token authentication is handled automatically
    through the FastMCP Context object.

    If a server instance is not provided, a new one will be created.
    Processes mutations first, then queries, so that queries will overwrite
    any mutations with the same name.

    :param schema: The GraphQLSchema to map.
    :param server: An optional existing FastMCP server instance to add tools to.
    :param allow_mutations: Whether to expose mutations as tools (default: True).
    :return: The populated FastMCP server instance.

    Note:
        For remote GraphQL servers, use `add_tools_from_schema_with_remote()` instead,
        which provides bearer token forwarding capabilities.
    """
    if server is None:
        server_name = "GraphQL"
        if schema.query_type and schema.query_type.name:
            server_name = schema.query_type.name
        server = FastMCP(name=server_name)

    # Process mutations first (if allowed), so that queries can overwrite them if a name collision occurs.
    if allow_mutations:
        add_mutation_tools_from_schema(server, schema)

    add_query_tools_from_schema(server, schema)

    # After top-level queries and mutations, add tools for nested mutations
    _add_nested_tools_from_schema(server, schema, allow_mutations=allow_mutations)

    return server


def add_tools_from_schema_with_remote(
    schema: GraphQLSchema,
    server: FastMCP,
    remote_client: RemoteGraphQLClient,
    allow_mutations: bool = True,
    forward_bearer_token: bool = False
) -> FastMCP:
    """
    Populates a FastMCP server with tools for REMOTE GraphQL server execution.

    This function creates tools that forward GraphQL operations to a remote server
    via the provided RemoteGraphQLClient. Unlike local schema execution, bearer
    tokens are not automatically available and must be explicitly forwarded if needed.

    :param schema: The GraphQLSchema from the remote server
    :param server: The FastMCP server instance to add tools to
    :param remote_client: The remote GraphQL client for executing queries
    :param allow_mutations: Whether to expose mutations as tools (default: True)
    :param forward_bearer_token: Whether to forward bearer tokens from MCP requests 
                                to the remote server (default: False). Only relevant
                                for remote servers - local schemas get token context
                                automatically through FastMCP.
    :return: The populated FastMCP server instance

    Security Note:
        When forward_bearer_token=True, client bearer tokens will be sent to the
        remote GraphQL server. Only enable this if you trust the remote server.
    """
    # Process mutations first (if allowed), then queries
    if allow_mutations and schema.mutation_type:
        _add_tools_from_fields_remote(
            server, schema, schema.mutation_type.fields, remote_client, is_mutation=True, forward_bearer_token=forward_bearer_token
        )

    if schema.query_type:
        _add_tools_from_fields_remote(
            server, schema, schema.query_type.fields, remote_client, is_mutation=False, forward_bearer_token=forward_bearer_token
        )

    # Add nested tools for remote schema
    _add_nested_tools_from_schema_remote(server, schema, remote_client, allow_mutations=allow_mutations, forward_bearer_token=forward_bearer_token)

    return server


def _create_tool_function(
    field_name: str,
    field: GraphQLField,
    schema: GraphQLSchema,
    is_mutation: bool = False,
) -> Callable:
    """
    Creates a function for LOCAL GraphQL schema execution.
    
    This function executes GraphQL operations directly against the provided schema.
    Bearer token authentication is automatically available through FastMCP's Context.
    No token forwarding is needed since execution happens locally.
    """
    parameters = []
    arg_defs = []
    annotations = {}
    for arg_name, arg_def in field.args.items():
        arg_def: GraphQLArgument
        python_type = _map_graphql_type_to_python_type(arg_def.type)
        annotations[arg_name] = python_type
        # GraphQL uses Undefined for arguments without defaults
        # For required (non-null) arguments, we should not set a default
        from graphql.pyutils import Undefined
        if arg_def.default_value is Undefined:
            default = inspect.Parameter.empty
        else:
            default = arg_def.default_value
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        parameters.append(
            inspect.Parameter(arg_name, kind, default=default, annotation=python_type)
        )
        arg_defs.append(f"${arg_name}: {_get_graphql_type_name(arg_def.type)}")

    async def wrapper(**kwargs):
        # Convert enums to their values for graphql_sync
        processed_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                # GraphQL variables for enums expect the ENUM NAME, not the underlying value
                if isinstance(v.value, str):
                    processed_kwargs[k] = v.value
                else:
                    processed_kwargs[k] = v.name
            elif hasattr(v, "model_dump"):  # Check for Pydantic model
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                # graphql-api expects a JSON string for dict inputs
                processed_kwargs[k] = json.dumps(v)
            else:
                processed_kwargs[k] = v

        # Normalize enum inputs so callers can pass either enum NAME or VALUE as string
        if field.args:
            for arg_name, arg_def in field.args.items():
                if arg_name in processed_kwargs:
                    named = get_named_type(arg_def.type)
                    if isinstance(named, GraphQLEnumType):
                        val = processed_kwargs[arg_name]
                        if isinstance(val, str):
                            # If not already a valid NAME, try to map VALUE->NAME
                            if val not in named.values:
                                for enum_name, enum_value in named.values.items():
                                    try:
                                        if str(enum_value.value) == val:
                                            processed_kwargs[arg_name] = enum_name
                                            break
                                    except Exception:
                                        continue

        operation_type = "mutation" if is_mutation else "query"
        arg_str = ", ".join(f"{name}: ${name}" for name in kwargs)
        selection_set = _build_selection_set(field.type)

        query_str = f"{operation_type} ({', '.join(arg_defs)}) {{ {field_name}({arg_str}) {selection_set} }}"
        if not arg_defs:
            query_str = f"{operation_type} {{ {field_name} {selection_set} }}"

        # Execute the query
        result = await graphql(schema, query_str, variable_values=processed_kwargs)

        if result.errors:
            # For simplicity, just raise the first error
            raise result.errors[0]

        if result.data:
            return result.data.get(field_name)

        return None

    # Add return type annotation for FastMCP schema generation
    return_type = _map_graphql_type_to_python_type(field.type)
    annotations['return'] = return_type

    # Create signature with return annotation
    signature = inspect.Signature(parameters, return_annotation=return_type)
    wrapper.__signature__ = signature
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
    async def wrapper(**kwargs):

        processed_kwargs: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                # GraphQL variables for enums expect the ENUM NAME, not the underlying value
                processed_kwargs[k] = v.name
            elif hasattr(v, "model_dump"):
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                processed_kwargs[k] = json.dumps(v)
            else:
                processed_kwargs[k] = v

        # Normalize enum inputs for nested paths (support enum VALUE or NAME)
        for idx, (field_name, field_def) in enumerate(path):
            if field_def.args:
                for arg in field_def.args.keys():
                    var_name = arg if idx == len(path) - 1 else f"{field_name}_{arg}"
                    if var_name in processed_kwargs:
                        named = get_named_type(field_def.args[arg].type)
                        if isinstance(named, GraphQLEnumType):
                            val = processed_kwargs[var_name]
                            if isinstance(val, str) and val not in named.values:
                                for enum_name, enum_value in named.values.items():
                                    try:
                                        if str(enum_value.value) == val:
                                            processed_kwargs[var_name] = enum_name
                                            break
                                    except Exception:
                                        continue

        result = await graphql(schema, query_str, variable_values=processed_kwargs)

        if result.errors:
            raise result.errors[0]

        # Walk down the path to extract the nested value
        data_cursor = result.data
        for field_name, _ in path:
            if data_cursor is None:
                break
            data_cursor = data_cursor.get(field_name) if isinstance(data_cursor, dict) else None

        # Return the raw data cursor since we now have proper return type annotations
        return data_cursor

    tool_name = _to_snake_case("_".join(name for name, _ in path))

    # Add return type annotation for FastMCP schema generation
    return_type = _map_graphql_type_to_python_type(path[-1][1].type)
    annotations['return'] = return_type

    # Create signature with return annotation
    signature = inspect.Signature(parameters, return_annotation=return_type)
    wrapper.__signature__ = signature
    wrapper.__doc__ = path[-1][1].description
    wrapper.__name__ = tool_name
    wrapper.__annotations__ = annotations

    return tool_name, wrapper


def _add_nested_tools_from_schema(server: FastMCP, schema: GraphQLSchema, allow_mutations: bool = True):
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
    if allow_mutations and schema.mutation_type:
        recurse(schema.mutation_type, "mutation", [])


# ---------------------------------------------------------------------------
# Remote GraphQL support functions
# ---------------------------------------------------------------------------


def _add_tools_from_fields_remote(
    server: FastMCP,
    schema: GraphQLSchema,
    fields: dict[str, Any],
    remote_client: RemoteGraphQLClient,
    is_mutation: bool,
    forward_bearer_token: bool = False,
):
    """Add tools from fields that execute against a remote GraphQL server."""
    for field_name, field in fields.items():
        snake_case_name = _to_snake_case(field_name)
        tool_func = _create_remote_tool_function(
            field_name, field, schema, remote_client, is_mutation=is_mutation, forward_bearer_token=forward_bearer_token
        )
        tool_decorator = server.tool(name=snake_case_name)
        tool_decorator(tool_func)


def _create_remote_tool_function(
    field_name: str,
    field: GraphQLField,
    schema: GraphQLSchema,
    remote_client: RemoteGraphQLClient,
    is_mutation: bool = False,
    forward_bearer_token: bool = False,
) -> Callable:
    """
    Creates a function for REMOTE GraphQL server execution.
    
    This function forwards GraphQL operations to a remote server via RemoteGraphQLClient.
    Unlike local execution, bearer tokens are not automatically available and must be
    explicitly extracted from the MCP request context if forwarding is enabled.
    
    :param forward_bearer_token: Whether to extract bearer token from MCP request
                               context and forward it to the remote server.
    """
    parameters = []
    arg_defs = []
    annotations = {}

    for arg_name, arg_def in field.args.items():
        arg_def: GraphQLArgument
        python_type = _map_graphql_type_to_python_type(arg_def.type)
        annotations[arg_name] = python_type

        from graphql.pyutils import Undefined
        if arg_def.default_value is Undefined:
            default = inspect.Parameter.empty
        else:
            default = arg_def.default_value

        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        parameters.append(
            inspect.Parameter(arg_name, kind, default=default, annotation=python_type)
        )
        arg_defs.append(f"${arg_name}: {_get_graphql_type_name(arg_def.type)}")

    # Add Context parameter for bearer token extraction
    parameters.append(
        inspect.Parameter(
            "ctx",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=None,
            annotation=Optional[Context]
        )
    )
    annotations["ctx"] = Optional[Context]

    async def wrapper(**kwargs):
        # Extract context and bearer token (only if configured to forward)
        ctx = kwargs.pop("ctx", None)
        bearer_token = _extract_bearer_token_from_context(ctx) if forward_bearer_token else None

        # Process arguments
        processed_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                if isinstance(v.value, str):
                    processed_kwargs[k] = v.value
                else:
                    processed_kwargs[k] = v.name
            elif hasattr(v, "model_dump"):
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                processed_kwargs[k] = v
            else:
                processed_kwargs[k] = v

        # Normalize enum inputs
        if field.args:
            for arg_name, arg_def in field.args.items():
                if arg_name in processed_kwargs:
                    named = get_named_type(arg_def.type)
                    if isinstance(named, GraphQLEnumType):
                        val = processed_kwargs[arg_name]
                        if isinstance(val, str):
                            if val not in named.values:
                                for enum_name, enum_value in named.values.items():
                                    try:
                                        if str(enum_value.value) == val:
                                            processed_kwargs[arg_name] = enum_name
                                            break
                                    except Exception:
                                        continue

        # Build GraphQL query
        operation_type = "mutation" if is_mutation else "query"
        arg_str = ", ".join(f"{name}: ${name}" for name in kwargs)
        selection_set = _build_selection_set(field.type)

        query_str = f"{operation_type} ({', '.join(arg_defs)}) {{ {field_name}({arg_str}) {selection_set} }}"
        if not arg_defs:
            query_str = f"{operation_type} {{ {field_name} {selection_set} }}"

        # Execute against remote server with optional bearer token override
        try:
            result = await remote_client.execute_with_token(
                query_str, processed_kwargs, bearer_token_override=bearer_token
            )
            return result.get(field_name) if result else None
        except Exception as e:
            raise Exception(f"Remote GraphQL execution failed: {e}")

    # Add return type annotation
    return_type = _map_graphql_type_to_python_type(field.type)
    annotations['return'] = return_type

    # Create signature
    signature = inspect.Signature(parameters, return_annotation=return_type)
    wrapper.__signature__ = signature
    wrapper.__doc__ = field.description
    wrapper.__name__ = _to_snake_case(field_name)
    wrapper.__annotations__ = annotations

    return wrapper


def _create_recursive_remote_tool_function(
    path: list[tuple[str, GraphQLField]],
    operation_type: str,
    schema: GraphQLSchema,
    remote_client: RemoteGraphQLClient,
    forward_bearer_token: bool = False,
) -> Tuple[str, Callable]:
    """Builds a FastMCP tool that resolves a nested field chain against a remote server."""

    # Collect parameters & GraphQL variable definitions
    parameters: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    arg_defs: list[str] = []

    for idx, (field_name, field_def) in enumerate(path):
        for arg_name, arg_def in field_def.args.items():
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

    # Add Context parameter for bearer token extraction
    parameters.append(
        inspect.Parameter(
            "ctx",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=None,
            annotation=Optional[Context]
        )
    )
    annotations["ctx"] = Optional[Context]

    # Build nested call string
    def _build_call(index: int) -> str:
        field_name, field_def = path[index]
        if field_def.args:
            arg_str_parts = []
            for arg in field_def.args.keys():
                var_name = arg if index == len(path) - 1 else f"{field_name}_{arg}"
                arg_str_parts.append(f"{arg}: ${var_name}")
            arg_str = ", ".join(arg_str_parts)
            call = f"{field_name}({arg_str})"
        else:
            call = field_name

        if index == len(path) - 1:
            selection_set = _build_selection_set(field_def.type)
            return f"{call} {selection_set}"

        return f"{call} {{ {_build_call(index + 1)} }}"

    graphql_body = _build_call(0)

    arg_def_str = ", ".join(arg_defs)
    operation_header = (
        f"{operation_type} ({arg_def_str})" if arg_def_str else operation_type
    )
    query_str = f"{operation_header} {{ {graphql_body} }}"

    # Tool wrapper
    async def wrapper(**kwargs):
        # Extract context and bearer token (only if configured to forward)
        ctx = kwargs.pop("ctx", None)
        bearer_token = _extract_bearer_token_from_context(ctx) if forward_bearer_token else None

        processed_kwargs: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, enum.Enum):
                processed_kwargs[k] = v.name
            elif hasattr(v, "model_dump"):
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, dict):
                processed_kwargs[k] = v
            else:
                processed_kwargs[k] = v

        # Normalize enum inputs
        for idx, (field_name, field_def) in enumerate(path):
            if field_def.args:
                for arg in field_def.args.keys():
                    var_name = arg if idx == len(path) - 1 else f"{field_name}_{arg}"
                    if var_name in processed_kwargs:
                        named = get_named_type(field_def.args[arg].type)
                        if isinstance(named, GraphQLEnumType):
                            val = processed_kwargs[var_name]
                            if isinstance(val, str) and val not in named.values:
                                for enum_name, enum_value in named.values.items():
                                    try:
                                        if str(enum_value.value) == val:
                                            processed_kwargs[var_name] = enum_name
                                            break
                                    except Exception:
                                        continue

        # Execute against remote server with optional bearer token override
        try:
            result = await remote_client.execute_with_token(
                query_str, processed_kwargs, bearer_token_override=bearer_token
            )

            # Walk down the path to extract the nested value
            data_cursor = result
            for field_name, _ in path:
                if data_cursor is None:
                    break
                data_cursor = data_cursor.get(field_name) if isinstance(data_cursor, dict) else None

            return data_cursor
        except Exception as e:
            raise Exception(f"Remote GraphQL execution failed: {e}")

    tool_name = _to_snake_case("_".join(name for name, _ in path))

    # Add return type annotation
    return_type = _map_graphql_type_to_python_type(path[-1][1].type)
    annotations['return'] = return_type

    # Create signature
    signature = inspect.Signature(parameters, return_annotation=return_type)
    wrapper.__signature__ = signature
    wrapper.__doc__ = path[-1][1].description
    wrapper.__name__ = tool_name
    wrapper.__annotations__ = annotations

    return tool_name, wrapper


def _add_nested_tools_from_schema_remote(
    server: FastMCP,
    schema: GraphQLSchema,
    remote_client: RemoteGraphQLClient,
    allow_mutations: bool = True,
    forward_bearer_token: bool = False
):
    """Recursively registers tools for nested fields that execute against a remote server."""

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
                tool_name, tool_func = _create_recursive_remote_tool_function(
                    new_path, operation_type, schema, remote_client, forward_bearer_token=forward_bearer_token
                )
                server.tool(name=tool_name)(tool_func)

            if isinstance(named_type, GraphQLObjectType):
                recurse(named_type, operation_type, new_path)

    # Start from both query and mutation roots
    if schema.query_type:
        recurse(schema.query_type, "query", [])
    if allow_mutations and schema.mutation_type:
        recurse(schema.mutation_type, "mutation", [])
