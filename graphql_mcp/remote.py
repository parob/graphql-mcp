"""Remote GraphQL server support for graphql-mcp."""

import aiohttp

from typing import Any, Dict, Optional, Callable
from graphql import (
    GraphQLSchema,
    build_client_schema,
    get_introspection_query
)
from graphql.pyutils import Undefined


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
        token_refresh_callback: Optional[Callable[[], str]] = None
    ):
        """
        Initialize a remote GraphQL client.

        Args:
            url: The GraphQL endpoint URL
            headers: Optional headers to include in requests
            timeout: Request timeout in seconds
            bearer_token: Optional Bearer token for authentication
            token_refresh_callback: Optional callback to refresh the bearer token
        """
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.bearer_token = bearer_token
        self.token_refresh_callback = token_refresh_callback
        self._session: Optional[aiohttp.ClientSession] = None

        # Add bearer token to headers if provided
        if self.bearer_token:
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"

    def _clean_variables(self, variables: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove or convert Undefined values from variables dictionary."""
        if not variables:
            return variables
            
        cleaned = {}
        for key, value in variables.items():
            if value is not Undefined:
                # Recursively clean nested dictionaries
                if isinstance(value, dict):
                    cleaned_nested = self._clean_variables(value)
                    if cleaned_nested:  # Only include non-empty dicts
                        cleaned[key] = cleaned_nested
                elif isinstance(value, list):
                    # Clean lists by filtering out Undefined values and recursively cleaning nested dicts
                    cleaned_list = []
                    for item in value:
                        if item is not Undefined:
                            if isinstance(item, dict):
                                cleaned_item = self._clean_variables(item)
                                if cleaned_item:  # Only include non-empty cleaned dicts
                                    cleaned_list.append(cleaned_item)
                            else:
                                cleaned_list.append(item)
                    if cleaned_list:  # Only include non-empty lists
                        cleaned[key] = cleaned_list
                else:
                    cleaned[key] = value
        
        return cleaned if cleaned else None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
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
        """
        payload = {
            "query": query,
        }

        # Clean variables to remove Undefined values
        cleaned_variables = self._clean_variables(variables)
        if cleaned_variables:
            payload["variables"] = cleaned_variables

        if operation_name:
            payload["operationName"] = operation_name

        # Use existing session or create temporary one
        if self._session:
            session = self._session
            close_session = False
        else:
            session = aiohttp.ClientSession()
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

                return result.get("data", {})
        finally:
            if close_session:
                await session.close()
