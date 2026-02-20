"""Hello World - minimal GraphQL MCP server example."""

from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP


class HelloWorldAPI:

    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"


api = GraphQLAPI(root_type=HelloWorldAPI)
server = GraphQLMCP.from_api(api, graphql_http_kwargs={
    "graphiql_example_query": """\
{
  hello

  custom: hello(name: "GraphQL MCP")
}""",
})
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
