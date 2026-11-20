"""Shared column types for ORM models.

`Vector` maps the pgvector `vector(N)` column without pulling in the pgvector
Python package (not in 04_TRD §1). It is sufficient for DDL/metadata and plain
reads/writes; ANN similarity operators are issued via SQL where needed.

The `pg_enum` helper references the native ENUM types created by the migrations
(`create_type=False`), so the ORM never tries to CREATE/DROP them.
"""

from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: object) -> str:
        return f"VECTOR({self.dim})"

    def bind_processor(self, dialect):  # type: ignore[no-untyped-def]
        def process(value):  # type: ignore[no-untyped-def]
            if value is None:
                return None
            return "[" + ",".join(str(v) for v in value) + "]"
        return process

    def result_processor(self, dialect, coltype):  # type: ignore[no-untyped-def]
        def process(value):  # type: ignore[no-untyped-def]
            if value is None:
                return None
            if isinstance(value, str):
                return [float(v) for v in value.strip("[]").split(",")]
            return list(value)
        return process


def pg_enum(name: str, *labels: str) -> PgEnum:
    """A native ENUM column bound to an existing type (migrations own the type)."""
    return PgEnum(*labels, name=name, create_type=False)
