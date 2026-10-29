from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employer_web_document import EmployerWebDocument
    from .job_web_document import JobWebDocument


class WebDocument(Base):
    __tablename__ = "web_documents"
    __table_args__ = (
        UniqueConstraint("canonical_url", "content_hash"),
        CheckConstraint("length(btrim(canonical_url)) > 0", name="url_not_blank"),
        CheckConstraint("length(btrim(content_text)) > 0", name="content_not_blank"),
        CheckConstraint("length(btrim(content_hash)) > 0", name="hash_not_blank"),
        CheckConstraint(
            "retrieval_provider IN ('tavily', 'direct')", name="provider_valid"
        ),
        CheckConstraint(
            "first_retrieved_at <= last_verified_at", name="timestamps_ordered"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    retrieval_provider: Mapped[str] = mapped_column(Text)
    first_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job_links: Mapped[list["JobWebDocument"]] = relationship(
        back_populates="document", passive_deletes="all", lazy="raise"
    )
    employer_links: Mapped[list["EmployerWebDocument"]] = relationship(
        back_populates="document", passive_deletes="all", lazy="raise"
    )
