"""Validation contract for verification request payloads."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Final


class IdType(str, Enum):
    """Supported identity document types."""

    PAN = "PAN"
    DL = "DL"
    VOTER = "VOTER"


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    """Validated and normalized verification request data."""

    client_ref_id: str
    id_type: IdType
    id_number: str
    name: str


class RequestValidationError(ValueError):
    """Safe validation error suitable for mapping to API error VP4022."""

    def __init__(
        self,
        *,
        reason: str,
        message: str,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.field = field
        self.message = message


_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {"client_ref_id", "id_type", "id_number", "name"}
)

_CLIENT_REF_MIN_LENGTH: Final = 3
_CLIENT_REF_MAX_LENGTH: Final = 64
_NAME_MIN_LENGTH: Final = 2
_NAME_MAX_LENGTH: Final = 100
_DL_MIN_LENGTH: Final = 6
_DL_MAX_LENGTH: Final = 25
_VOTER_MIN_LENGTH: Final = 6
_VOTER_MAX_LENGTH: Final = 20

_PAN_PATTERN: Final = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_CLIENT_REF_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_DL_PATTERN: Final = re.compile(r"^[A-Z0-9][A-Z0-9 /-]*$")
_VOTER_PATTERN: Final = re.compile(r"^[A-Z0-9][A-Z0-9/-]*$")
_ALLOWED_NAME_PUNCTUATION: Final[frozenset[str]] = frozenset({"'", "’", ".", "-"})


def _invalid_format(field: str, message: str) -> RequestValidationError:
    """Build a safe field-format error without echoing submitted data."""
    return RequestValidationError(
        reason="INVALID_FORMAT",
        field=field,
        message=message,
    )


def _validate_client_ref_id(value: str) -> None:
    """Validate a client-generated request reference."""
    if not _CLIENT_REF_MIN_LENGTH <= len(value) <= _CLIENT_REF_MAX_LENGTH:
        raise _invalid_format(
            "client_ref_id",
            "client_ref_id has an invalid format",
        )
    if _CLIENT_REF_PATTERN.fullmatch(value) is None:
        raise _invalid_format(
            "client_ref_id",
            "client_ref_id has an invalid format",
        )


def _validate_pan(value: str) -> None:
    """Validate a PAN number using its stable ten-character structure."""
    if _PAN_PATTERN.fullmatch(value) is None:
        raise _invalid_format(
            "id_number",
            "id_number has an invalid PAN format",
        )


def _validate_dl(value: str) -> None:
    """Validate a driving licence using a conservative cross-state format."""
    if not _DL_MIN_LENGTH <= len(value) <= _DL_MAX_LENGTH:
        raise _invalid_format(
            "id_number",
            "id_number has an invalid driving licence format",
        )
    if _DL_PATTERN.fullmatch(value) is None:
        raise _invalid_format(
            "id_number",
            "id_number has an invalid driving licence format",
        )


def _validate_voter(value: str) -> None:
    """Validate a voter ID using a synthetic-data-friendly format."""
    if not _VOTER_MIN_LENGTH <= len(value) <= _VOTER_MAX_LENGTH:
        raise _invalid_format(
            "id_number",
            "id_number has an invalid voter ID format",
        )
    if _VOTER_PATTERN.fullmatch(value) is None:
        raise _invalid_format(
            "id_number",
            "id_number has an invalid voter ID format",
        )


def _validate_name(value: str) -> None:
    """Validate a human name without restricting it to ASCII letters."""
    if not _NAME_MIN_LENGTH <= len(value) <= _NAME_MAX_LENGTH:
        raise _invalid_format("name", "name has an invalid format")

    has_letter = False
    for character in value:
        category = unicodedata.category(character)
        if category.startswith("L"):
            has_letter = True
            continue
        if category.startswith("M"):
            continue
        if character == " " or character in _ALLOWED_NAME_PUNCTUATION:
            continue
        raise _invalid_format("name", "name has an invalid format")

    if not has_letter:
        raise _invalid_format("name", "name has an invalid format")


_ID_NUMBER_VALIDATORS: Final[dict[IdType, Callable[[str], None]]] = {
    IdType.PAN: _validate_pan,
    IdType.DL: _validate_dl,
    IdType.VOTER: _validate_voter,
}


def validate_verification_request(payload: object) -> VerificationRequest:
    """Validate raw JSON-compatible input without mutating caller-owned data."""
    if not isinstance(payload, dict):
        raise RequestValidationError(
            reason="INVALID_BODY",
            message="Request body must be a JSON object",
        )

    received_fields = set(payload)
    missing_fields = _REQUIRED_FIELDS - received_fields
    if missing_fields:
        field = sorted(missing_fields)[0]
        raise RequestValidationError(
            reason="MISSING_FIELD",
            field=field,
            message=f"Required field is missing: {field}",
        )

    unknown_fields = received_fields - _REQUIRED_FIELDS
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        raise RequestValidationError(
            reason="UNKNOWN_FIELD",
            field=field,
            message=f"Unknown field is not allowed: {field}",
        )

    normalized: dict[str, str] = {}
    for field in sorted(_REQUIRED_FIELDS):
        value = payload[field]
        if not isinstance(value, str):
            raise RequestValidationError(
                reason="INVALID_TYPE",
                field=field,
                message=f"Field must be a string: {field}",
            )

        stripped_value = value.strip()
        if not stripped_value:
            raise RequestValidationError(
                reason="EMPTY_VALUE",
                field=field,
                message=f"Field must not be empty: {field}",
            )
        normalized[field] = stripped_value

    try:
        id_type = IdType(normalized["id_type"])
    except ValueError as exc:
        raise RequestValidationError(
            reason="UNSUPPORTED_ID_TYPE",
            field="id_type",
            message="Unsupported id_type",
        ) from exc

    _validate_client_ref_id(normalized["client_ref_id"])
    _validate_name(normalized["name"])
    _ID_NUMBER_VALIDATORS[id_type](normalized["id_number"])

    return VerificationRequest(
        client_ref_id=normalized["client_ref_id"],
        id_type=id_type,
        id_number=normalized["id_number"],
        name=normalized["name"],
    )
