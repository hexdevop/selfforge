from fastapi import status


class AppException(Exception):  # noqa: N818 (mirrors FastAPI's own HTTPException naming)
    """Base class for application-level exceptions.

    Raised from services/repositories and translated into a JSON response
    by the handler registered in `app.main`. Keeps HTTP concerns out of the
    business logic layer.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "bad_request"
    detail: str = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    detail = "Resource not found"


class AlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "already_exists"
    detail = "Resource already exists"


class InvalidCredentialsException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_credentials"
    detail = "Invalid credentials"


class InvalidTokenException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_token"
    detail = "Invalid or expired token"


class PermissionDeniedException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"
    detail = "Permission denied"


class InactiveUserException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "inactive_user"
    detail = "User is inactive"
