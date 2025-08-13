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
    timeout: int = 30
) -> GraphQLSchema:
    """
    Fetches a GraphQL schema from a remote server via introspection.

    Args:
        url: The GraphQL endpoint URL
        headers: Optional headers to include in the request (e.g., authorization)
        timeout: Request timeout in seconds

    Returns:
        GraphQLSchema: The fetched and built schema

    Raises:
        Exception: If the introspection query fails
    """
    introspection_query = get_introspection_query()

    payload = {
        "query": introspection_query,
    }

    async with aiohttp.ClientSession() as session:
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
    timeout: int = 30
) -> GraphQLSchema:
    """
    Synchronous wrapper for fetching a remote GraphQL schema.

    Args:
        url: The GraphQL endpoint URL
        headers: Optional headers to include in the request
        timeout: Request timeout in seconds

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
                fetch_remote_schema(url, headers, timeout)
            )
            return schema
        finally:
            loop.close()
    else:
        # There's already a loop running, use nest_asyncio or create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_remote_schema(url, headers, timeout))
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
        verify_ssl: bool = True
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
        """
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.bearer_token = bearer_token
        self.token_refresh_callback = token_refresh_callback
        self.verify_ssl = verify_ssl
        self._session: Optional[aiohttp.ClientSession] = None

        # Schema introspection cache for type-aware transformations
        self._schema_cache = {}
        self._array_fields_cache = {}
        self._introspected = False

        # Add bearer token to headers if provided
        if self.bearer_token:
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"

    def _clean_variables(self, variables: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert Undefined values to None to avoid GraphQL validation errors."""
        if not variables:
            return variables
            
        cleaned = {}
        for key, value in variables.items():
            if value is Undefined:
                # Convert Undefined to None instead of removing entirely
                # This prevents GraphQL validation errors for required parameters
                cleaned[key] = None
            elif isinstance(value, dict):
                # Recursively clean nested dictionaries
                cleaned_nested = self._clean_variables(value)
                if cleaned_nested is not None:  # Include even empty dicts
                    cleaned[key] = cleaned_nested
            elif isinstance(value, list):
                # Clean lists by converting Undefined values to None and recursively cleaning nested dicts
                cleaned_list = []
                for item in value:
                    if item is Undefined:
                        cleaned_list.append(None)
                    elif isinstance(item, dict):
                        cleaned_item = self._clean_variables(item)
                        cleaned_list.append(cleaned_item)
                    else:
                        cleaned_list.append(item)
                cleaned[key] = cleaned_list
            else:
                cleaned[key] = value
        
        return cleaned if cleaned else None

    def _remove_unused_variables_from_query(self, query: str, variables: Optional[Dict[str, Any]]) -> str:
        """Remove variable declarations from GraphQL query when variables are not provided."""
        if not variables:
            # Remove all variable declarations if no variables provided
            import re
            # Remove the entire variable declaration part: (...)
            return re.sub(r'\([^)]*\)', '', query, count=1)
        
        import re
        
        # Find variable declarations and filter them
        var_decl_match = re.search(r'\(([^)]+)\)', query)
        if not var_decl_match:
            return query
            
        original_vars = var_decl_match.group(1)
        var_declarations = []
        
        # Split variable declarations by comma
        for var_decl in original_vars.split(','):
            var_decl = var_decl.strip()
            if var_decl:
                # Extract variable name (e.g., "$dateGrouping" from "$dateGrouping: DateGrouping!")
                var_name_match = re.match(r'\$(\w+)', var_decl)
                if var_name_match:
                    var_name = var_name_match.group(1)
                    # Only keep this declaration if we have the variable
                    if var_name in variables:
                        var_declarations.append(var_decl)
        
        if var_declarations:
            # Reconstruct the query with filtered variable declarations
            new_var_part = '(' + ', '.join(var_declarations) + ')'
            return query.replace(var_decl_match.group(0), new_var_part, 1)
        else:
            # No variables left, remove the declaration part entirely
            return query.replace(var_decl_match.group(0), '', 1)

    def _transform_null_arrays(self, data: Any, parent_key: str = '', type_context: Optional[str] = None) -> Any:
        """Transform null values to empty arrays based on GraphQL schema types."""
        if isinstance(data, dict):
            transformed = {}
            
            # Try to infer the GraphQL type context from the data structure
            # This is a simple heuristic - in a real implementation you'd track this more precisely
            current_type_context = type_context
            
            for key, value in data.items():
                if value is None and self._should_convert_to_array(key, value, data, current_type_context):
                    transformed[key] = []
                else:
                    # Recursively transform nested structures
                    transformed[key] = self._transform_null_arrays(value, key, current_type_context)
            return transformed
        elif isinstance(data, list):
            return [self._transform_null_arrays(item, parent_key, type_context) for item in data]
        else:
            return data

    async def _raw_execute_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Raw GraphQL request without transformation - used for introspection."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

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
            
            # Parse schema and cache array fields
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
    
    def _should_convert_to_array(self, key: str, value: Any, siblings: Dict[str, Any], type_context: Optional[str] = None) -> bool:
        """Determine if a null value should become an empty array based on GraphQL schema types."""
        if value is not None:
            return False
        
        # First try to use cached schema information
        if self._introspected and type_context:
            type_fields = self._array_fields_cache.get(type_context, {})
            if key in type_fields:
                return type_fields[key]
        
        # If we don't have schema info, fall back to analyzing data structure patterns
        # Look at sibling fields to infer if this should be an array
        for sibling_key, sibling_value in siblings.items():
            if (sibling_key == key and 
                isinstance(sibling_value, list)):
                return True
                
        # Fallback to field name heuristics as last resort
        if (key.endswith('s') or key.endswith('es') or 
            key in ['children', 'items', 'results', 'data', 'list', 'components', 'systems']):
            return True
                
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

        # Clean variables to convert Undefined values to None
        cleaned_variables = self._clean_variables(variables)
        
        # Debug logging (only if debug level is enabled)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Original query: {query}")
            logger.debug(f"Original variables: {variables}")
            logger.debug(f"Cleaned variables: {cleaned_variables}")
        
        if cleaned_variables:
            payload["variables"] = cleaned_variables

        if operation_name:
            payload["operationName"] = operation_name
            
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Final payload: {payload}")

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
                        # Retry with refreshed token
                        if close_session:
                            await session.close()
                        return await self._execute_request(
                            query, variables, operation_name,
                            retry_on_auth_error=False,
                            headers=headers  # Use the updated headers with new token
                        )

                if response.status != 200:
                    text = await response.text()
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
                transformed_data = self._transform_null_arrays(data)
                return transformed_data
        finally:
            if close_session:
                await session.close()
