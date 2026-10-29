from sqlalchemy import CheckConstraint, Identity, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class County(Base):
    __tablename__ = "counties"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
