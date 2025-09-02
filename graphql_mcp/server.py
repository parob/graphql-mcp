import enum
import inspect
import re
import uuid
import json
import logging

from datetime import date, datetime
from typing import Any, Callable, Literal, Tuple, Optional, Dict

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware import Middleware as ASGIMiddleware
from fastmcp.server.http import (
    StarletteWithLifespan
)

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


class GraphQLMCP(FastMCP):  # type: ignore

    @classmethod
    def from_schema(cls, graphql_schema: GraphQLSchema, allow_mutations: bool = True, *args, **kwargs):
        """
        Create a GraphQLMCP from a LOCAL GraphQL schema.

        This method creates tools that execute GraphQL operations directly against the
        provided schema. Bearer token authentication is handled automatically through
        the FastMCP Context object - no token forwarding configuration is needed.

        Args:
            graphql_schema: The GraphQL schema to expose as MCP tools
            allow_mutations: Whether to expose mutations as tools (default: True)
            *args: Additional arguments to pass to FastMCP
            **kwargs: Additional keyword arguments to pass to FastMCP

        Returns:
            GraphQLMCP: A server instance with tools generated from the schema

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
        verify_ssl: bool = True,
        *args,
        **kwargs
    ):
        """
        Create a GraphQLMCP from a remote GraphQL endpoint.

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
            GraphQLMCP: A server instance with tools generated from the remote schema

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
        client = RemoteGraphQLClient(url, request_headers, timeout, bearer_token=bearer_token, verify_ssl=verify_ssl)

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

    class GraphQLMCP(GraphQLMCP):

        @classmethod
        def from_api(cls, api: GraphQLAPI, graphql_http: bool = True, allow_mutations: bool = True, *args, **kwargs):
            mcp = GraphQLMCP(api=api, graphql_http=graphql_http, allow_mutations=allow_mutations, *args, **kwargs)
            return mcp

        def __init__(self, api: GraphQLAPI, graphql_http: bool = True, allow_mutations: bool = True, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.api = api
            self.graphql_http = graphql_http
            add_tools_from_schema(api.build_schema()[0], self, allow_mutations=allow_mutations)

        def http_app(self, *args, **kwargs):
            app = super().http_app(*args, **kwargs)
            if self.graphql_http:
                from graphql_http import GraphQLHTTP  # type: ignore

                if JWTVerifier and isinstance(self.auth, JWTVerifier):
                    graphql_app = GraphQLHTTP.from_api(
                        api=self.api,
                        auth_enabled=True,
                        auth_jwks_uri=self.auth.jwks_uri,
                        auth_issuer=self.auth.issuer,
                        auth_audience=self.auth.audience
                    ).app
                else:
                    graphql_app = GraphQLHTTP.from_api(
                        api=self.api,
                        auth_enabled=False,
                    ).app
                    if self.auth:
                        logger.critical("Auth mechanism is enabled for MCP but is not supported with GraphQLHTTP. Please use a different auth mechanism, or disable GraphQLHTTP.")

                app.add_middleware(GraphQLRootMiddleware, graphql_app=graphql_app)
            return app


except ImportError:
    HAS_GRAPHQL_API = False
    GraphQLUUID = object()
    GraphQLDateTime = object()
    GraphQLDate = object()
    GraphQLJSON = object()
    GraphQLBytes = object()


def _map_graphql_type_to_python_type(graphql_type: Any, _cache: Optional[Dict[str, Any]] = None) -> Any:
    """
    Maps a GraphQL type to a Python type for function signatures.

    Args:
        graphql_type: The GraphQL type to map
        _cache: Internal cache to prevent infinite recursion
    """
    if _cache is None:
        _cache = {}
    if isinstance(graphql_type, GraphQLNonNull):
        return _map_graphql_type_to_python_type(graphql_type.of_type, _cache)
    if isinstance(graphql_type, GraphQLList):
        return list[_map_graphql_type_to_python_type(graphql_type.of_type, _cache)]

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
        from typing import Union, Literal

        # Check if we have integer enum values
        has_integer_values = any(
            isinstance(enum_value_obj.value, int)
            for enum_value_obj in graphql_type.values.values()
            if enum_value_obj.value is not None
        )

        if has_integer_values:
            # For integer enums, create a Union that accepts both int and str
            # Collect both enum names and original integer values
            string_values = []
            integer_values = []

            for name, enum_value_obj in graphql_type.values.items():
                string_values.append(name)  # Always add enum name
                if enum_value_obj.value is not None and isinstance(enum_value_obj.value, int):
                    integer_values.append(enum_value_obj.value)
                    string_values.append(str(enum_value_obj.value))  # Also accept string version

            # Create a Union type that accepts integers, strings, or enum names
            if integer_values:
                return Union[Literal[tuple(integer_values)], Literal[tuple(string_values)]]  # type: ignore
            else:
                return Literal[tuple(string_values)]  # type: ignore
        else:
            # For string enums, show ONLY enum values in schema (Pydantic-consistent)
            # This matches Pydantic's model_dump(mode="json") behavior
            schema_values = []

            for name, enum_value_obj in graphql_type.values.items():
                if enum_value_obj.value is not None:
                    # Only add enum values (e.g., "#ff0000", "p1") to the schema
                    schema_values.append(str(enum_value_obj.value))
                else:
                    # Fallback to name if value is None
                    schema_values.append(name)

            # Remove duplicates while preserving order
            schema_values = list(dict.fromkeys(schema_values))

            return Literal[tuple(schema_values)]  # type: ignore

    if isinstance(graphql_type, GraphQLInputObjectType):
        # Check cache to prevent infinite recursion
        cache_key = f"input_object_{graphql_type.name}"
        if cache_key in _cache:
            return _cache[cache_key]

        # Create a dynamic Pydantic model for GraphQL input object types
        # This provides better MCP schema generation with detailed field information
        try:
            from pydantic import create_model

            # Add placeholder to cache first to prevent infinite recursion
            _cache[cache_key] = dict  # Temporary placeholder

            # Build field definitions for the dynamic model
            field_definitions = {}
            for field_name, field_def in graphql_type.fields.items():
                field_type = _map_graphql_type_to_python_type(field_def.type, _cache)

                # Handle default values and required fields
                if isinstance(field_def.type, GraphQLNonNull):
                    # Required field
                    field_definitions[field_name] = (field_type, ...)
                else:
                    # For GraphQL input object fields, we typically want them to be required
                    # unless they have explicit default values. Since we can't easily determine
                    # the original Pydantic model defaults, we'll make them optional for safety
                    from typing import Union
                    field_definitions[field_name] = (Union[field_type, type(None)], None)

            # Create dynamic Pydantic model
            model_name = f"{graphql_type.name}Model"
            dynamic_model = create_model(model_name, **field_definitions)

            # Update cache with actual model
            _cache[cache_key] = dynamic_model
            return dynamic_model

        except ImportError:
            # Fallback to dict if pydantic is not available
            _cache[cache_key] = dict
            return dict

    return Any


def _to_snake_case(name: str) -> str:
    """Converts a camelCase string to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _convert_enum_names_to_values_in_output(data, graphql_return_type):
    """Convert enum names to values in GraphQL output data for MCP validation"""
    if data is None:
        return data

    try:
        # Get the core type, unwrapping NonNull and List wrappers
        current_type = graphql_return_type
        while isinstance(current_type, GraphQLNonNull):
            current_type = current_type.of_type

        if isinstance(current_type, GraphQLList):
            # Handle list of items
            if isinstance(data, list):
                return [_convert_enum_names_to_values_in_output(item, current_type.of_type) for item in data]
            return data

        named_type = get_named_type(current_type)

        if isinstance(named_type, GraphQLEnumType):
            # Convert enum name to value
            if isinstance(data, str) and data in named_type.values:
                enum_value_obj = named_type.values[data]
                if enum_value_obj.value is not None:
                    return enum_value_obj.value
            return data

        elif isinstance(named_type, GraphQLObjectType):
            # Handle object types - recursively process fields
            if isinstance(data, dict):
                result = {}
                for field_name, field_value in data.items():
                    if field_name in named_type.fields:
                        field_def = named_type.fields[field_name]
                        converted_value = _convert_enum_names_to_values_in_output(field_value, field_def.type)
                        result[field_name] = converted_value
                    else:
                        result[field_name] = field_value
                return result
            return data

        return data

    except Exception:
        # If conversion fails, return original data
        return data


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
                # For GraphQL input objects, convert Pydantic models to dicts
                # Use mode="json" to properly serialize enums and other complex types
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, list):
                # Handle lists that might contain Pydantic models
                processed_list = []
                for item in v:
                    if hasattr(item, "model_dump"):
                        # Convert Pydantic model to dict for GraphQL
                        # Use mode="json" to properly serialize enums and other complex types
                        processed_list.append(item.model_dump(mode="json"))
                    elif isinstance(item, dict):
                        processed_list.append(item)
                    else:
                        processed_list.append(item)
                processed_kwargs[k] = processed_list
            elif isinstance(v, dict):
                # Check if this dict argument maps to a JSON scalar or an Input Object Type
                if k in field.args:
                    arg_def = field.args[k]
                    named_type = get_named_type(arg_def.type)
                    # If it's a GraphQLInputObjectType, keep as dict for GraphQL-core
                    # If it's a JSON scalar type, convert to JSON string
                    if isinstance(named_type, GraphQLInputObjectType):
                        processed_kwargs[k] = v
                    else:
                        # Likely a JSON scalar type - convert to JSON string
                        processed_kwargs[k] = json.dumps(v)
                else:
                    # Default: convert to JSON string for backward compatibility
                    processed_kwargs[k] = json.dumps(v)
            else:
                processed_kwargs[k] = v

        # Normalize enum inputs so callers can pass either enum NAME or VALUE as string
        # This handles both top-level args and nested enum values in lists/dicts
        def normalize_enum_values_recursively(data, arg_def):
            """Recursively normalize enum values in nested data structures"""
            if data is None:
                return data

            try:
                # Check if this is a list type by inspecting the full type structure
                current_type = arg_def.type

                # Unwrap NonNull wrappers to get to the core type
                from graphql import GraphQLNonNull
                while isinstance(current_type, GraphQLNonNull):
                    current_type = current_type.of_type

                # Now check if it's a list
                if isinstance(current_type, GraphQLList):
                    # This is a list type, process each item
                    list_item_type = get_named_type(current_type.of_type)

                    if isinstance(data, list) and hasattr(list_item_type, 'fields'):
                        # List of input objects - normalize enum fields in each item
                        for item in data:
                            if isinstance(item, dict):
                                for field_name, field_def in list_item_type.fields.items():
                                    if field_name in item:
                                        field_type = get_named_type(field_def.type)

                                        # Check if this field is a list of enums
                                        field_def_type = field_def.type
                                        # Unwrap NonNull wrappers
                                        while isinstance(field_def_type, GraphQLNonNull):
                                            field_def_type = field_def_type.of_type

                                        if isinstance(field_def_type, GraphQLList):
                                            # This field is a list - check if it's a list of enums
                                            list_item_type_inner = get_named_type(field_def_type.of_type)
                                            if isinstance(list_item_type_inner, GraphQLEnumType):
                                                # Handle list of enum values
                                                val = item[field_name]
                                                if isinstance(val, list):
                                                    normalized_list = []
                                                    for list_val in val:
                                                        if list_val not in list_item_type_inner.values:
                                                            # Try to map VALUE->NAME for each item in the list
                                                            for enum_name, enum_value in list_item_type_inner.values.items():
                                                                try:
                                                                    if (enum_value.value == list_val
                                                                            or str(enum_value.value) == str(list_val)):
                                                                        normalized_list.append(enum_name)
                                                                        break
                                                                except Exception:
                                                                    continue
                                                            else:
                                                                # If no mapping found, keep original value
                                                                normalized_list.append(list_val)
                                                        else:
                                                            # Value is already a valid enum name
                                                            normalized_list.append(list_val)
                                                    item[field_name] = normalized_list
                                        elif isinstance(field_type, GraphQLEnumType):
                                            val = item[field_name]
                                            # Handle single enum values only (lists are handled above)
                                            if not isinstance(val, list) and val not in field_type.values:
                                                # Try to map VALUE->NAME using same logic as existing normalization
                                                for enum_name, enum_value in field_type.values.items():
                                                    try:
                                                        # Handle both string and integer comparisons
                                                        if (enum_value.value == val
                                                                or str(enum_value.value) == str(val)):
                                                            item[field_name] = enum_name
                                                            break
                                                    except Exception:
                                                        continue

                # Handle single input object (contains enum fields)
                named = get_named_type(arg_def.type)
                if isinstance(named, GraphQLInputObjectType) and isinstance(data, dict):
                    # Process enum fields within the input object
                    for field_name, field_def in named.fields.items():
                        if field_name in data:
                            # Handle both direct enum fields and list enum fields
                            field_def_type = field_def.type
                            # Unwrap NonNull wrappers
                            while isinstance(field_def_type, GraphQLNonNull):
                                field_def_type = field_def_type.of_type

                            # Check if this field is a list
                            if isinstance(field_def_type, GraphQLList):
                                list_item_type = get_named_type(field_def_type.of_type)
                                val = data[field_name]
                                if isinstance(val, list):
                                    if isinstance(list_item_type, GraphQLEnumType):
                                        # Handle list of enums
                                        converted_list = []
                                        for item in val:
                                            if item not in list_item_type.values:
                                                # Convert enum value to name
                                                for enum_name, enum_value in list_item_type.values.items():
                                                    try:
                                                        if str(enum_value.value) == str(item):
                                                            converted_list.append(enum_name)
                                                            break
                                                    except Exception:
                                                        continue
                                                else:
                                                    # If no conversion found, keep original
                                                    converted_list.append(item)
                                            else:
                                                # Already a valid enum name
                                                converted_list.append(item)
                                        data[field_name] = converted_list
                                    elif isinstance(list_item_type, GraphQLInputObjectType):
                                        # Handle list of input objects (nested structures)
                                        for list_item in val:
                                            if isinstance(list_item, dict):
                                                # Recursively process each input object in the list
                                                for nested_field_name, nested_field_def in list_item_type.fields.items():
                                                    if nested_field_name in list_item:
                                                        nested_field_type = get_named_type(nested_field_def.type)
                                                        if isinstance(nested_field_type, GraphQLEnumType):
                                                            nested_val = list_item[nested_field_name]
                                                            # Convert enum value to name if needed
                                                            if nested_val not in nested_field_type.values:
                                                                for enum_name, enum_value in nested_field_type.values.items():
                                                                    try:
                                                                        if str(enum_value.value) == str(nested_val):
                                                                            list_item[nested_field_name] = enum_name
                                                                            break
                                                                    except Exception:
                                                                        continue
                                                        elif isinstance(nested_field_type, GraphQLList):
                                                            # Handle nested lists (like list of enums within input object)
                                                            nested_field_list_type = nested_field_def.type
                                                            # Unwrap NonNull wrappers for list fields
                                                            while isinstance(nested_field_list_type, GraphQLNonNull):
                                                                nested_field_list_type = nested_field_list_type.of_type
                                                            if isinstance(nested_field_list_type, GraphQLList):
                                                                nested_list_item_type = get_named_type(nested_field_list_type.of_type)
                                                                if isinstance(nested_list_item_type, GraphQLEnumType) and isinstance(list_item[nested_field_name], list):
                                                                    converted_nested_list = []
                                                                    for nested_item in list_item[nested_field_name]:
                                                                        if nested_item not in nested_list_item_type.values:
                                                                            for enum_name, enum_value in nested_list_item_type.values.items():
                                                                                try:
                                                                                    if str(enum_value.value) == str(nested_item):
                                                                                        converted_nested_list.append(enum_name)
                                                                                        break
                                                                                except Exception:
                                                                                    continue
                                                                            else:
                                                                                converted_nested_list.append(nested_item)
                                                                        else:
                                                                            converted_nested_list.append(nested_item)
                                                                    list_item[nested_field_name] = converted_nested_list
                            else:
                                # Handle single enum field
                                field_type = get_named_type(field_def.type)
                                if isinstance(field_type, GraphQLEnumType):
                                    val = data[field_name]
                                    # Convert enum value to name if needed
                                    if val not in field_type.values:
                                        for enum_name, enum_value in field_type.values.items():
                                            try:
                                                if str(enum_value.value) == str(val):
                                                    data[field_name] = enum_name
                                                    break
                                            except Exception:
                                                continue
                    return data

                # Handle single enum values (non-list case)
                elif isinstance(named, GraphQLEnumType):
                    # Handle both string and integer input values
                    if data not in named.values:
                        for enum_name, enum_value in named.values.items():
                            try:
                                # Handle integer enum values
                                if isinstance(enum_value.value, int):
                                    if isinstance(data, int) and enum_value.value == data:
                                        return enum_name
                                    elif isinstance(data, str) and str(enum_value.value) == data:
                                        return enum_name
                                # Handle string enum values
                                elif str(enum_value.value) == str(data):
                                    return enum_name
                            except Exception:
                                continue

                return data
            except Exception as e:
                # If normalization fails, return original data to avoid breaking the request
                print(f"Warning: Enum normalization failed: {e}")
                return data

        if field.args:
            for arg_name, arg_def in field.args.items():
                if arg_name in processed_kwargs:
                    try:
                        # Apply recursive enum normalization
                        processed_kwargs[arg_name] = normalize_enum_values_recursively(
                            processed_kwargs[arg_name], arg_def
                        )
                    except Exception as e:
                        # Log the error and continue with original value
                        print(f"Warning: Failed to normalize enum values for {arg_name}: {e}")
                        # Keep original value

        operation_type = "mutation" if is_mutation else "query"
        arg_str = ", ".join(f"{name}: ${name}" for name in kwargs)
        selection_set = _build_selection_set(field.type)

        query_str = f"{operation_type} ({', '.join(arg_defs)}) {{ {field_name}({arg_str}) {selection_set} }}"
        if not arg_defs:
            query_str = f"{operation_type} {{ {field_name} {selection_set} }}"

        try:
            result = await graphql(schema, query_str, variable_values=processed_kwargs)
        except Exception as e:
            print(f"Error executing GraphQL query: {e}")
            print(f"Query: {query_str}")
            print(f"Variables: {processed_kwargs}")
            raise

        if result.errors:
            # Log detailed error information for debugging
            print(f"GraphQL errors for {field_name}: {[str(err) for err in result.errors]}")
            print(f"Query: {query_str}")
            print(f"Variables: {processed_kwargs}")
            # For simplicity, just raise the first error
            raise result.errors[0]

        if result.data:
            raw_data = result.data.get(field_name)
            # Convert enum names back to values for MCP validation
            processed_data = _convert_enum_names_to_values_in_output(raw_data, field.type)
            return processed_data

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


class GraphQLRootMiddleware:
    def __init__(self, app: ASGIApp, graphql_app: ASGIApp) -> None:
        self.app = app
        self.graphql_app = graphql_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path") or ""
        if scope.get("type") == "http" and not path.endswith("/mcp") and not path.endswith("/mcp/"):
            await self.graphql_app(scope, receive, send)
            return
        if scope['type'] == 'http':
            path = scope['path']
            if path.endswith('/mcp/'):
                new_path = path[:-1]
                scope['path'] = new_path
                if 'raw_path' in scope:
                    scope['raw_path'] = new_path.encode()
        await self.app(scope, receive, send)


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

    # Build static query for this nested path
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
                # For GraphQL input objects, convert Pydantic models to dicts
                # Use mode="json" to properly serialize enums and other complex types
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, list):
                # Handle lists that might contain Pydantic models
                processed_list = []
                for item in v:
                    if hasattr(item, "model_dump"):
                        # Convert Pydantic model to dict for GraphQL
                        # Use mode="json" to properly serialize enums and other complex types
                        processed_list.append(item.model_dump(mode="json"))
                    elif isinstance(item, dict):
                        processed_list.append(item)
                    else:
                        processed_list.append(item)
                processed_kwargs[k] = processed_list
            elif isinstance(v, dict):
                # Check if this dict argument maps to a JSON scalar or an Input Object Type
                # For nested paths, find the correct field definition
                field_def = None
                for idx, (field_name, fd) in enumerate(path):
                    # Check if this variable belongs to this field level
                    if idx == len(path) - 1:  # Leaf field
                        if k in fd.args:
                            field_def = fd.args[k]
                            break
                    else:  # Intermediate field
                        var_name = f"{field_name}_{k}" if f"{field_name}_{k}" in kwargs else k
                        if var_name == k and k.startswith(f"{field_name}_"):
                            actual_arg = k[len(f"{field_name}_"):]
                            if actual_arg in fd.args:
                                field_def = fd.args[actual_arg]
                                break

                if field_def:
                    named_type = get_named_type(field_def.type)
                    if isinstance(named_type, GraphQLInputObjectType):
                        processed_kwargs[k] = v
                    else:
                        # Likely a JSON scalar type - convert to JSON string
                        processed_kwargs[k] = json.dumps(v)
                else:
                    # Default: convert to JSON string for backward compatibility
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

        # Convert enum names to values for MCP validation
        processed_data = _convert_enum_names_to_values_in_output(data_cursor, path[-1][1].type)
        return processed_data

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
                # For remote GraphQL, convert Pydantic models to dicts
                # Use mode="json" to properly serialize enums and other complex types
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, list):
                # Handle lists that might contain Pydantic models
                processed_list = []
                for item in v:
                    if hasattr(item, "model_dump"):
                        # Convert Pydantic model to dict for GraphQL
                        # Use mode="json" to properly serialize enums and other complex types
                        processed_list.append(item.model_dump(mode="json"))
                    elif isinstance(item, dict):
                        processed_list.append(item)
                    else:
                        processed_list.append(item)
                processed_kwargs[k] = processed_list
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

        # Build GraphQL query (only include variables that are not Undefined)
        from graphql.pyutils import Undefined
        operation_type = "mutation" if is_mutation else "query"
        arg_str = ", ".join(
            f"{name}: ${name}" for name, value in processed_kwargs.items() if value is not Undefined
        )
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
            message = str(e)
            lower = message.lower()
            if "timed out" in lower or "504" in lower:
                raise ToolError("The remote GraphQL endpoint timed out. Try again or narrow the request.")
            if "unavailable" in lower or "503" in lower or "502" in lower:
                raise ToolError("The remote GraphQL endpoint is temporarily unavailable. Please try again.")
            if "unauthorized" in lower or "forbidden" in lower or "401" in lower or "403" in lower:
                raise ToolError("Authentication failed for the remote GraphQL endpoint.")
            raise ToolError(f"Remote GraphQL execution failed: {message}")

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

    # Build nested call string dynamically based on provided variables
    def _build_call_filtered(index: int, provided: set[str]) -> str:
        field_name, field_def = path[index]
        if field_def.args:
            arg_str_parts: list[str] = []
            for arg in field_def.args.keys():
                var_name = arg if index == len(path) - 1 else f"{field_name}_{arg}"
                if var_name in provided:
                    arg_str_parts.append(f"{arg}: ${var_name}")
            if arg_str_parts:
                call = f"{field_name}({', '.join(arg_str_parts)})"
            else:
                call = field_name
        else:
            call = field_name

        if index == len(path) - 1:
            selection_set = _build_selection_set(field_def.type)
            return f"{call} {selection_set}"

        return f"{call} {{ {_build_call_filtered(index + 1, provided)} }}"

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
                # For remote GraphQL, convert Pydantic models to dicts
                # Use mode="json" to properly serialize enums and other complex types
                processed_kwargs[k] = v.model_dump(mode="json")
            elif isinstance(v, list):
                # Handle lists that might contain Pydantic models
                processed_list = []
                for item in v:
                    if hasattr(item, "model_dump"):
                        # Convert Pydantic model to dict for GraphQL
                        # Use mode="json" to properly serialize enums and other complex types
                        processed_list.append(item.model_dump(mode="json"))
                    elif isinstance(item, dict):
                        processed_list.append(item)
                    else:
                        processed_list.append(item)
                processed_kwargs[k] = processed_list
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

        # Build query using only provided variables
        provided_vars = set(processed_kwargs.keys())

        # Build filtered variable declarations
        filtered_arg_defs: list[str] = []
        for idx, (fname, fdef) in enumerate(path):
            for arg in fdef.args.keys():
                var_name = arg if idx == len(path) - 1 else f"{fname}_{arg}"
                if var_name in provided_vars:
                    filtered_arg_defs.append(f"${var_name}: {_get_graphql_type_name(fdef.args[arg].type)}")

        arg_def_str = ", ".join(filtered_arg_defs)
        operation_header = (
            f"{operation_type} ({arg_def_str})" if arg_def_str else operation_type
        )
        graphql_body = _build_call_filtered(0, provided_vars)
        query_str = f"{operation_header} {{ {graphql_body} }}"

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
            message = str(e)
            lower = message.lower()
            if "timed out" in lower or "504" in lower:
                raise ToolError("The remote GraphQL endpoint timed out. Try again or narrow the request.")
            if "unavailable" in lower or "503" in lower or "502" in lower:
                raise ToolError("The remote GraphQL endpoint is temporarily unavailable. Please try again.")
            if "unauthorized" in lower or "forbidden" in lower or "401" in lower or "403" in lower:
                raise ToolError("Authentication failed for the remote GraphQL endpoint.")
            raise ToolError(f"Remote GraphQL execution failed: {message}")

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
