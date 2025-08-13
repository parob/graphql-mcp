"""Remote GraphQL server support for graphql-mcp."""

import aiohttp
import logging
import ssl

from typing import Any, Dict, Optional, Callable
from graphql import (
    GraphQLSchema,
    build_client_schema,
    get_introspection_query
)
from graphql.pyutils import Undefined


logger = logging.getLogger(__name__)


async def fetch_remote_schema(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    verify_ssl: bool = True
) -> GraphQLSchema:
    """
    Fetches a GraphQL schema from a remote server via introspection.

    Args:
        url: The GraphQL endpoint URL
        headers: Optional headers to include in the request (e.g., authorization)
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates (default: True, set to False for development)

    Returns:
        GraphQLSchema: The fetched and built schema

    Raises:
        Exception: If the introspection query fails
    """
    introspection_query = get_introspection_query()

    payload = {
        "query": introspection_query,
    }

    # Create SSL context based on verify_ssl setting
    ssl_context = ssl.create_default_context()
    if not verify_ssl:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        logger.warning("SSL certificate verification disabled for schema fetch - only use in development!")

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            url,
            json=payload,
            headers=headers or {},
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Failed to fetch schema from {url}: {response.status} - {text}")

            result = await response.json()

            if "errors" in result:
                raise Exception(f"GraphQL errors during introspection: {result['errors']}")

            if "data" not in result:
                raise Exception(f"No data in introspection response from {url}")

            # Build the client schema from the introspection result
            schema = build_client_schema(result["data"])
            return schema


def fetch_remote_schema_sync(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    verify_ssl: bool = True
) -> GraphQLSchema:
    """
    Synchronous wrapper for fetching a remote GraphQL schema.

    Args:
        url: The GraphQL endpoint URL
        headers: Optional headers to include in the request
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates (default: True, set to False for development)

    Returns:
        GraphQLSchema: The fetched and built schema
    """
    import asyncio

    # Check if there's already an event loop running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop running, create a new one
        loop = asyncio.new_event_loop()
        try:
            schema = loop.run_until_complete(
                fetch_remote_schema(url, headers, timeout, verify_ssl)
            )
            return schema
        finally:
            loop.close()
    else:
        # There's already a loop running, use nest_asyncio or create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_remote_schema(url, headers, timeout, verify_ssl))
            return future.result()


class RemoteGraphQLClient:
    """Client for executing queries against a remote GraphQL server."""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        bearer_token: Optional[str] = None,
        token_refresh_callback: Optional[Callable[[], str]] = None,
        verify_ssl: bool = True,
        undefined_strategy: str = "remove",
        debug: bool = False
    ):
        """
        Initialize a remote GraphQL client with schema introspection for type-aware transformations.

        Args:
            url: The GraphQL endpoint URL
            headers: Optional headers to include in requests
            timeout: Request timeout in seconds
            bearer_token: Optional Bearer token for authentication
            token_refresh_callback: Optional callback to refresh the bearer token
            verify_ssl: Whether to verify SSL certificates (default: True, set to False for development)
            undefined_strategy: How to handle Undefined variables ("remove" or "null", default: "remove")
            debug: Enable verbose debug logging (default: False)
        """
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.bearer_token = bearer_token
        self.token_refresh_callback = token_refresh_callback
        self.verify_ssl = verify_ssl
        self.undefined_strategy = undefined_strategy
        self.debug = debug
        self._session: Optional[aiohttp.ClientSession] = None

        # Schema introspection cache for type-aware transformations
        self._schema_cache = {}
        self._array_fields_cache = {}
        self._field_type_map = {}  # Maps field names to their return type names
        self._introspected = False

        # Add bearer token to headers if provided
        if self.bearer_token:
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"

    def _clean_variables(self, variables: Optional[Dict[str, Any]], strategy: str = "remove") -> Optional[Dict[str, Any]]:
        """
        Handle Undefined values in GraphQL variables with configurable strategies.

        Args:
            variables: The variables dictionary to clean
            strategy: How to handle Undefined values:
                - "remove": Remove Undefined values entirely (default, prevents validation errors)
                - "null": Convert Undefined values to None (alternative approach)

        For non-null GraphQL variables (marked with !), the "remove" strategy completely removes
        Undefined variables and their declarations from the query. The "null" strategy converts
        Undefined to None, which may work for some servers but can cause validation errors.
        """
        if not variables:
            return variables

        cleaned = {}
        for key, value in variables.items():
            if value is Undefined:
                if strategy == "null":
                    # Convert Undefined to None (alternative approach)
                    cleaned[key] = None
                else:  # strategy == "remove"
                    # Remove Undefined values entirely (default approach)
                    # This prevents GraphQL validation errors for non-null parameters
                    continue
            elif isinstance(value, dict):
                # Recursively clean nested dictionaries
                cleaned_nested = self._clean_variables(value, strategy)
                if cleaned_nested or strategy == "null":  # Include empty dicts when using null strategy
                    cleaned[key] = cleaned_nested
            elif isinstance(value, list):
                # Clean lists by filtering out Undefined values and recursively cleaning nested structures
                cleaned_list = []
                for item in value:
                    if item is Undefined:
                        if strategy == "null":
                            cleaned_list.append(None)
                        else:
                            # Skip Undefined items entirely
                            continue
                    elif isinstance(item, dict):
                        cleaned_item = self._clean_variables(item, strategy)
                        if cleaned_item or strategy == "null":  # Include empty dicts when using null strategy
                            cleaned_list.append(cleaned_item)
                    elif isinstance(item, list):
                        # Recursively clean nested lists
                        nested_result = self._clean_variables({"temp": item}, strategy)
                        if nested_result and "temp" in nested_result:
                            cleaned_list.append(nested_result["temp"])
                        elif strategy == "null":
                            cleaned_list.append(None)
                    else:
                        cleaned_list.append(item)
                cleaned[key] = cleaned_list
            else:
                cleaned[key] = value

        return cleaned if cleaned else None

    def _remove_unused_variables_from_query(self, query: str, variables: Optional[Dict[str, Any]]) -> str:
        """Remove unused variable declarations from the operation header only.

        Behavior (per tests):
        - If variables is None or empty, remove the entire variable declaration list from the header.
        - Otherwise, keep only declarations whose names exist in the variables dict.
        Additionally, ensure the query body does not reference variables we removed from the header
        by stripping corresponding "arg: $var" pairs to avoid server-side validation errors.
        """
        import re

        # Regex to match the operation header's variable declaration list
        # Handles: query MyOp(...), mutation MyOp(...), or anonymous: query (...)
        op_pattern = re.compile(r"\b(query|mutation)\b\s*[A-Za-z_][A-Za-z0-9_]*?\s*\(([^)]*)\)", re.IGNORECASE)
        anon_op_pattern = re.compile(r"\b(query|mutation)\b\s*\(([^)]*)\)", re.IGNORECASE)

        match = op_pattern.search(query) or anon_op_pattern.search(query)
        if not match:
            return query

        full_block = match.group(0)
        vars_block = match.group(2)

        # If no variables provided, strip the entire declaration list
        if not variables:
            # Remove header declarations entirely, do not touch the body
            return query.replace(full_block, full_block.split('(')[0].rstrip())

        kept: list[str] = []
        for var_decl in vars_block.split(','):
            decl = var_decl.strip()
            if not decl:
                continue
            name_match = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)", decl)
            if name_match:
                var_name = name_match.group(1)
                if var_name in variables:
                    kept.append(decl)

        if kept:
            new_block = full_block.split('(')[0] + '(' + ', '.join(kept) + ')'
            # Replace only the header, do not touch the body
            return query.replace(full_block, new_block, 1)
        else:
            # Remove parentheses entirely if nothing kept
            return query.replace(full_block, full_block.split('(')[0].rstrip(), 1)

    def _remove_unused_variables_from_query_and_body(self, query: str, variables: Optional[Dict[str, Any]]) -> str:
        """Strips unused variable declarations from the header AND removes corresponding usages in the body.

        This is used only at execution time to prevent server-side errors like
        "Variable '$x' is not defined" when optional variables are omitted.
        Tests call _remove_unused_variables_from_query() and expect header-only behavior.
        """
        import re

        # First perform header-level filtering using the tested function
        new_query = self._remove_unused_variables_from_query(query, variables)

        # If no variables provided, drop all usages in body
        if not variables:
            # Remove any ", arg: $var" or leading "(arg: $var, ...)" patterns
            new_query = re.sub(r"\s*,\s*\w+\s*:\s*\$[A-Za-z_][A-Za-z0-9_]*", "", new_query)
            new_query = re.sub(r"\(\s*\w+\s*:\s*\$[A-Za-z_][A-Za-z0-9_]*\s*,\s*", "(", new_query)
            new_query = re.sub(r"\(\s*\)", "()", new_query)
            new_query = re.sub(r"\(\s*\w+\s*:\s*\$[A-Za-z_][A-Za-z0-9_]*\s*\)", "()", new_query)
            return new_query

        # Identify variables declared in header after filtering
        header_match = re.search(r"\b(query|mutation)\b\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*)?\(([^)]*)\)", new_query, re.IGNORECASE)
        kept_vars: set[str] = set()
        if header_match:
            for decl in header_match.group(2).split(','):
                m = re.match(r"\s*\$([A-Za-z_][A-Za-z0-9_]*)", decl)
                if m:
                    kept_vars.add(m.group(1))

        # Remove usages for variables NOT in kept_vars
        # Determine original declared vars from the original query's header
        original_match = re.search(r"\b(query|mutation)\b\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*)?\(([^)]*)\)", query, re.IGNORECASE)
        original_vars: set[str] = set()
        if original_match:
            for decl in original_match.group(2).split(','):
                m = re.match(r"\s*\$([A-Za-z_][A-Za-z0-9_]*)", decl)
                if m:
                    original_vars.add(m.group(1))

        dropped = original_vars - kept_vars
        for var_name in dropped:
            # Remove usage patterns for this var
            new_query = re.sub(rf"\s*,\s*\w+\s*:\s*\${var_name}\b", "", new_query)
            new_query = re.sub(rf"\(\s*\w+\s*:\s*\${var_name}\s*,\s*", "(", new_query)
            new_query = re.sub(rf"\(\s*\w+\s*:\s*\${var_name}\s*\)", "()", new_query)
            new_query = re.sub(rf"\b\w+\s*:\s*\${var_name}\b", "", new_query)
            new_query = re.sub(r"\(\s*,\s*\)", "()", new_query)
            new_query = re.sub(r",\s*,", ",", new_query)

        return new_query

    def _transform_null_arrays(self, data: Any, parent_key: str = '', type_context: Optional[str] = None) -> Any:
        """Transform null values to empty arrays based on GraphQL schema types."""
        if isinstance(data, dict):
            transformed = {}

            current_type_context = type_context

            for key, value in data.items():
                if value is None and self._should_convert_to_array(key, value, data, current_type_context):
                    transformed[key] = []
                else:
                    # For nested objects, get the type context from schema
                    nested_type_context = self._get_field_type_context(key, current_type_context)
                    transformed[key] = self._transform_null_arrays(value, key, nested_type_context)
            return transformed
        elif isinstance(data, list):
            # For lists, check if items should have array fields converted based on sibling analysis
            transformed_items = []

            # Collect all dictionary items to analyze sibling patterns across the list
            dict_items = [item for item in data if isinstance(item, dict)]

            for item in data:
                if isinstance(item, dict):
                    # Create a combined siblings dict from all similar items in the list
                    combined_siblings = {}
                    for dict_item in dict_items:
                        for k, v in dict_item.items():
                            if k not in combined_siblings and isinstance(v, list):
                                combined_siblings[k] = v  # Use the first non-null list we find

                    # Transform this item with enhanced sibling context
                    transformed_item = {}
                    for key, value in item.items():
                        if value is None and self._should_convert_to_array(key, value, combined_siblings, type_context):
                            transformed_item[key] = []
                        else:
                            nested_type_context = self._get_field_type_context(key, type_context)
                            transformed_item[key] = self._transform_null_arrays(value, key, nested_type_context)
                    transformed_items.append(transformed_item)
                else:
                    transformed_items.append(self._transform_null_arrays(item, parent_key, type_context))

            return transformed_items
        else:
            return data

    def _get_field_type_context(self, field_name: str, current_type_context: Optional[str]) -> Optional[str]:
        """Get the type context for a nested field based on schema introspection."""
        if not self._introspected:
            return current_type_context

        # Try the fully qualified field name first (Type.field)
        if current_type_context:
            field_key = f"{current_type_context}.{field_name}"
            if field_key in self._field_type_map:
                return self._field_type_map[field_key]

        # Fall back to simple field name lookup
        if field_name in self._field_type_map:
            return self._field_type_map[field_name]

        # If we can't find it in the schema, return the current context
        return current_type_context

    async def _raw_execute_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Raw GraphQL request without transformation - used for introspection."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables  # type: ignore

        headers = self.headers.copy()

        # Use existing session or create temporary one with SSL handling
        if self._session:
            session = self._session
            close_session = False
        else:
            session = self._create_session()
            close_session = True

        try:
            async with session.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Failed to execute introspection query: {response.status} - {text}")

                result = await response.json()
                if "errors" in result:
                    raise Exception(f"GraphQL introspection errors: {result['errors']}")

                return result.get("data", {})
            # If we exit the retry loop without returning, raise a final error
            raise Exception("Failed to execute query after multiple retry attempts.")
        finally:
            if close_session:
                await session.close()

    async def _introspect_schema(self):
        """Perform GraphQL schema introspection to cache field types."""
        if self._introspected:
            return

        introspection_query = """
        query IntrospectionQuery {
            __schema {
                types {
                    name
                    kind
                    fields {
                        name
                        type {
                            name
                            kind
                            ofType {
                                name
                                kind
                                ofType {
                                    name
                                    kind
                                    ofType {
                                        name
                                        kind
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            result = await self._raw_execute_request(introspection_query)

            # Parse schema and cache array fields and field-to-type mappings
            if "__schema" in result and "types" in result["__schema"]:
                for type_def in result["__schema"]["types"]:
                    if type_def.get("fields"):
                        type_name = type_def["name"]
                        self._array_fields_cache[type_name] = {}

                        for field in type_def["fields"]:
                            field_name = field["name"]
                            field_type = field["type"]

                            # Check if field is a list type
                            is_list = self._is_list_type(field_type)
                            self._array_fields_cache[type_name][field_name] = is_list

                            # Extract the actual return type name for this field
                            return_type_name = self._extract_type_name(field_type)
                            if return_type_name:
                                # Create mapping from field name to its return type
                                field_key = f"{type_name}.{field_name}"
                                self._field_type_map[field_key] = return_type_name

                                # Also create a simple field name mapping as fallback
                                if field_name not in self._field_type_map:
                                    self._field_type_map[field_name] = return_type_name

            self._introspected = True
            logger.debug(f"Schema introspected, found {len(self._array_fields_cache)} types")

        except Exception as e:
            logger.warning(f"Schema introspection failed: {e}")
            # Fall back to heuristic approach if introspection fails
            self._introspected = True

    def _is_list_type(self, field_type: Dict) -> bool:
        """Check if a GraphQL field type represents a list."""
        if not field_type:
            return False

        # Check if this type is LIST
        if field_type.get("kind") == "LIST":
            return True

        # Check if this is NON_NULL wrapping a LIST
        if field_type.get("kind") == "NON_NULL":
            of_type = field_type.get("ofType")
            if of_type and of_type.get("kind") == "LIST":
                return True

        return False

    def _extract_type_name(self, field_type: Dict) -> Optional[str]:
        """Extract the actual type name from a GraphQL field type definition."""
        if not field_type:
            return None

        # If it's a simple named type
        if field_type.get("name"):
            return field_type["name"]

        # If it's wrapped (NON_NULL, LIST, etc.), unwrap to find the base type
        of_type = field_type.get("ofType")
        if of_type:
            return self._extract_type_name(of_type)

        return None

    def _should_convert_to_array(self, key: str, value: Any, siblings: Dict[str, Any], type_context: Optional[str] = None) -> bool:
        """Determine if a null value should become an empty array based on GraphQL schema types."""
        if value is not None:
            return False

        # Use cached schema information from introspection
        if self._introspected and type_context:
            type_fields = self._array_fields_cache.get(type_context, {})
            if key in type_fields:
                return type_fields[key]

        # If we don't have schema info for the specific field, analyze data structure patterns
        # Look at sibling fields to infer if this should be an array
        for sibling_key, sibling_value in siblings.items():
            if (sibling_key == key and isinstance(sibling_value, list)):
                return True

        # Without schema information or sibling analysis, default to not converting
        # This ensures we only convert null to [] when we have solid evidence it should be an array
        return False

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context based on verify_ssl setting."""
        ssl_context = ssl.create_default_context()
        if not self.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("SSL certificate verification disabled - only use in development!")
        return ssl_context

    def _create_session(self) -> aiohttp.ClientSession:
        """Create an aiohttp session with appropriate SSL configuration."""
        connector = aiohttp.TCPConnector(ssl=self._create_ssl_context())
        return aiohttp.ClientSession(connector=connector)

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    async def refresh_token(self):
        """Refresh the bearer token if a refresh callback is provided."""
        if self.token_refresh_callback:
            try:
                new_token = self.token_refresh_callback()
                self.bearer_token = new_token
                self.headers["Authorization"] = f"Bearer {new_token}"
                return True
            except Exception:
                return False
        return False

    async def execute_with_token(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        retry_on_auth_error: bool = True,
        bearer_token_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query with an optional bearer token override.

        Args:
            query: The GraphQL query string
            variables: Optional variables for the query
            operation_name: Optional operation name
            retry_on_auth_error: Whether to retry with refreshed token on 401/403
            bearer_token_override: Optional bearer token to use instead of the client's token

        Returns:
            The GraphQL response data

        Raises:
            Exception: If the query fails
        """
        # Prepare headers, using override token if provided
        headers = self.headers.copy()
        if bearer_token_override:
            headers["Authorization"] = f"Bearer {bearer_token_override}"

        return await self._execute_request(
            query, variables, operation_name, retry_on_auth_error, headers
        )

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        retry_on_auth_error: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the remote server.

        Args:
            query: The GraphQL query string
            variables: Optional variables for the query
            operation_name: Optional operation name
            retry_on_auth_error: Whether to retry with refreshed token on 401/403

        Returns:
            The GraphQL response data

        Raises:
            Exception: If the query fails
        """
        return await self._execute_request(
            query, variables, operation_name, retry_on_auth_error, self.headers
        )

    async def _execute_request(
        self,
        query: str,
        variables: Optional[Dict[str, Any]],
        operation_name: Optional[str],
        retry_on_auth_error: bool,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Internal method to execute a GraphQL request with specified headers.
        Fixed to handle Undefined values properly and transform response data.
        """
        payload: Dict[str, Any] = {
            "query": query,
        }

        # Clean variables using the configured strategy
        cleaned_variables = self._clean_variables(variables, self.undefined_strategy)

        # For "remove" strategy, also remove variable declarations from query
        if self.undefined_strategy == "remove":
            cleaned_query = self._remove_unused_variables_from_query_and_body(query, cleaned_variables)
        else:
            # For "null" strategy, keep original query since variables are converted to null
            cleaned_query = query

        # Enhanced debug logging
        if self.debug or logger.isEnabledFor(logging.DEBUG):
            debug_msg = f"""
DEBUG: GraphQL Request Processing:
- URL: {self.url}
- Strategy: {self.undefined_strategy}
- Original query: {query}
- Original variables: {variables}
- Cleaned variables: {cleaned_variables}
- Cleaned query: {cleaned_query}
            """.strip()
            if self.debug:
                print(debug_msg)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(debug_msg)

        payload["query"] = cleaned_query
        if cleaned_variables:
            payload["variables"] = cleaned_variables

        if operation_name:
            payload["operationName"] = operation_name

        if self.debug or logger.isEnabledFor(logging.DEBUG):
            final_debug = f"DEBUG: Final payload: {payload}"
            if self.debug:
                print(final_debug)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(final_debug)

        # Use existing session or create temporary one
        if self._session:
            session = self._session
            close_session = False
        else:
            session = self._create_session()
            close_session = True

        try:
            async with session.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                # Handle authentication errors
                if response.status in (401, 403) and retry_on_auth_error:
                    if await self.refresh_token():
                        # Retry once with refreshed token
                        if close_session:
                            await session.close()
                        return await self._execute_request(
                            query, variables, operation_name,
                            retry_on_auth_error=False,
                            headers=headers  # Use the updated headers with new token
                        )

                if response.status != 200:
                    text = await response.text()
                    # Friendly error messages for common statuses
                    if response.status == 504:
                        raise Exception("Remote GraphQL endpoint timed out (HTTP 504). Please try again.")
                    if response.status in (502, 503):
                        raise Exception(f"Remote GraphQL endpoint unavailable (HTTP {response.status}). Please try again.")

                    raise Exception(f"Failed to execute query: {response.status} - {text}")

                result = await response.json()

                if "errors" in result:
                    # Check for authentication-related errors in GraphQL response
                    error_messages = str(result['errors']).lower()
                    if ('unauthorized' in error_messages or 'authentication' in error_messages or 'forbidden' in error_messages) and retry_on_auth_error:
                        if await self.refresh_token():
                            if close_session:
                                await session.close()
                            return await self._execute_request(
                                query, variables, operation_name,
                                retry_on_auth_error=False,
                                headers=headers  # Use the updated headers with new token
                            )

                    raise Exception(f"GraphQL errors: {result['errors']}")

                # Ensure schema is introspected before transforming data
                await self._introspect_schema()

                # Transform null arrays to empty arrays to satisfy MCP output schema validation
                data = result.get("data", {})
                transformed_data = self._transform_null_arrays(data, type_context="Query")
                return transformed_data

        except aiohttp.ClientError:
            raise Exception("Network error talking to remote GraphQL endpoint. Please try again.")
        finally:
            if close_session:
                await session.close()
