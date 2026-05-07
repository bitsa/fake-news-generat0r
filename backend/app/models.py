from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.sources import Source


class Base(DeclarativeBase): ...


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source: Mapped[Source] = mapped_column(
        sa.Enum(
            Source,
            name="source_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    url: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    fake: Mapped["ArticleFake | None"] = relationship(
        "ArticleFake",
        back_populates="article",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ArticleFake(Base):
    __tablename__ = "article_fakes"
    __table_args__ = (
        sa.CheckConstraint(
            "transform_status IN ('pending', 'completed')",
            name="ck_article_fakes_transform_status",
        ),
    )

    article_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    transform_status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="pending"
    )
    title: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    model: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    temperature: Mapped[float | None] = mapped_column(sa.Double, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    article: Mapped["Article"] = relationship("Article", back_populates="fake")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
        sa.Index(
            "ix_chat_messages_article_id_created_at",
            "article_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_error: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    request_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
