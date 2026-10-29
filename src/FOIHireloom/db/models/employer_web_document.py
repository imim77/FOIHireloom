from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employer import Employer
    from .web_document import WebDocument


class EmployerWebDocument(Base):
    __tablename__ = "employer_web_documents"
    __table_args__ = (
        CheckConstraint(
            "relation_kind IN ('official_site', 'careers', 'company_context')",
            name="relation_kind_valid",
        ),
    )

    employer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employers.id", ondelete="RESTRICT"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("web_documents.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    relation_kind: Mapped[str] = mapped_column(Text)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employer: Mapped["Employer"] = relationship(back_populates="web_document_links", lazy="raise")
    document: Mapped["WebDocument"] = relationship(back_populates="employer_links", lazy="raise")
