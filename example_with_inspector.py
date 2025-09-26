#!/usr/bin/env python3
"""
Example GraphQL MCP Server with Web Inspector

This example demonstrates how to create a GraphQL MCP server with the built-in
web inspection tool enabled. The inspector allows you to:
- Browse all available MCP tools
- View tool documentation and parameters
- Test tools directly from a web interface

Usage:
    python example_with_inspector.py

Then visit:
    - http://localhost:8002/ - GraphQL endpoint
    - http://localhost:8002/inspector - Web inspection tool
    - http://localhost:8002/mcp - MCP endpoint
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import asyncio
import uvicorn
from typing import List, Optional

try:
    from graphql_api import GraphQLAPI, field
    from graphql_mcp.server import GraphQLMCP
except ImportError:
    print("Dependencies not available. Creating basic example...")
    # Simple fallback if graphql-api not available
    from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLArgument
    from graphql_mcp.server import GraphQLMCP

    def resolve_hello(root, info, name="World"):
        return f"Hello, {name}!"

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "hello": GraphQLField(
                    GraphQLString,
                    args={"name": GraphQLArgument(GraphQLString)},
                    resolve=resolve_hello,
                    description="Greet someone by name"
                )
            }
        )
    )

    server = GraphQLMCP(schema=schema, name="Simple Example", inspector=True, graphql_http=False)
    app = server.http_app(transport="http", stateless_http=True)

    print("🚀 Starting Simple MCP Server with Web Inspector...")
    print("📚 Available endpoints:")
    print("   • Inspector: http://localhost:8002/inspector")
    print("   • MCP:       http://localhost:8002/mcp")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8002)
    exit()


class Book:
    """A book with title, author, and optional genre."""

    def __init__(self, id: str, title: str, author: str, genre: Optional[str] = None):
        self.id = id
        self.title = title
        self.author = author
        self.genre = genre

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "genre": self.genre
        }


class BookStoreAPI:
    """A simple bookstore API for demonstration."""

    def __init__(self):
        self.books = [
            Book("1", "The Hobbit", "J.R.R. Tolkien", "Fantasy"),
            Book("2", "1984", "George Orwell", "Dystopian"),
            Book("3", "To Kill a Mockingbird", "Harper Lee", "Fiction"),
            Book("4", "The Great Gatsby", "F. Scott Fitzgerald", "Classic"),
            Book("5", "Pride and Prejudice", "Jane Austen", "Romance"),
        ]
        self.next_id = 6

    @field
    def books(self) -> List[dict]:
        """Get all books in the store."""
        return [book.to_dict() for book in self.books]

    @field
    def book(self, id: str) -> Optional[dict]:
        """Get a specific book by ID."""
        for book in self.books:
            if book.id == id:
                return book.to_dict()
        return None

    @field
    def books_by_author(self, author: str) -> List[dict]:
        """Find books by a specific author."""
        matching_books = [
            book.to_dict() for book in self.books
            if author.lower() in book.author.lower()
        ]
        return matching_books

    @field
    def books_by_genre(self, genre: str) -> List[dict]:
        """Find books in a specific genre."""
        matching_books = [
            book.to_dict() for book in self.books
            if book.genre and genre.lower() in book.genre.lower()
        ]
        return matching_books

    @field
    def add_book(self, title: str, author: str, genre: Optional[str] = None) -> dict:
        """Add a new book to the store."""
        book = Book(str(self.next_id), title, author, genre)
        self.books.append(book)
        self.next_id += 1
        return book.to_dict()

    @field
    def update_book(self, id: str, title: Optional[str] = None,
                   author: Optional[str] = None, genre: Optional[str] = None) -> Optional[dict]:
        """Update an existing book's information."""
        for book in self.books:
            if book.id == id:
                if title is not None:
                    book.title = title
                if author is not None:
                    book.author = author
                if genre is not None:
                    book.genre = genre
                return book.to_dict()
        return None

    @field
    def delete_book(self, id: str) -> bool:
        """Delete a book from the store."""
        for i, book in enumerate(self.books):
            if book.id == id:
                del self.books[i]
                return True
        return False

    @field
    def search_books(self, query: str) -> List[dict]:
        """Search books by title, author, or genre."""
        query_lower = query.lower()
        matching_books = []

        for book in self.books:
            if (query_lower in book.title.lower() or
                query_lower in book.author.lower() or
                (book.genre and query_lower in book.genre.lower())):
                matching_books.append(book.to_dict())

        return matching_books


def main():
    # Create the GraphQL API
    api = GraphQLAPI(root_type=BookStoreAPI)

    # Create the MCP server with inspector enabled (default)
    server = GraphQLMCP.from_api(
        api,
        name="BookStore MCP",
        graphql_http=True,          # Enable GraphQL HTTP endpoint
        allow_mutations=True,       # Allow mutations (add_book, update_book, etc.)
        inspector=True,             # Enable web inspector (default: True)
        inspector_title="BookStore Inspector"  # Custom inspector title
    )

    # Create the ASGI app
    app = server.http_app(
        transport="streamable-http",
        stateless_http=True
    )

    print("🚀 Starting BookStore MCP Server with Web Inspector...")
    print("📚 Available endpoints:")
    print("   • GraphQL:   http://localhost:8002/")
    print("   • Inspector: http://localhost:8002/inspector")
    print("   • MCP:       http://localhost:8002/mcp")
    print()
    print("💡 Try the inspector to:")
    print("   • Browse all available tools")
    print("   • View tool parameters and documentation")
    print("   • Test tools directly from the web interface")
    print()
    print("🛠️  Available tools include:")
    print("   • books() - List all books")
    print("   • book(id) - Get a specific book")
    print("   • books_by_author(author) - Find books by author")
    print("   • search_books(query) - Search books")
    print("   • add_book(title, author, genre?) - Add new book")
    print("   • update_book(id, title?, author?, genre?) - Update book")
    print("   • delete_book(id) - Delete a book")
    print()

    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()