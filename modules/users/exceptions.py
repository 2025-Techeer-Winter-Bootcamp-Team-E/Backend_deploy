"""
Users module exceptions.
"""
from shared.exceptions import AppException, ValidationError


class InvalidEmailError(ValidationError):
    """Raised when an email is invalid."""

    def __init__(self, email: str):
        super().__init__(message=f"Invalid email format: '{email}'", field="email")
        self.email = email


class InvalidPhoneNumberError(ValidationError):
    """Raised when a phone number is invalid."""

    def __init__(self, phone: str):
        super().__init__(message=f"Invalid phone number: '{phone}'", field="phone_number")
        self.phone = phone


class UserAlreadyExistsError(AppException):
    """Raised when attempting to create a user that already exists."""

    def __init__(self, field: str, value: str):
        super().__init__(
            message=f"User with {field} '{value}' already exists",
            code="USER_ALREADY_EXISTS"
        )
        self.field = field
        self.value = value


class UserNotFoundError(AppException):
    """Raised when a user is not found."""

    def __init__(self, identifier: str):
        super().__init__(
            message=f"User '{identifier}' not found",
            code="USER_NOT_FOUND"
        )
        self.identifier = identifier


class UserAlreadyVerifiedError(AppException):
    """Raised when attempting to verify an already verified user."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"User '{user_id}' is already verified",
            code="USER_ALREADY_VERIFIED"
        )
        self.user_id = user_id


class InvalidCredentialsError(AppException):
    """Raised when login credentials are invalid."""

    def __init__(self):
        super().__init__(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS"
        )


class UserInactiveError(AppException):
    """Raised when an inactive user attempts to perform an action."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"User '{user_id}' is inactive",
            code="USER_INACTIVE"
        )
        self.user_id = user_id
