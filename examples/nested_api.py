"""Nested API - demonstrates nested tools, @mcpHidden, Pydantic models, and async resolvers.

Demonstrates:
- Nested query paths that auto-generate MCP tools (category → articles)
- @mcpHidden directive to hide arguments from MCP tools
- Pydantic BaseModel types as GraphQL object types
- Async resolvers
- Separate query_type / mutation_type pattern
"""

from typing import Annotated, Optional
from uuid import uuid4

from pydantic import BaseModel

from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP, mcp_hidden


class Comment(BaseModel):
    id: str
    author: str
    text: str


class Article(BaseModel):
    id: str
    title: str
    body: str
    tags: list[str]
    comments: list[Comment] = []


# In-memory store keyed by category name
_categories: dict[str, list[Article]] = {}


def _seed():
    _categories["python"] = [
        Article(
            id=str(uuid4()), title="Getting Started with FastAPI",
            body="FastAPI is a modern web framework for building APIs with Python.",
            tags=["web", "fastapi"],
            comments=[
                Comment(id=str(uuid4()), author="alice", text="Great intro!"),
                Comment(id=str(uuid4()), author="bob", text="Very helpful."),
            ],
        ),
        Article(
            id=str(uuid4()), title="Async Python Patterns",
            body="Learn how to use asyncio effectively in your projects.",
            tags=["async", "patterns"],
            comments=[
                Comment(id=str(uuid4()), author="charlie", text="Exactly what I needed."),
            ],
        ),
    ]
    _categories["graphql"] = [
        Article(
            id=str(uuid4()), title="Schema-First vs Code-First GraphQL",
            body="Comparing the two main approaches to building GraphQL APIs.",
            tags=["architecture", "patterns"],
            comments=[],
        ),
        Article(
            id=str(uuid4()), title="GraphQL Subscriptions Deep Dive",
            body="Understanding real-time data with GraphQL subscriptions.",
            tags=["real-time", "subscriptions"],
            comments=[
                Comment(id=str(uuid4()), author="diana", text="When would you use SSE instead?"),
            ],
        ),
    ]
    _categories["mcp"] = [
        Article(
            id=str(uuid4()), title="Building MCP Servers",
            body="How to expose your API as MCP tools for AI agents.",
            tags=["ai", "mcp"],
            comments=[
                Comment(id=str(uuid4()), author="eve", text="This is the future."),
            ],
        ),
    ]


_seed()


class Category:
    """A category containing articles. Fields with arguments generate nested MCP tools."""

    def __init__(self, name: str, articles: list[Article]):
        self._name = name
        self._articles = articles

    @field
    async def articles(
        self,
        tag: Optional[str] = None,
        internal_score: Annotated[Optional[int], mcp_hidden] = None,
    ) -> list[Article]:
        """List articles in this category, optionally filtered by tag.

        The internal_score argument is hidden from MCP tools via @mcpHidden
        but remains accessible through the GraphQL API directly.
        """
        result = self._articles
        if tag is not None:
            result = [a for a in result if tag in a.tags]
        return result

    @field
    def name(self) -> str:
        """The category name."""
        return self._name

    @field
    def article_count(self) -> int:
        """Number of articles in this category."""
        return len(self._articles)


class Query:

    @field
    def categories(self) -> list[str]:
        """List all category names."""
        return list(_categories.keys())

    @field
    def category(self, name: str) -> Optional[Category]:
        """Get a category by name."""
        articles = _categories.get(name)
        if articles is None:
            return None
        return Category(name, articles)


class Mutation:

    @field(mutable=True)
    def add_article(
        self,
        category: str,
        title: str,
        body: str,
        tags: Optional[list[str]] = None,
    ) -> Article:
        """Add an article to a category. Creates the category if it doesn't exist."""
        article = Article(
            id=str(uuid4()),
            title=title,
            body=body,
            tags=tags or [],
        )
        if category not in _categories:
            _categories[category] = []
        _categories[category].append(article)
        return article


api = GraphQLAPI(
    query_type=Query,
    mutation_type=Mutation,
    directives=[mcp_hidden],
)
server = GraphQLMCP.from_api(api, allow_mutations=True, graphql_http_kwargs={
    "graphiql_example_query": """\
# Browse the knowledge base
{
  categories

  category(name: "python") {
    name
    articleCount
    articles {
      title
      tags
      comments {
        author
        text
      }
    }
  }
}

# Filter articles by tag
# {
#   category(name: "python") {
#     articles(tag: "async") {
#       title
#       body
#     }
#   }
# }

# Add an article
# mutation {
#   addArticle(
#     category: "python"
#     title: "My New Article"
#     body: "Article content here"
#     tags: ["tutorial"]
#   ) {
#     id
#     title
#   }
# }""",
})
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
