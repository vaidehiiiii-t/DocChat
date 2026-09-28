from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def make_error_response(
    code: str, message: str, status_code: int, details: dict[str, Any] | None = None
):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            }
        ),
        status_code,
    )


def register_error_handlers(app: Flask):
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(400)
    def handle_bad_request(err):
        msg = getattr(err, "description", "Bad Request")
        return make_error_response("VALIDATION_ERROR", msg, 400)

    @app.errorhandler(401)
    def handle_unauthorized(err):
        msg = getattr(err, "description", "Unauthorized")
        return make_error_response("UNAUTHORIZED", msg, 401)

    @app.errorhandler(403)
    def handle_forbidden(err):
        msg = getattr(err, "description", "Forbidden")
        return make_error_response("FORBIDDEN", msg, 403)

    @app.errorhandler(404)
    def handle_not_found(err):
        msg = getattr(err, "description", "Resource not found")
        return make_error_response("NOT_FOUND", msg, 404)

    @app.errorhandler(405)
    def handle_method_not_allowed(err):
        return make_error_response("VALIDATION_ERROR", "Method not allowed", 405)

    @app.errorhandler(409)
    def handle_conflict(err):
        msg = getattr(err, "description", "Conflict")
        return make_error_response("CONFLICT", msg, 409)

    @app.errorhandler(413)
    def handle_payload_too_large(err):
        return make_error_response(
            "PAYLOAD_TOO_LARGE", "File exceeds maximum upload size limit", 413
        )

    @app.errorhandler(415)
    def handle_unsupported_media(err):
        return make_error_response("UNSUPPORTED_MEDIA", "Unsupported media type", 415)

    @app.errorhandler(429)
    def handle_rate_limited(err):
        return make_error_response("RATE_LIMITED", "Too many requests. Please slow down.", 429)

    @app.errorhandler(500)
    def handle_internal_server_error(err):
        return make_error_response("INTERNAL", "An internal server error occurred", 500)

    @app.errorhandler(HTTPException)
    def handle_generic_http_exception(err: HTTPException):
        return make_error_response("INTERNAL", err.description, err.code or 500)

    @app.errorhandler(Exception)
    def handle_unhandled_exception(err: Exception):
        app.logger.exception("Unhandled exception: %s", str(err))
        return make_error_response("INTERNAL", "An internal server error occurred", 500)


def register_jwt_error_handlers(jwt):
    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return make_error_response("UNAUTHORIZED", f"Missing authorization token: {reason}", 401)

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return make_error_response("UNAUTHORIZED", f"Invalid authorization token: {reason}", 401)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return make_error_response("UNAUTHORIZED", "Token has expired", 401)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_data):
        return make_error_response("UNAUTHORIZED", "Token has been revoked", 401)
