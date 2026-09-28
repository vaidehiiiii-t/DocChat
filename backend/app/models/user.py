from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    name = db.Column(String(100), nullable=True)
    email = db.Column(String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(String(255), nullable=False)
    created_at = db.Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    documents = db.relationship(
        "Document",
        backref="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chat_sessions = db.relationship(
        "ChatSession",
        backref="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
