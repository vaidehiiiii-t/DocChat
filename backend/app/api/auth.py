from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import make_error_response
from app.extensions import db, limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.utils.validation import validate_json

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
@validate_json(RegisterRequest)
def register(data: RegisterRequest):
    email = data.email.lower().strip()

    # Check for duplicate email
    existing_user = db.session.scalar(select(User).where(User.email == email))
    if existing_user:
        return make_error_response("CONFLICT", "Email is already registered", 409)

    # Hash password & create user
    password_hash = generate_password_hash(data.password)
    user = User(
        name=data.name.strip() if data.name else None,
        email=email,
        password_hash=password_hash,
    )
    db.session.add(user)
    db.session.commit()

    # Generate JWT token
    access_token = create_access_token(identity=str(user.id))

    return (
        jsonify(
            {
                "user": user.to_dict(),
                "access_token": access_token,
            }
        ),
        201,
    )


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
@validate_json(LoginRequest)
def login(data: LoginRequest):
    email = data.email.lower().strip()

    # Generic invalid credentials message to prevent user enumeration
    invalid_creds_msg = "Invalid email or password"

    user = db.session.scalar(select(User).where(User.email == email))
    if not user:
        return make_error_response("UNAUTHORIZED", invalid_creds_msg, 401)

    if not check_password_hash(user.password_hash, data.password):
        return make_error_response("UNAUTHORIZED", invalid_creds_msg, 401)

    access_token = create_access_token(identity=str(user.id))

    return (
        jsonify(
            {
                "user": user.to_dict(),
                "access_token": access_token,
            }
        ),
        200,
    )


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if not user:
        return make_error_response("UNAUTHORIZED", "User not found or no longer exists", 401)

    return jsonify({"user": user.to_dict()}), 200
