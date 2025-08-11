import enum

from fastmcp import Client
from graphql_api import GraphQLAPI

from graphql_mcp.server import GraphQLMCPServer

api = GraphQLAPI()

class PreferenceKey(str, enum.Enum):
    AI_MODEL = "ai_model"
    TOOLS_ENABLED = "tools_enabled"

@api.type(is_root_type=True)
class DemoApp:
    @api.field
    def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
        if isinstance(key, PreferenceKey):
            return True
        else:
            return False


mcp_server = GraphQLMCPServer(api=api)


# Add an addition tool
@mcp_server.tool()
def set_preference(key: PreferenceKey, value: str) -> bool:
    """Set a preference"""
    if isinstance(key, PreferenceKey):
        return True
    else:
        return False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_server.http_app, host="0.0.0.0", port=8010)