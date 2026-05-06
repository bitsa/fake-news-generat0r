class AppError(Exception):
    """Base for all application-level errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message or self.__class__.__name__
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
