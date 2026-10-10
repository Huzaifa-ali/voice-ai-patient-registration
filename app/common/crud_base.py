"""Generic base CRUD — trivial get/create/update/delete only.

A convenience for simple operations, NOT a query abstraction (VLE 7.1). The moment a
query needs a filter, join, or ordering, write a named method on the module's CRUD
class instead of bending this with kwargs.

Transaction model: write methods ``add``/``flush`` only. The service layer owns commit
(via the ``get_db`` request boundary). This keeps multi-step operations atomic.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic CRUD operations for any SQLAlchemy model.

    Usage:
        class CRUDPatient(CRUDBase[Patient, None, None]):
            model = Patient
    """

    model: type[ModelType]

    def __class_getitem__(cls, params: Any) -> Any:
        """Accept 1–3 type args; pad missing ones with None for convenience."""
        if not isinstance(params, tuple):
            params = (params,)
        while len(params) < 3:
            params = (*params, type(None))
        return super().__class_getitem__(params)  # type: ignore[misc]

    def get_by_id(self, db: Session, record_id: Any) -> ModelType | None:
        pk = self.model.__mapper__.primary_key[0]
        stmt = select(self.model).where(pk == record_id)
        return db.execute(stmt).scalar_one_or_none()

    def get_all(self, db: Session) -> list[ModelType]:
        return list(db.execute(select(self.model)).scalars().all())

    def create(self, db: Session, **kwargs: Any) -> ModelType:
        instance = self.model(**kwargs)
        db.add(instance)
        db.flush()
        db.refresh(instance)
        return instance

    def update(self, db: Session, instance: ModelType, **kwargs: Any) -> ModelType:
        """Apply provided keyword args as-is (only pass keys you intend to change)."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        db.flush()
        db.refresh(instance)
        return instance

    def delete(self, db: Session, instance: ModelType) -> None:
        db.delete(instance)
        db.flush()
