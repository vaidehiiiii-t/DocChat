from concurrent.futures import ThreadPoolExecutor

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()


def get_user_rate_limit_key() -> str:
    """Return user-scoped identifier for JWT-authenticated requests, or client IP."""
    try:
        from flask_jwt_extended import get_jwt_identity

        identity = get_jwt_identity()
        if identity is not None:
            return f"user:{identity}"
    except Exception:
        pass
    return get_remote_address()


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)
executor = ThreadPoolExecutor(max_workers=3)
