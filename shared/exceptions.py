"""Custom exception hierarchy for the Gmail Automation project."""

class GmailAutomationError(Exception):
    """Base exception class for all project-specific errors."""
    pass

class AuthenticationError(GmailAutomationError):
    """Raised for authentication-related errors (e.g., invalid credentials, token issues)."""
    pass

class ConfigurationError(GmailAutomationError):
    """Raised for configuration-related errors (e.g., missing environment variables)."""
    pass

class ValidationError(GmailAutomationError):
    """Raised for data validation errors (e.g., invalid input)."""
    pass

class ExternalServiceError(GmailAutomationError):
    """Raised for errors originating from external services (e.g., Gmail API, RabbitMQ)."""
    def __init__(self, message: str, service: str = None, details: dict = None):
        super().__init__(message)
        self.service = service
        self.details = details or {}

class ResourceNotFoundError(GmailAutomationError):
    """Raised when a requested resource is not found."""
    pass

class RateLimitError(ExternalServiceError):
    """Raised specifically for rate limiting errors from external services."""
    pass

class EmailProcessingError(GmailAutomationError):
    """Raised for errors during the processing or normalization of emails."""
    pass

class SyncStateError(GmailAutomationError):
    """Raised for errors related to synchronization state management (e.g., Redis issues)."""
    pass
