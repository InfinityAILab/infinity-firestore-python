import logging
from datetime import datetime, timezone
from typing import Any, Callable, Generic, Type, TypeVar, cast

from google.cloud.firestore import Client, CollectionReference, Query
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

from infinity_firestore import get_firestore_client

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U")


class FieldPath(Generic[U]):
    """Represents a single field path with type info."""

    def __init__(self, name: str, type_: Type[U]):
        self.name = name
        self.type_ = type_

    def __str__(self) -> str:
        return self.name


def safe_annotation(annotation: Any) -> type:
    """Safely resolve annotation to a type, falling back to object if invalid."""
    if annotation is None:
        return object
    # typing.Any is a type, so allow it directly
    if isinstance(annotation, type) or annotation is Any:
        return annotation
    return object  # Fallback for any other unexpected cases


class FieldRef(Generic[T]):
    """Typed reference to a Pydantic model's fields."""

    def __init__(self, model_class: type[T]):
        self.model_class = model_class
        for field_name, field_info in model_class.model_fields.items():
            safe_type = safe_annotation(field_info.annotation)
            setattr(self, field_name, FieldPath(field_name, safe_type))

    def __getattr__(self, name: str) -> FieldPath:
        """Type hint for dynamic attribute access."""
        # This helps type checkers understand dynamic attributes
        try:
            return cast(FieldPath, super().__getattribute__(name))
        except AttributeError:
            raise AttributeError(f"Field '{name}' does not exist in model {self.model_class.__name__}")


class FirestoreQueryBuilder(Generic[T]):
    """Fluent builder with type-safe fields for constructing Firestore queries."""

    def __init__(self, collection: CollectionReference, fields: FieldRef[T]):
        self._query: CollectionReference | Query = collection
        self.fields = fields  # Store typed fields for reference

    def where(self, field: FieldPath[U], op: str, value: U) -> "FirestoreQueryBuilder":
        """Type-safe where clause."""
        # Runtime type check (optional but recommended)
        if not isinstance(value, field.type_):
            raise TypeError(f"Value {value} does not match field type {field.type_}")
        self._query = self._query.where(filter=FieldFilter(str(field), op, value))
        return self

    def order_by(self, field: FieldPath, direction: str = Query.ASCENDING) -> "FirestoreQueryBuilder":
        """Order results by a field (ASCENDING or DESCENDING)."""
        self._query = self._query.order_by(str(field), direction=direction)
        return self

    def limit(self, count: int) -> "FirestoreQueryBuilder":
        """Limit the number of results."""
        self._query = self._query.limit(count)
        return self

    def build(self) -> CollectionReference | Query:
        """Return the built Firestore Query object."""
        return self._query

    async def execute(self, from_dict_func: Callable) -> list[T]:
        """Execute the query and return results as list of models."""
        docs = self.build().stream()
        return [from_dict_func(doc.to_dict(), doc.id) for doc in docs if doc.to_dict()]


class FirestoreRepository(Generic[T]):
    """Generic Firestore repository for CRUD operations with Pydantic models."""

    def __init__(self, collection_name: str, model_class: Type[T]):
        self.collection_name = collection_name
        self.model_class = model_class
        self._db: Client | None = None

    @property
    def db(self) -> Client:
        """Lazy initialization of Firestore client."""
        if self._db is None:
            self._db = get_firestore_client()
        return self._db

    @property
    def collection(self):
        """Get the Firestore collection reference."""
        return self.db.collection(self.collection_name)

    def fields(self) -> FieldRef[T]:
        """Get typed field references for the model."""
        return FieldRef(self.model_class)

    def _to_dict(self, model: T) -> dict[str, Any]:
        """Convert Pydantic model to dictionary for Firestore storage."""
        data = model.model_dump(exclude={"id"})
        # Convert datetime objects to Firestore timestamps
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value
        return data

    def _from_dict(self, data: dict[str, Any] | None, doc_id: str) -> T:
        """Convert Firestore document to Pydantic model."""
        if not data:
            data = {}
        data.update({"id": doc_id})
        return self.model_class(**data)

    async def create(self, model: T) -> T:
        """Create a new document in Firestore."""
        try:
            data = self._to_dict(model)
            doc_ref = self.collection.document()
            doc_ref.create(data)

            # Return model with generated ID
            model_dict = model.model_dump()
            model_dict["id"] = doc_ref.id
            result = self.model_class(**model_dict)

            logger.info(f"Created {self.collection_name} document with ID: {doc_ref.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to create {self.collection_name} document: {e}")
            raise

    async def get_by_id(self, doc_id: str) -> T | None:
        """Get a document by ID."""
        try:
            doc = self.collection.document(doc_id).get()
            if not doc.exists:
                return None

            # Type annotation to help type checker
            return self._from_dict(doc.to_dict(), doc_id)  # type: ignore

        except Exception as e:
            logger.error(f"Failed to get {self.collection_name} document {doc_id}: {e}")
            raise

    async def update(self, doc_id: str, model: T) -> T:
        """Update an existing document."""
        try:
            data = self._to_dict(model)
            data["updated_at"] = datetime.now(tz=timezone.utc)

            self.collection.document(doc_id).update(data)

            # Return updated model
            model_dict = model.model_dump()
            model_dict["id"] = doc_id
            model_dict["updated_at"] = data["updated_at"]
            result = self.model_class(**model_dict)

            logger.info(f"Updated {self.collection_name} document: {doc_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to update {self.collection_name} document {doc_id}: {e}")
            raise

    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        try:
            self.collection.document(doc_id).delete()
            logger.info(f"Deleted {self.collection_name} document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {self.collection_name} document {doc_id}: {e}")
            raise

    async def list_all(self, limit: int | None = None) -> list[T]:
        """List all documents in the collection."""
        try:
            query = self.collection
            if limit:
                query = query.limit(limit)

            docs = query.stream()
            return [self._from_dict(doc.to_dict(), doc.id) for doc in docs]

        except Exception as e:
            logger.error(f"Failed to list {self.collection_name} documents: {e}")
            raise

    async def find_by_field(self, field: str, value: Any) -> list[T]:
        """Find documents by a specific field value."""
        try:
            docs = self.collection.where(filter=FieldFilter(field, "==", value)).stream()
            return [self._from_dict(doc.to_dict(), doc.id) for doc in docs if doc.to_dict()]

        except Exception as e:
            logger.error(f"Failed to find {self.collection_name} documents by {field}: {e}")
            raise

    async def find_by_fields(self, **fields: Any) -> list[T]:
        """Find documents by multiple field values using keyword arguments."""
        try:
            query: CollectionReference | Query = self.collection
            for field, value in fields.items():
                query = query.where(filter=FieldFilter(field, "==", value))

            docs = query.stream()
            return [self._from_dict(doc.to_dict(), doc.id) for doc in docs if doc.to_dict()]

        except Exception:
            logger.error(f"Failed to find {self.collection_name} documents by fields: {fields}")
            raise

    async def query(self, builder: FirestoreQueryBuilder[T]) -> list[T]:
        """Execute a query built with FirestoreQueryBuilder."""
        try:
            return await builder.execute(self._from_dict)
        except Exception as e:
            logger.error(f"Failed to execute query on {self.collection_name}: {e}")
            raise
