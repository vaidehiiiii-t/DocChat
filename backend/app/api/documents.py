import logging
import os

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.errors import AppError
from app.extensions import db, executor, get_user_rate_limit_key, limiter
from app.models.document import Document
from app.services.ingestion import IngestionService
from app.services.vector_store import VectorStore
from app.utils.files import (
    generate_storage_filename,
    get_safe_storage_path,
    validate_uploaded_file,
)

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/documents", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute", key_func=get_user_rate_limit_key)
def upload_document():
    current_user_id = int(get_jwt_identity())

    if "file" not in request.files:
        raise AppError(
            "Missing 'file' field in multipart form upload",
            code="VALIDATION_ERROR",
            status_code=400,
        )

    file = request.files["file"]
    settings = current_app.config.get("DOCCHAT_SETTINGS")
    allowed_exts = (
        {f".{ext}" for ext in settings.allowed_extensions_set}
        if settings
        else {".pdf", ".txt", ".md"}
    )
    max_bytes = settings.max_content_length if settings else 20 * 1024 * 1024

    original_filename, ext, size_bytes = validate_uploaded_file(
        file,
        allowed_extensions=allowed_exts,
        max_size_bytes=max_bytes,
    )

    stored_name = generate_storage_filename(ext)
    upload_dir = current_app.config.get("UPLOAD_DIR", "./storage/uploads")
    save_path = get_safe_storage_path(upload_dir, stored_name)

    # Save physical file
    file.save(save_path)

    # Insert document record with pending status
    mime_type = file.mimetype or "application/octet-stream"
    doc = Document(
        user_id=current_user_id,
        filename=original_filename,
        stored_name=stored_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        status="pending",
    )
    db.session.add(doc)
    db.session.commit()

    # Submit background processing
    app_obj = current_app._get_current_object()

    def process_task(doc_id: int):
        with app_obj.app_context():
            try:
                IngestionService().process(doc_id)
            except Exception as e:
                logger.exception("Background ingestion error for doc %s: %s", doc_id, e)

    executor.submit(process_task, doc.id)

    return jsonify(doc.to_dict()), 202


@documents_bp.route("/documents", methods=["GET"])
@jwt_required()
def list_documents():
    current_user_id = int(get_jwt_identity())
    docs = (
        Document.query.filter_by(user_id=current_user_id).order_by(Document.created_at.desc()).all()
    )
    return jsonify([d.to_dict() for d in docs]), 200


@documents_bp.route("/documents/<int:document_id>", methods=["GET"])
@jwt_required()
def get_document(document_id: int):
    current_user_id = int(get_jwt_identity())
    doc = db.session.get(Document, document_id)

    if not doc or doc.user_id != current_user_id:
        # Cross-user access returns 404 (never 403, per D2)
        raise AppError("Document not found", code="NOT_FOUND", status_code=404)

    return jsonify(doc.to_dict()), 200


@documents_bp.route("/documents/<int:document_id>", methods=["DELETE"])
@jwt_required()
def delete_document(document_id: int):
    current_user_id = int(get_jwt_identity())
    doc = db.session.get(Document, document_id)

    if not doc or doc.user_id != current_user_id:
        # Cross-user access returns 404 (never 403, per D2)
        raise AppError("Document not found", code="NOT_FOUND", status_code=404)

    # 1. Delete physical file
    upload_dir = current_app.config.get("UPLOAD_DIR", "./storage/uploads")
    safe_path = os.path.join(upload_dir, doc.stored_name)
    if os.path.exists(safe_path):
        try:
            os.remove(safe_path)
        except Exception as exc:
            logger.warning("Error deleting file %s: %s", safe_path, exc)

    # 2. Delete Chroma vectors
    chroma_dir = current_app.config.get("CHROMA_DIR", "./storage/chroma")
    vector_store = VectorStore(persist_dir=chroma_dir)
    try:
        vector_store.delete_document(document_id)
    except Exception as exc:
        logger.warning("Error deleting Chroma vectors for doc %s: %s", document_id, exc)
    finally:
        vector_store.close()

    # 3. Delete Document row in MySQL (cascades to chunks)
    db.session.delete(doc)
    db.session.commit()

    return jsonify({"message": "Document deleted"}), 200
