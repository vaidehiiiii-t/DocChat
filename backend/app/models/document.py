from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text

from app.extensions import db


class Document(db.Model):
    __tablename__ = "documents"

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
    filename = db.Column(String(255), nullable=False)
    stored_name = db.Column(String(255), nullable=False)
    mime_type = db.Column(String(100), nullable=False)
    size_bytes = db.Column(BigInteger, nullable=False)
    page_count = db.Column(Integer, nullable=True)
    chunk_count = db.Column(Integer, default=0, nullable=False)
    status = db.Column(
        Enum("pending", "processing", "ready", "failed", name="document_status_enum"),
        default="pending",
        nullable=False,
    )
    error_message = db.Column(Text, nullable=True)
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
    chunks = db.relationship(
        "Chunk",
        backref="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chat_sessions = db.relationship(
        "ChatSession",
        backref="document",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_documents_user_id_created_at", "user_id", "created_at"),)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
