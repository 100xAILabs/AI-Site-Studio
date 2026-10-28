"""Durable project and build-run history for AI Studio builds."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class StudioBuild(UUIDMixin, TimestampMixin, Base):
    """A durable website project created through the conversational Studio."""

    __tablename__ = "studio_builds"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    initial_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    site_type: Mapped[str] = mapped_column(String(100), nullable=False)
    stack: Mapped[str] = mapped_column(String(80), nullable=False, default="html-css-js")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    current_phase: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approved_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["StudioBuildMessage"]] = relationship(back_populates="build", cascade="all, delete-orphan", order_by="StudioBuildMessage.sequence")
    events: Mapped[list["StudioBuildEvent"]] = relationship(back_populates="build", cascade="all, delete-orphan", order_by="StudioBuildEvent.sequence")


class StudioBuildMessage(UUIDMixin, Base):
    """Append-only chat history associated with a generated website project."""

    __tablename__ = "studio_build_messages"
    __table_args__ = (UniqueConstraint("build_id", "sequence", name="uq_studio_build_message_sequence"),)

    build_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("studio_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    build: Mapped[StudioBuild] = relationship(back_populates="messages")


class StudioBuildEvent(UUIDMixin, Base):
    """Ordered progress events that allow clients to resume build timelines."""

    __tablename__ = "studio_build_events"

    build_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("studio_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    build: Mapped[StudioBuild] = relationship(back_populates="events")
