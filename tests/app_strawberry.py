import asyncio
import strawberry
import uvicorn
from graphql import GraphQLSchema

from graphql_mcp.server import GraphQLMCP


@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"


schema: GraphQLSchema = strawberry.Schema(query=Query)._schema


server = GraphQLMCP(schema=schema, name="MyGraphQLServer")

mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)


async def demo():
    # Get available tools
    print(f"Available tools: {await server.list_tools()}")

    # Call the hello tool
    print(f"Query result: {await server._mcp_call_tool('hello', arguments={'name': 'Rob'})}")


if __name__ == "__main__":
    asyncio.run(demo())
    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
