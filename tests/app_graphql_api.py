import asyncio
import uvicorn

from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP


class HelloWorldAPI:

    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"


api = GraphQLAPI(root_type=HelloWorldAPI)

server = GraphQLMCP.from_api(api)

mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)


async def demo_mcp():
    # Get available tools
    print(f"Available tools: {await server.get_tools()}")

    # Call the hello tool
    print(f"Query result: {await server._mcp_call_tool('hello', arguments={'name': 'Rob'})}")

if __name__ == "__main__":
    asyncio.run(demo_mcp())

    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
