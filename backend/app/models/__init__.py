from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.task import GenerationTask  # noqa: E402, F401
from app.models.audit_log import AuditLog  # noqa: E402, F401
