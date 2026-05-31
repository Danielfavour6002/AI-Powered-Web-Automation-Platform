"""Custom exceptions for QA Platform."""

class QAPError(Exception):
    """Base exception for QA Platform."""
    pass

class ConfigError(QAPError):
    """Raised when there is a configuration error."""
    pass

class DatabaseError(QAPError):
    """Raised when a database operation fails."""
    pass

class RecordingError(QAPError):
    """Raised when an error occurs during test recording."""
    pass

class ReplayError(QAPError):
    """Raised when an error occurs during test replay."""
    pass

class ReportError(QAPError):
    """Raised when an error occurs during report generation."""
    pass

class StepFailedError(QAPError):
    """Raised when a test step fails during execution."""
    
    def __init__(self, step_id: str, message: str, screenshot_path: str | None = None) -> None:
        """Initialize StepFailedError."""
        super().__init__(message)
        self.step_id = step_id
        self.message = message
        self.screenshot_path = screenshot_path
