from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db
from app.services.vector_store import VectorStore

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    db_status = "ok"
    vector_status = "ok"

    # Check database connectivity
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    # Check vector store connectivity
    store = None
    try:
        chroma_dir = current_app.config.get("CHROMA_DIR", "./storage/chroma")
        store = VectorStore(persist_dir=chroma_dir)
        store.count()
    except Exception as exc:
        vector_status = f"warning: {str(exc)}"
    finally:
        if store is not None:
            store.close()

    is_ok = db_status == "ok"
    status_str = "ok" if is_ok else "unhealthy"
    status_code = 200 if is_ok else 503

    return (
        jsonify(
            {
                "status": status_str,
                "db": db_status,
                "vector_store": vector_status,
            }
        ),
        status_code,
    )
