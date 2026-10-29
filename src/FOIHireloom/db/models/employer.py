from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Employer(Base):
    __tablename__ = "employers"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("created_at <= updated_at", name="timestamps_ordered"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
