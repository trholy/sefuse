class AuthError(Exception):
    """Base class for authentication-related errors."""


class ConfigurationError(AuthError):
    """Raised when required authentication configuration is missing or invalid."""


class ValidationError(AuthError):
    """Raised when user input fails validation."""


class AuthenticationError(AuthError):
    """Raised when user credentials are invalid."""


class AuthorizationError(AuthError):
    """Raised when the caller does not have the required permissions."""


class UserAlreadyExistsError(AuthError):
    """Raised when creating a user with an existing username."""


class UserNotFoundError(AuthError):
    """Raised when a user cannot be found."""

