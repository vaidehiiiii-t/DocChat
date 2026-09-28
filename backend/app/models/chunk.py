from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects import mysql

from app.extensions import db


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    document_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = db.Column(Integer, nullable=False)
    page_number = db.Column(Integer, nullable=True)
    text = db.Column(
        Text().with_variant(mysql.MEDIUMTEXT, "mysql"),
        nullable=False,
    )
    char_count = db.Column(Integer, nullable=False)
    created_at = db.Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_chunk_index"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "char_count": self.char_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
