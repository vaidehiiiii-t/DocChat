import os

from flask import Flask

import app.models  # noqa: F401
from app.api.auth import auth_bp
from app.api.chat import chat_bp
from app.api.documents import documents_bp
from app.api.health import health_bp
from app.config import Config
from app.errors import register_error_handlers, register_jwt_error_handlers
from app.extensions import cors, db, jwt, limiter, migrate
from app.utils.logging import setup_logging


def reset_stuck_documents(app: Flask):
    """
    On application startup, reset any documents stuck in 'processing' back to 'failed'.
    """
    with app.app_context():
        try:
            from datetime import datetime, timezone

            from app.models.document import Document

            stuck_docs = Document.query.filter_by(status="processing").all()
            for doc in stuck_docs:
                doc.status = "failed"
                doc.error_message = "Server restarted during processing"
                doc.updated_at = datetime.now(timezone.utc)
            if stuck_docs:
                db.session.commit()
        except Exception:
            # Avoid crashing if tables do not exist yet (e.g. during migrations)
            pass


def create_app(config_class=None) -> Flask:
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        config_obj = Config()
    elif isinstance(config_class, type):
        config_obj = config_class()
    else:
        config_obj = config_class

    config_obj.apply_to_flask(app)
    setup_logging(app)

    # Ensure storage directories exist
    upload_dir = app.config.get("UPLOAD_DIR", "./storage/uploads")
    chroma_dir = app.config.get("CHROMA_DIR", "./storage/chroma")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(chroma_dir, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # Configure CORS for allowed origin
    frontend_origin = app.config.get("FRONTEND_ORIGIN", "http://localhost:5173")
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": [frontend_origin]}},
        supports_credentials=True,
    )

    # Register error handlers
    register_error_handlers(app)
    register_jwt_error_handlers(jwt)

    # Register blueprints
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(documents_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")

    # Reset any documents left in 'processing' state from prior crash/restart
    reset_stuck_documents(app)

    return app
