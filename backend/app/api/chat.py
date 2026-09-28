import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import select

from app.errors import AppError
from app.extensions import db, get_user_rate_limit_key, limiter
from app.models.chat import ChatSession, Message
from app.models.document import Document
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat/sessions", methods=["POST"])
@jwt_required()
def create_session():
    current_user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    document_id = data.get("document_id")
    title = data.get("title")

    if document_id is not None:
        doc = db.session.get(Document, int(document_id))
        # Cross-user scoping returns 404 (never 403, per D2)
        if not doc or doc.user_id != current_user_id:
            raise AppError("Document not found", code="NOT_FOUND", status_code=404)
        if doc.status != "ready":
            raise AppError(
                "Only documents with 'ready' status can be selected for chat scoping.",
                code="VALIDATION_ERROR",
                status_code=400,
            )

    session = ChatSession(
        user_id=current_user_id,
        document_id=int(document_id) if document_id is not None else None,
        title=title.strip() if title and title.strip() else None,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(session.to_dict()), 201


@chat_bp.route("/chat/sessions", methods=["GET"])
@jwt_required()
def list_sessions():
    current_user_id = int(get_jwt_identity())
    sessions = (
        ChatSession.query.filter_by(user_id=current_user_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in sessions]), 200


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["GET"])
@jwt_required()
def get_session_messages(session_id: int):
    current_user_id = int(get_jwt_identity())
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != current_user_id:
        raise AppError("Chat session not found", code="NOT_FOUND", status_code=404)

    return jsonify([m.to_dict() for m in session.messages]), 200


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["DELETE"])
@jwt_required()
def delete_session(session_id: int):
    current_user_id = int(get_jwt_identity())
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != current_user_id:
        raise AppError("Chat session not found", code="NOT_FOUND", status_code=404)

    db.session.delete(session)
    db.session.commit()

    return jsonify({"message": "Session deleted"}), 200


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["POST"])
@jwt_required()
@limiter.limit("6 per minute", key_func=get_user_rate_limit_key)
def post_message(session_id: int):
    current_user_id = int(get_jwt_identity())
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != current_user_id:
        raise AppError("Chat session not found", code="NOT_FOUND", status_code=404)

    data = request.get_json(silent=True) or {}
    content = data.get("content")

    if not content or not isinstance(content, str) or not content.strip():
        raise AppError("Message content cannot be empty", code="VALIDATION_ERROR", status_code=400)

    clean_content = content.strip()
    if len(clean_content) > 2000:
        raise AppError(
            "Message exceeds maximum character limit of 2000",
            code="VALIDATION_ERROR",
            status_code=400,
        )

    # 1. Save user message
    user_msg = Message(session_id=session.id, role="user", content=clean_content)
    db.session.add(user_msg)

    # 2. Auto-title if session has no title and this is first user message
    if not session.title:
        session.title = clean_content[:60]

    session.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # 3. Retrieve relevant chunks
    retrieval_service = RetrievalService()
    sources = retrieval_service.retrieve(
        query=clean_content,
        user_id=current_user_id,
        document_id=session.document_id,
    )

    # 4. If no relevant chunks found: short-circuit (Decision D4 - do not call LLM)
    if not sources:
        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content="I couldn't find this in your documents.",
            sources_json=[],
            model="retrieval_fallback",
        )
        db.session.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return (
            jsonify(
                {
                    "user_message": user_msg.to_dict(),
                    "assistant_message": assistant_msg.to_dict(),
                }
            ),
            200,
        )

    # 5. Build prompt and call LLM
    # History carries only previous turns without context
    history = [
        {"role": m.role, "content": m.content} for m in session.messages if m.id != user_msg.id
    ]

    llm_service = LLMService()
    # If LLMService raises AppError (e.g. 503 LLM_UNAVAILABLE), user message stays saved!
    answer, model_used = llm_service.answer(
        question=clean_content,
        sources=sources,
        history=history,
    )

    # 6. Save assistant message
    sources_to_save = [
        {
            "chunk_id": s["chunk_id"],
            "document_id": s["document_id"],
            "filename": s["filename"],
            "page": s["page"],
            "snippet": s["snippet"],
            "score": s["score"],
        }
        for s in sources
    ]

    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources_json=sources_to_save,
        model=model_used,
    )
    db.session.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return (
        jsonify(
            {
                "user_message": user_msg.to_dict(),
                "assistant_message": assistant_msg.to_dict(),
            }
        ),
        200,
    )


@chat_bp.route("/chat/sessions/<int:session_id>/messages/stream", methods=["POST"])
@jwt_required()
@limiter.limit("6 per minute", key_func=get_user_rate_limit_key)
def stream_message(session_id: int):
    current_user_id = int(get_jwt_identity())
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != current_user_id:
        raise AppError("Chat session not found", code="NOT_FOUND", status_code=404)

    data = request.get_json(silent=True) or {}
    content = data.get("content")

    if not content or not isinstance(content, str) or not content.strip():
        raise AppError("Message content cannot be empty", code="VALIDATION_ERROR", status_code=400)

    clean_content = content.strip()
    if len(clean_content) > 2000:
        raise AppError(
            "Message exceeds maximum character limit of 2000",
            code="VALIDATION_ERROR",
            status_code=400,
        )

    # 1. Save user message
    user_msg = Message(session_id=session.id, role="user", content=clean_content)
    db.session.add(user_msg)

    # 2. Auto-title if session has no title and this is first user message
    if not session.title:
        session.title = clean_content[:60]

    session.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    user_msg_id = user_msg.id
    session_id_val = session.id
    doc_id_val = session.document_id

    # 3. Retrieve relevant chunks
    retrieval_service = RetrievalService()
    sources = retrieval_service.retrieve(
        query=clean_content,
        user_id=current_user_id,
        document_id=doc_id_val,
    )

    sources_to_save = [
        {
            "chunk_id": s["chunk_id"],
            "document_id": s["document_id"],
            "filename": s["filename"],
            "page": s["page"],
            "snippet": s["snippet"],
            "score": s["score"],
        }
        for s in sources
    ]

    # 4. Fetch history turns
    history_objs = db.session.scalars(
        select(Message)
        .where(Message.session_id == session.id, Message.id < user_msg_id)
        .order_by(Message.created_at.asc())
    ).all()
    history = [{"role": m.role, "content": m.content} for m in history_objs]

    app_instance = current_app._get_current_object()

    def generate_events():
        # Step 1: Emit sources event first
        sources_payload = json.dumps(sources_to_save)
        yield f"event: sources\ndata: {sources_payload}\n\n"

        # If no sources found: short circuit (Decision D4)
        if not sources_to_save:
            fallback_text = "I couldn't find this in your documents."
            token_payload = json.dumps({"token": fallback_text})
            yield f"event: token\ndata: {token_payload}\n\n"

            with app_instance.app_context():
                assistant_msg = Message(
                    session_id=session_id_val,
                    role="assistant",
                    content=fallback_text,
                    sources_json=[],
                    model="retrieval_fallback",
                )
                db.session.add(assistant_msg)
                sess = db.session.get(ChatSession, session_id_val)
                if sess:
                    sess.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                ast_id = assistant_msg.id

            done_payload = json.dumps(
                {
                    "user_message_id": user_msg_id,
                    "assistant_message_id": ast_id,
                    "model": "retrieval_fallback",
                }
            )
            yield f"event: done\ndata: {done_payload}\n\n"
            return

        # Step 2: Stream tokens from LLM
        llm_service = LLMService()
        full_tokens = []

        try:
            for token in llm_service.stream_answer(clean_content, sources=sources, history=history):
                full_tokens.append(token)
                token_payload = json.dumps({"token": token})
                yield f"event: token\ndata: {token_payload}\n\n"

            # Step 3: Save assistant message on clean completion
            final_content = "".join(full_tokens).strip()
            model_used = llm_service.last_stream_model or "default"

            with app_instance.app_context():
                assistant_msg = Message(
                    session_id=session_id_val,
                    role="assistant",
                    content=final_content,
                    sources_json=sources_to_save,
                    model=model_used,
                )
                db.session.add(assistant_msg)
                sess = db.session.get(ChatSession, session_id_val)
                if sess:
                    sess.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                ast_id = assistant_msg.id

            done_payload = json.dumps(
                {
                    "user_message_id": user_msg_id,
                    "assistant_message_id": ast_id,
                    "model": model_used,
                }
            )
            yield f"event: done\ndata: {done_payload}\n\n"

        except Exception as exc:
            logger.error("Error during streaming generation: %s", exc)
            err_payload = json.dumps(
                {"message": "The AI model is busy. Please try again in a minute."}
            )
            yield f"event: error\ndata: {err_payload}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate_events()), headers=headers)
