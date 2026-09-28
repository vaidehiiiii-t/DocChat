from functools import wraps
from typing import Type

from flask import request
from pydantic import BaseModel, ValidationError

from app.errors import make_error_response


def validate_json(schema_cls: Type[BaseModel]):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return make_error_response(
                    "VALIDATION_ERROR",
                    "Request body must be JSON",
                    400,
                )
            try:
                validated_data = schema_cls.model_validate(request.get_json() or {})
            except ValidationError as err:
                details = {}
                for error in err.errors():
                    field_name = ".".join(str(x) for x in error["loc"])
                    details[field_name] = error["msg"]
                return make_error_response(
                    "VALIDATION_ERROR",
                    "Validation failed",
                    400,
                    details=details,
                )
            return fn(validated_data, *args, **kwargs)

        return wrapper

    return decorator
