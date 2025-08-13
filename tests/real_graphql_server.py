"""
Real GraphQL server implementation for testing the RemoteGraphQLClient.
This uses Strawberry GraphQL to create an actual server with realistic schemas and data.
"""

import strawberry
from typing import List, Optional, Dict, Any
import asyncio
import uuid
from datetime import datetime
from dataclasses import dataclass
from strawberry.extensions import QueryDepthLimiter
from strawberry.aiohttp.views import GraphQLView
from strawberry.scalars import ID
from aiohttp import web, ClientSession
import threading
import time


# Data Models
@dataclass
class UserData:
    id: str
    name: str
    email: str
    orders: List['OrderData']
    addresses: List['AddressData']
    preferences: Optional['UserPreferencesData']
    tags: List[str]


@dataclass  
class OrderData:
    id: str
    total: float
    items: List['OrderItemData']
    discounts: List['DiscountData']
    notes: Optional[str]
    status: str = "PENDING"


@dataclass
class OrderItemData:
    id: str
    quantity: int
    product: 'ProductData'


@dataclass
class ProductData:
    id: str
    name: str
    price: float
    categories: List['CategoryData']
    reviews: List['ReviewData']
    variants: List['ProductVariantData']
    description: Optional[str]
    metadata: Optional['ProductMetadataData']


@dataclass
class CategoryData:
    id: str
    name: str
    parent_category: Optional['CategoryData']


@dataclass
class ReviewData:
    id: str
    rating: int
    comment: str
    author: 'UserData'


@dataclass
class ProductVariantData:
    id: str
    sku: str
    price: float
    attributes: Dict[str, str]


@dataclass
class ProductMetadataData:
    width: Optional[int]
    height: Optional[int]
    weight: Optional[float]
    tags: List[str]


@dataclass
class DiscountData:
    id: str
    code: str
    amount: float


@dataclass  
class AddressData:
    id: str
    street: str
    city: str
    country: str
    postal_code: str
    type: str = "HOME"


@dataclass
class UserPreferencesData:
    newsletter: bool
    notifications: bool
    theme: str = "light"
    language: str = "en"


# GraphQL Types - Note: Use Optional[List[...]] to allow null arrays
@strawberry.type
class User:
    id: ID
    name: str
    email: str
    orders: Optional[List['Order']]
    addresses: Optional[List['Address']]
    preferences: Optional['UserPreferences']
    tags: Optional[List[str]]


@strawberry.type
class Order:
    id: ID
    total: float
    items: Optional[List['OrderItem']]
    discounts: Optional[List['Discount']]
    notes: Optional[str]
    status: str


@strawberry.type
class OrderItem:
    id: ID
    quantity: int
    product: 'Product'


@strawberry.type
class Product:
    id: ID
    name: str
    price: float
    categories: Optional[List['Category']]
    reviews: Optional[List['Review']]
    variants: Optional[List['ProductVariant']]
    description: Optional[str]
    metadata: Optional['ProductMetadata']


@strawberry.type
class Category:
    id: ID
    name: str
    parent_category: Optional['Category']


@strawberry.type
class Review:
    id: ID
    rating: int
    comment: str


@strawberry.type
class ProductVariant:
    id: ID
    sku: str
    price: float
    attributes: strawberry.scalars.JSON


@strawberry.type
class ProductMetadata:
    width: Optional[int]
    height: Optional[int]
    weight: Optional[float]
    tags: Optional[List[str]]


@strawberry.type
class Discount:
    id: ID
    code: str
    amount: float


@strawberry.type
class Address:
    id: ID
    street: str
    city: str
    country: str
    postal_code: str
    type: str


@strawberry.type
class UserPreferences:
    newsletter: bool
    notifications: bool
    theme: str
    language: str


@strawberry.type
class SearchResult:
    products: Optional[List[Product]]
    filters: Optional[List['Filter']]
    suggestions: Optional[List[str]]
    total_count: int


@strawberry.type
class Filter:
    name: str
    values: List[str]
    count: int


@strawberry.type
class CreateSearchResult:
    id: ID
    results: SearchResult


# Input Types
@strawberry.input
class SearchInput:
    query: str
    filters: Optional['SearchFiltersInput'] = None
    sorting: Optional['SortingInput'] = None
    pagination: Optional['PaginationInput'] = None
    options: Optional['SearchOptionsInput'] = None


@strawberry.input
class SearchFiltersInput:
    category: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    brand: Optional[str] = None
    in_stock: Optional[bool] = None
    tags: Optional[List[Optional[str]]] = None


@strawberry.input
class SortingInput:
    field: str
    direction: str
    priority: Optional[int] = None


@strawberry.input
class PaginationInput:
    limit: int
    offset: Optional[int] = None


@strawberry.input
class SearchOptionsInput:
    include_reviews: Optional[bool] = None
    include_variants: Optional[bool] = None
    include_suggestions: Optional[bool] = None


@strawberry.input
class UserProfileInput:
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional['UserPreferencesInput'] = None
    addresses: Optional[List['AddressInput']] = None
    metadata: Optional['UserMetadataInput'] = None


@strawberry.input
class UserPreferencesInput:
    newsletter: Optional[bool] = None
    notifications: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None


@strawberry.input
class AddressInput:
    type: str
    street: str
    city: str
    country: str
    is_primary: Optional[bool] = None
    instructions: Optional[str] = None


@strawberry.input
class UserMetadataInput:
    source: str
    version: str
    session_id: Optional[str] = None


@strawberry.type
class UpdateUserProfileResult:
    success: bool
    errors: List['ValidationError']
    user: Optional[User]


@strawberry.type
class ValidationError:
    field: str
    message: str


# Mock Data Store
class MockDataStore:
    def __init__(self):
        # Create sample data that includes null values strategically
        self.users = {
            "user123": UserData(
                id="user123",
                name="John Doe",
                email="john@example.com",
                orders=[
                    OrderData(
                        id="order1",
                        total=99.99,
                        items=[
                            OrderItemData(
                                id="item1",
                                quantity=2,
                                product=ProductData(
                                    id="prod1",
                                    name="Gaming Laptop",
                                    price=1299.99,
                                    categories=[],  # Empty list to test null transformations
                                    reviews=[],     # Empty list to test null transformations
                                    variants=[],    # Empty list to test null transformations
                                    description="High-performance gaming laptop",
                                    metadata=None   # This will be null in responses
                                )
                            )
                        ],
                        discounts=[],  # Empty list to test null transformations
                        notes=None
                    )
                ],
                addresses=[],  # Empty list to test null transformations
                preferences=UserPreferencesData(
                    newsletter=True,
                    notifications=False,
                    theme="dark",
                    language="en"
                ),
                tags=[]  # Empty list to test null transformations
            ),
            "user456": UserData(
                id="user456",
                name="Jane Smith", 
                email="jane@example.com",
                orders=[],  # Empty list
                addresses=[
                    AddressData(
                        id="addr1",
                        street="123 Main St",
                        city="New York",
                        country="US",
                        postal_code="10001"
                    )
                ],
                preferences=None,  # This will be null in responses
                tags=["premium", "verified"]
            )
        }
        
        self.products = {
            "prod1": ProductData(
                id="prod1",
                name="Gaming Laptop",
                price=1299.99,
                categories=[
                    CategoryData(id="cat1", name="Electronics", parent_category=None),
                    CategoryData(id="cat2", name="Laptops", parent_category=None)
                ],
                reviews=[
                    ReviewData(id="rev1", rating=5, comment="Excellent!", author=self.users["user123"])
                ],
                variants=[
                    ProductVariantData(id="var1", sku="GL-001", price=1299.99, attributes={"color": "black", "ram": "16GB"})
                ],
                description="High-performance gaming laptop",
                metadata=ProductMetadataData(width=35, height=25, weight=2.5, tags=["gaming", "laptop"])
            )
        }
        
        # Simulate sometimes returning null arrays instead of empty arrays
        # This is the key behavior we want to test
        self._return_null_arrays = True

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user, potentially with null arrays instead of empty arrays."""
        user_data = self.users.get(user_id)
        if not user_data:
            return None
            
        # Convert to GraphQL types, sometimes returning null instead of empty arrays
        orders = []
        for order_data in user_data.orders:
            items = []
            for item_data in order_data.items:
                product = self.convert_product(item_data.product)
                items.append(OrderItem(
                    id=item_data.id,
                    quantity=item_data.quantity,
                    product=product
                ))
            
            # Sometimes return null instead of empty discounts array
            discounts = None if self._return_null_arrays and not order_data.discounts else [
                Discount(id=d.id, code=d.code, amount=d.amount) for d in order_data.discounts
            ]
            
            orders.append(Order(
                id=order_data.id,
                total=order_data.total,
                items=items,
                discounts=discounts,
                notes=order_data.notes,
                status=order_data.status
            ))
        
        # Sometimes return null instead of empty addresses array
        addresses = None if self._return_null_arrays and not user_data.addresses else [
            Address(
                id=addr.id,
                street=addr.street,
                city=addr.city,
                country=addr.country,
                postal_code=addr.postal_code,
                type=addr.type
            ) for addr in user_data.addresses
        ]
        
        # Sometimes return null instead of empty tags array
        tags = None if self._return_null_arrays and not user_data.tags else user_data.tags
        
        preferences = None
        if user_data.preferences:
            preferences = UserPreferences(
                newsletter=user_data.preferences.newsletter,
                notifications=user_data.preferences.notifications,
                theme=user_data.preferences.theme,
                language=user_data.preferences.language
            )
        
        return User(
            id=user_data.id,
            name=user_data.name,
            email=user_data.email,
            orders=orders,
            addresses=addresses,
            preferences=preferences,
            tags=tags
        )
    
    def convert_product(self, product_data: ProductData) -> Product:
        """Convert ProductData to Product GraphQL type."""
        # Sometimes return null instead of empty arrays for categories, reviews, variants
        categories = None if self._return_null_arrays and not product_data.categories else [
            Category(id=cat.id, name=cat.name, parent_category=None) for cat in product_data.categories
        ]
        
        reviews = None if self._return_null_arrays and not product_data.reviews else [
            Review(id=rev.id, rating=rev.rating, comment=rev.comment) for rev in product_data.reviews
        ]
        
        variants = None if self._return_null_arrays and not product_data.variants else [
            ProductVariant(id=var.id, sku=var.sku, price=var.price, attributes=var.attributes) 
            for var in product_data.variants
        ]
        
        metadata = None
        if product_data.metadata:
            # Sometimes return null instead of empty tags array in metadata
            tags = None if self._return_null_arrays and not product_data.metadata.tags else product_data.metadata.tags
            metadata = ProductMetadata(
                width=product_data.metadata.width,
                height=product_data.metadata.height,
                weight=product_data.metadata.weight,
                tags=tags
            )
        
        return Product(
            id=product_data.id,
            name=product_data.name,
            price=product_data.price,
            categories=categories,
            reviews=reviews,
            variants=variants,
            description=product_data.description,
            metadata=metadata
        )

    def search_products(self, search_input: SearchInput) -> CreateSearchResult:
        """Search products and return results with potential null arrays."""
        # Simple mock search - in real implementation this would be more complex
        products = [self.convert_product(prod) for prod in self.products.values()]
        
        # Sometimes return null instead of empty arrays
        filters = None if self._return_null_arrays else []
        suggestions = None if self._return_null_arrays else []
        
        return CreateSearchResult(
            id=str(uuid.uuid4()),
            results=SearchResult(
                products=products,
                filters=filters,
                suggestions=suggestions,
                total_count=len(products)
            )
        )


# Global data store
data_store = MockDataStore()


# Resolvers
@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: ID) -> Optional[User]:
        return data_store.get_user(id)
    
    @strawberry.field
    def users(self) -> Optional[List[User]]:
        return [data_store.get_user(user_id) for user_id in data_store.users.keys()]


@strawberry.type  
class Mutation:
    @strawberry.mutation
    def create_search(self, input: SearchInput) -> CreateSearchResult:
        return data_store.search_products(input)
    
    @strawberry.mutation
    def update_user_profile(self, user_id: ID, input: UserProfileInput) -> UpdateUserProfileResult:
        # Mock validation error for testing
        if input.preferences and input.preferences.theme == "dark":
            return UpdateUserProfileResult(
                success=False,
                errors=[ValidationError(field="input.preferences.theme", message="Invalid theme value")],
                user=None
            )
        
        # Mock successful update
        user = data_store.get_user(user_id)
        return UpdateUserProfileResult(
            success=True,
            errors=[],
            user=user
        )


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def order_updates(self, user_id: ID) -> User:
        """Mock subscription that yields user updates."""
        # Simulate real-time updates
        for i in range(3):
            await asyncio.sleep(0.1)  # Short delay to simulate real-time
            user = data_store.get_user(user_id)
            if user:
                yield user


# Create the schema
schema = strawberry.Schema(
    query=Query, 
    mutation=Mutation,
    subscription=Subscription,
    extensions=[QueryDepthLimiter(max_depth=10)]
)


class RealGraphQLServer:
    """Real GraphQL server for integration testing."""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.app = None
        self.runner = None
        self.site = None
        self.server_thread = None
        self._running = False
        
    async def create_app(self):
        """Create the aiohttp application with GraphQL endpoint."""
        app = web.Application()
        
        # Add GraphQL endpoint
        graphql_view = GraphQLView(schema=schema)
        app.router.add_post('/graphql', graphql_view)
        app.router.add_get('/graphql', graphql_view)  # For GraphQL Playground
        
        return app
    
    def run_server(self):
        """Run the server in a background thread."""
        async def _run_server():
            self.app = await self.create_app()
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, 'localhost', self.port)
            await self.site.start()
            
            print(f"GraphQL server running at http://localhost:{self.port}/graphql")
            self._running = True
            
            # Keep the server running
            try:
                while self._running:
                    await asyncio.sleep(0.1)
            except Exception:
                pass
            finally:
                await self.cleanup()
        
        # Run in new event loop in thread
        def _thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run_server())
            finally:
                loop.close()
        
        self.server_thread = threading.Thread(target=_thread_target, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        timeout = 10
        start_time = time.time()
        while not self._running and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not self._running:
            raise RuntimeError(f"Server failed to start within {timeout}s")
    
    async def cleanup(self):
        """Clean up server resources."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
    
    def start(self):
        """Start the server."""
        if not self._running:
            self.run_server()
    
    def stop(self):
        """Stop the server."""
        self._running = False
        if self.server_thread:
            self.server_thread.join(timeout=5)
    
    @property
    def url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}/graphql"
    
    def set_return_null_arrays(self, value: bool):
        """Configure whether to return null arrays instead of empty arrays."""
        data_store._return_null_arrays = value


# Test helper functions
def create_test_server(port: int = 8765) -> RealGraphQLServer:
    """Create and start a test GraphQL server."""
    server = RealGraphQLServer(port)
    server.start()
    return server


async def check_server_health(url: str) -> bool:
    """Test if the GraphQL server is responsive."""
    try:
        async with ClientSession() as session:
            query = "query { __schema { types { name } } }"
            payload = {"query": query}
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return "data" in result and "__schema" in result["data"]
    except Exception:
        pass
    return False


if __name__ == "__main__":
    # Start server for manual testing
    server = create_test_server()
    try:
        print("Server running. Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.stop()