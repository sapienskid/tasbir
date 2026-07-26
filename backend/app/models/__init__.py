from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.asset import Asset  # noqa: E402, F401
from app.models.format import Format  # noqa: E402, F401
from app.models.prompt import PromptRegistry, PromptVersion  # noqa: E402, F401
from app.models.settings import Settings  # noqa: E402, F401
from app.models.task import GenerationTask  # noqa: E402, F401
from app.models.template import Template  # noqa: E402, F401
from app.models.tokens import DesignToken  # noqa: E402, F401
from app.models.brand import Brand  # noqa: E402, F401
