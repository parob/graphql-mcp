import enum
import pytest

from fastmcp.client import Client

from graphql_mcp.server import add_tools_from_schema
from tests.test_graphql_mcp import get_result_text


@pytest.mark.asyncio
async def test_graphql_generated_tool_sends_enum_name_for_variables():
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class PreferenceKey(str, enum.Enum):
        AI_MODEL = "ai_model"
        TOOLS_ENABLED = "tools_enabled"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def echo_preference(self, key: PreferenceKey) -> str:
            # GraphQL resolvers receive enum VALUEs; echo back the value we received
            if isinstance(key, str):
                try:
                    key = PreferenceKey[key]
                except KeyError:
                    key = PreferenceKey(key)
            return key.value

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Pass a Python Enum instance; the wrapper should convert to the GraphQL enum NAME
        result = await client.call_tool("echo_preference", {"key": PreferenceKey.AI_MODEL})
        assert get_result_text(result) == "ai_model"
