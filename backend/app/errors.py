class NotFoundError(Exception):
    """Requested resource does not exist (HTTP 404)."""


class ConflictError(Exception):
    """Request clashes with existing data, e.g. duplicate reference ID (HTTP 409)."""


class BusinessRuleError(Exception):
    """Request is well-formed but breaks an auction rule (HTTP 400)."""
