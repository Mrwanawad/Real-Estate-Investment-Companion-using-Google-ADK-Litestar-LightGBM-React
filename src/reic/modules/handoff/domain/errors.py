class HandoffError(Exception):
    """Base class for handoff domain errors."""


class LeadValidationError(HandoffError, ValueError):
    """Raised when a lead is missing contact details or has out-of-range fields."""


class LeadNotFoundError(HandoffError):
    def __init__(self, lead_id: str) -> None:
        super().__init__(f"Lead not found: {lead_id!r}")
        self.lead_id = lead_id


class InvalidStatusTransitionError(HandoffError):
    def __init__(self, current: str, new: str) -> None:
        super().__init__(f"Cannot move a lead from {current!r} to {new!r}")
        self.current = current
        self.new = new
