from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.agent import Agent  # noqa: E402, F401
from app.models.agent_job import AgentJob  # noqa: E402, F401
from app.models.audit_log import AuditLog  # noqa: E402, F401
from app.models.chat import ChatMessage, ChatThread  # noqa: E402, F401
from app.models.design_system import DesignSystem  # noqa: E402, F401
from app.models.task import GenerationTask  # noqa: E402, F401
from app.models.template import Template  # noqa: E402, F401
