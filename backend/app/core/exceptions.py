from fastapi import status


class AppException(Exception):  # noqa: N818 (mirrors FastAPI's own HTTPException naming)
    """Base class for application-level exceptions.

    Raised from services/repositories and translated into the unified error
    body `{"detail": {"code", "message", "fields"}}` by the handler registered
    in `app.main`. `message` is Russian and shown to the user as-is.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Некорректный запрос"

    def __init__(self, message: str | None = None, fields: dict[str, str] | None = None) -> None:
        if message is not None:
            self.message = message
        self.fields = fields
        super().__init__(self.message)


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Не найдено"


class AlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "already_exists"
    message = "Такая запись уже есть"


class ValidationFailedException(AppException):
    """Business-rule validation that pydantic alone can't express (needs the DB or catalog)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "Проверь введённые данные"


class OnboardingIncompleteException(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "onboarding_incomplete"
    message = "Осталось заполнить несколько шагов"


class InvalidCredentialsException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "Неверный логин или пароль"


class InvalidTokenException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_token"
    message = "Сессия истекла, войди заново"


class InvalidLinkException(AppException):
    """Bad or expired token from an emailed link. Deliberately not 401: it says nothing
    about the current session, so clients must not treat it as one expiring."""

    code = "invalid_link"
    message = "Ссылка устарела или уже не действует"


class PermissionDeniedException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "Недостаточно прав"


class TooManyRequestsException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "too_many_requests"
    message = "Слишком много попыток. Подожди немного и попробуй снова"


class InactiveUserException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "inactive_user"
    message = "Аккаунт отключён"
