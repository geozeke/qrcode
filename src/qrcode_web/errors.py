"""Structured validation errors returned by internal API routes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One user-correctable validation failure.

    Parameters
    ----------
    path : str
        Dot-separated request path.
    code : str
        Stable machine-readable failure code.
    message : str
        Safe message suitable for display in the user interface.
    """

    path: str
    code: str
    message: str


class RequestValidationError(ValueError):
    """Exception containing one or more request validation issues.

    Parameters
    ----------
    issues : list[ValidationIssue]
        User-correctable validation failures.
    """

    def __init__(self, issues: list[ValidationIssue]) -> None:
        """Initialize the validation exception.

        Parameters
        ----------
        issues : list[ValidationIssue]
            User-correctable validation failures.
        """
        super().__init__("Request validation failed.")
        self.issues = issues
