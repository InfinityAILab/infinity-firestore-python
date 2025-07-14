# infinity-firestore-python

A type-safe wrapper around Google Cloud Firestore for internal use. This library provides a clean, Pydantic-based interface for Firestore operations with full type safety and modern Python features.

⚠️ **Use with caution** - This is not maintained as an OSS project and is intended for internal use only. Feel free to use it but at your own risk.

## Features

- 🔒 **Type-safe queries** with compile-time field validation
- 📝 **Pydantic integration** for automatic serialization/deserialization
- 🛠️ **Generic repository pattern** for consistent CRUD operations
- 🔍 **Fluent query builder** with method chaining
- 📊 **Automatic timestamping** for created_at and updated_at fields
- 🎯 **Field reference system** for IDE autocompletion and type checking

## Installation

```bash
uv add git+https://github.com/InfinityAILab/infinity-firestore-python --tag v0.1.0
```

## Requirements

- Python 3.9+
- Google Cloud Firestore
- Pydantic v2
- Firebase Admin SDK

## Quick Start

### 1. Initialize Firebase

```python
from infinity_firestore import initialize_firebase

# Initialize Firebase (typically done once at app startup)
initialize_firebase()
```

### 2. Define Your Model

```python
from infinity_firestore.model import Model
from pydantic import Field

class User(Model):
    name: str
    email: str
    age: int = Field(gt=0)
    is_active: bool = True
```

### 3. Create a Repository

```python
from infinity_firestore.repository import FirestoreRepository

class UserRepository(FirestoreRepository[User]):
    def __init__(self):
        super().__init__("users", User)

# Create repository instance
user_repo = UserRepository()
```

### 4. Basic CRUD Operations

```python
# Create a new user
user = User(name="John Doe", email="john@example.com", age=30)
created_user = await user_repo.create(user)

# Get user by ID
user = await user_repo.get_by_id(created_user.id)

# Update user
user.age = 31
updated_user = await user_repo.update(user.id, user)

# Delete user
await user_repo.delete(user.id)

# List all users
users = await user_repo.list_all(limit=10)
```

## Advanced Usage

### Type-Safe Queries

The library provides a type-safe query builder that prevents runtime errors:

```python
# Get field references for type-safe queries
fields = user_repo.fields()

# Build and execute type-safe queries
query = FirestoreQueryBuilder(user_repo.collection, fields) \
    .where(fields.age, ">=", 18) \
    .where(fields.is_active, "==", True) \
    .order_by(fields.created_at, "desc") \
    .limit(10)

adults = await user_repo.query(query)
```

### Field-Based Searches

```python
# Find by single field
active_users = await user_repo.find_by_field("is_active", True)

# Find by multiple fields
john_users = await user_repo.find_by_fields(
    name="John Doe",
    is_active=True
)
```

### Custom Database

```python
from infinity_firestore import get_firestore_client

# Use a specific database
client = get_firestore_client(database="my-custom-db")

class UserRepository(FirestoreRepository[User]):
    def __init__(self):
        super().__init__("users", User)
        self._db = client  # Override default client
```

## API Reference

### Core Functions

#### `initialize_firebase()`
Initializes the Firebase Admin SDK. Should be called once at application startup.

#### `get_firestore_client(database: str | None = None) -> Client`
Returns a Firestore client instance.

**Parameters:**
- `database`: Optional database name. If None, uses the default database.

### Model Class

#### `Model`
Base class for all Firestore models. Provides automatic ID generation and timestamps.

**Fields:**
- `id: str` - Auto-generated document ID
- `created_at: datetime` - UTC timestamp when document was created
- `updated_at: datetime` - UTC timestamp when document was last updated

### Repository Class

#### `FirestoreRepository[T]`
Generic repository for CRUD operations on Firestore collections.

**Constructor:**
```python
def __init__(self, collection_name: str, model_class: Type[T])
```

**Methods:**

##### `async create(model: T) -> T`
Creates a new document in Firestore.

##### `async get_by_id(doc_id: str) -> T | None`
Retrieves a document by its ID. Returns None if not found.

##### `async update(doc_id: str, model: T) -> T`
Updates an existing document. Automatically updates the `updated_at` timestamp.

##### `async delete(doc_id: str) -> bool`
Deletes a document by ID. Returns True if successful.

##### `async list_all(limit: int | None = None) -> list[T]`
Lists all documents in the collection with optional limit.

##### `async find_by_field(field: str, value: Any) -> list[T]`
Finds documents where a field equals a specific value.

##### `async find_by_fields(**fields: Any) -> list[T]`
Finds documents matching multiple field criteria.

##### `async query(builder: FirestoreQueryBuilder[T]) -> list[T]`
Executes a query built with FirestoreQueryBuilder.

##### `fields() -> FieldRef[T]`
Returns typed field references for the model.

### Query Builder

#### `FirestoreQueryBuilder[T]`
Fluent builder for constructing type-safe Firestore queries.

**Methods:**

##### `where(field: FieldPath[U], op: str, value: U) -> FirestoreQueryBuilder`
Adds a where clause to the query.

**Supported operators:**
- `"=="` - Equal
- `"!="` - Not equal
- `"<"` - Less than
- `"<="` - Less than or equal
- `">"` - Greater than
- `">="` - Greater than or equal
- `"in"` - In array
- `"not-in"` - Not in array
- `"array-contains"` - Array contains value
- `"array-contains-any"` - Array contains any of the values

##### `order_by(field: FieldPath, direction: str = Query.ASCENDING) -> FirestoreQueryBuilder`
Orders results by a field.

**Directions:**
- `Query.ASCENDING` (default)
- `Query.DESCENDING`

##### `limit(count: int) -> FirestoreQueryBuilder`
Limits the number of results.

##### `build() -> CollectionReference | Query`
Returns the built Firestore Query object.

##### `async execute(from_dict_func: Callable) -> list[T]`
Executes the query and returns results as a list of models.

## Error Handling

The library uses Python's standard exception handling. All repository methods may raise:

- `Exception` - For general Firestore operation failures
- `TypeError` - For type mismatches in queries
- `AttributeError` - For invalid field references

```python
try:
    user = await user_repo.get_by_id("invalid-id")
except Exception as e:
    logger.error(f"Failed to get user: {e}")
```

## Best Practices

### 1. Use Type Hints
Always use proper type hints for better IDE support and runtime safety:

```python
from typing import Optional

async def get_user_by_email(email: str) -> Optional[User]:
    users = await user_repo.find_by_field("email", email)
    return users[0] if users else None
```

### 2. Handle Exceptions Properly
Wrap repository calls in try-catch blocks:

```python
async def safe_create_user(user_data: dict) -> Optional[User]:
    try:
        user = User(**user_data)
        return await user_repo.create(user)
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return None
```

### 3. Use Field References for Queries
Always use the type-safe field references:

```python
# ✅ Good - Type-safe
fields = user_repo.fields()
query = FirestoreQueryBuilder(user_repo.collection, fields) \
    .where(fields.age, ">=", 18)

# ❌ Bad - String-based, error-prone
await user_repo.find_by_field("age", 18)  # Typos not caught at compile time
```

### 4. Initialize Firebase Early
Initialize Firebase at application startup:

```python
# main.py or app initialization
from infinity_firestore import initialize_firebase

def setup_app():
    initialize_firebase()
    # ... rest of app setup
```

## Limitations

- This library is designed for internal use and may not handle all edge cases
- No built-in pagination beyond simple `limit()`
- No support for Firestore transactions or batch operations
- Limited support for complex nested queries
- No built-in caching mechanisms

## Contributing

This is an internal library and is not maintained as an open-source project. Use at your own risk.
