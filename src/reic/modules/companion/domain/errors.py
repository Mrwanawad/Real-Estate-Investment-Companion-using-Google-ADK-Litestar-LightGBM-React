class CompanionError(Exception):
    """Base error of the companion module."""


class SessionNotFoundError(CompanionError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"unknown chat session: {session_id}")
        self.session_id = session_id


class ToolInputError(CompanionError):
    """A tool was called with arguments it cannot use; the message goes back to the model."""
