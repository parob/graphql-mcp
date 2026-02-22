import asyncio
import uvicorn

from graphql_api import GraphQLAPI, field
from typing import List, Dict
from graphql_mcp.server import GraphQLMCP


class HelloWorldAPI:

    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

    @field
    def messages(self) -> List[Dict]:
        messages = [
            {
                "role": "user",
                "content": "Hello, how are you?"
            },
            {
                "role": "assistant",
                "content": "I'm good, thank you!"
            }
        ]
        return messages


api = GraphQLAPI(root_type=HelloWorldAPI)

server = GraphQLMCP.from_api(api)

mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)


async def demo_mcp():
    # Get available tools
    print(f"Available tools: {await server.list_tools()}")

    # Call the hello tool
    print(f"Query result: {await server._call_tool_mcp('hello', arguments={'name': 'Rob'})}")

    # Call the messages tool
    print(f"Query result: {await server._call_tool_mcp('messages', arguments={})}")


if __name__ == "__main__":
    asyncio.run(demo_mcp())

    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
