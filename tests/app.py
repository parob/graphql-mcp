import enum
from graphql_api import GraphQLAPI, field

from graphql_mcp.server import GraphQLMCP


class PreferenceKey(str, enum.Enum):
    AI_MODEL = "ai_model"
    TOOLS_ENABLED = "tools_enabled"


class DemoApp:

    @field
    def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
        """Set a preference"""
        if isinstance(key, PreferenceKey):
            return True
        else:
            return False

    @field
    def get_preference_test(self) -> dict:
        """Get a preference"""
        return {"key": "ai_model", "value": "x"}


mcp_server = GraphQLMCP.from_api(api=GraphQLAPI(root_type=DemoApp))


# Add an addition standard fastmcp tool
@mcp_server.tool()
def clear_preferences() -> bool:
    """Clear all preferences"""
    return True


app = mcp_server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
