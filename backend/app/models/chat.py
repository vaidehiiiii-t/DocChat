from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects import mysql

from app.extensions import db


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = db.Column(String(200), nullable=True)
    created_at = db.Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # Relationships
    messages = db.relationship(
        "Message",
        backref="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at.asc()",
    )

    __table_args__ = (Index("ix_chat_sessions_user_id_updated_at", "user_id", "updated_at"),)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    session_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(
        Enum("user", "assistant", name="message_role_enum"),
        nullable=False,
    )
    content = db.Column(
        Text().with_variant(mysql.MEDIUMTEXT, "mysql"),
        nullable=False,
    )
    sources_json = db.Column(JSON, nullable=True)
    model = db.Column(String(100), nullable=True)
    created_at = db.Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources_json or [],
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
