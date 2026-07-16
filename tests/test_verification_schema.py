"""Unit tests for the verification request schema."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.schemas.verification import (
    IdType,
    RequestValidationError,
    validate_verification_request,
)


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_ref_id": "ALB-2026-000123",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "name": "Rahul Sharma",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("id_type", "id_number"),
    [
        ("PAN", "ABCDE1234F"),
        ("DL", "DL-0420110149646"),
        ("VOTER", "ABC1234567"),
    ],
)
def test_accepts_supported_id_types(id_type, id_number):
    result = validate_verification_request(
        _valid_payload(id_type=id_type, id_number=id_number)
    )

    assert result.id_type is IdType(id_type)


def test_trims_surrounding_whitespace_without_mutating_input():
    payload = _valid_payload(
        client_ref_id="  ALB-2026-000123  ",
        id_type="  PAN  ",
        id_number="  ABCDE1234F  ",
        name="  Rahul Sharma  ",
    )
    original = payload.copy()

    result = validate_verification_request(payload)

    assert result.client_ref_id == "ALB-2026-000123"
    assert result.id_type is IdType.PAN
    assert result.id_number == "ABCDE1234F"
    assert result.name == "Rahul Sharma"
    assert payload == original


@pytest.mark.parametrize("payload", [None, [], "invalid", 42, True])
def test_rejects_non_object_payloads(payload):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(payload)

    assert exc_info.value.reason == "INVALID_BODY"
    assert exc_info.value.field is None


@pytest.mark.parametrize(
    "missing_field",
    ["client_ref_id", "id_type", "id_number", "name"],
)
def test_rejects_each_missing_required_field(missing_field):
    payload = _valid_payload()
    del payload[missing_field]

    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(payload)

    assert exc_info.value.reason == "MISSING_FIELD"
    assert exc_info.value.field == missing_field


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("client_ref_id", 123),
        ("id_type", ["PAN"]),
        ("id_number", None),
        ("name", False),
    ],
)
def test_rejects_non_string_field_values(field, invalid_value):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(**{field: invalid_value}))

    assert exc_info.value.reason == "INVALID_TYPE"
    assert exc_info.value.field == field


@pytest.mark.parametrize("field", ["client_ref_id", "id_type", "id_number", "name"])
@pytest.mark.parametrize("invalid_value", ["", "   "])
def test_rejects_empty_and_whitespace_only_values(field, invalid_value):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(**{field: invalid_value}))

    assert exc_info.value.reason == "EMPTY_VALUE"
    assert exc_info.value.field == field


@pytest.mark.parametrize("id_type", ["PASSPORT", "pan", "Pan"])
def test_rejects_unsupported_or_non_uppercase_id_type(id_type):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(id_type=id_type))

    assert exc_info.value.reason == "UNSUPPORTED_ID_TYPE"
    assert exc_info.value.field == "id_type"


def test_rejects_unknown_fields():
    payload = _valid_payload(unexpected="value")

    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(payload)

    assert exc_info.value.reason == "UNKNOWN_FIELD"
    assert exc_info.value.field == "unexpected"


@pytest.mark.parametrize(
    "client_ref_id",
    ["ABC", "ALB-2026-000123", "client_123", "CLIENT.REF/2026", "A" * 64],
)
def test_accepts_valid_client_reference_formats(client_ref_id):
    result = validate_verification_request(
        _valid_payload(client_ref_id=client_ref_id)
    )

    assert result.client_ref_id == client_ref_id


@pytest.mark.parametrize(
    "client_ref_id",
    ["AB", "-ALB123", "ALB 123", "ALB@123", "A" * 65],
)
def test_rejects_invalid_client_reference_formats(client_ref_id):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(
            _valid_payload(client_ref_id=client_ref_id)
        )

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == "client_ref_id"


@pytest.mark.parametrize("id_number", ["ABCDE1234F", "AAAAA0000A"])
def test_accepts_valid_pan_formats(id_number):
    result = validate_verification_request(_valid_payload(id_number=id_number))

    assert result.id_number == id_number


@pytest.mark.parametrize(
    "id_number",
    ["abcde1234f", "ABCD1234F", "ABCDEF1234", "ABCDE12345", "ABCDE-1234F"],
)
def test_rejects_invalid_pan_formats(id_number):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(id_number=id_number))

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == "id_number"


@pytest.mark.parametrize(
    "id_number",
    ["ABC123", "DL-0420110149646", "MH14 20110012345", "KA01/2020/1234567"],
)
def test_accepts_valid_driving_licence_formats(id_number):
    result = validate_verification_request(
        _valid_payload(id_type="DL", id_number=id_number)
    )

    assert result.id_number == id_number


@pytest.mark.parametrize(
    "id_number",
    ["ABC", "dl-0420110149646", "DL@042011", "-DL042011", "A" * 26],
)
def test_rejects_invalid_driving_licence_formats(id_number):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(
            _valid_payload(id_type="DL", id_number=id_number)
        )

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == "id_number"


@pytest.mark.parametrize(
    "id_number",
    ["ABC123", "ABC1234567", "VOTER-12345", "AB/1234567", "A" * 20],
)
def test_accepts_valid_voter_id_formats(id_number):
    result = validate_verification_request(
        _valid_payload(id_type="VOTER", id_number=id_number)
    )

    assert result.id_number == id_number


@pytest.mark.parametrize(
    "id_number",
    ["ABC", "abc1234567", "ABC 1234567", "@ABC1234567", "A" * 21],
)
def test_rejects_invalid_voter_id_formats(id_number):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(
            _valid_payload(id_type="VOTER", id_number=id_number)
        )

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == "id_number"


@pytest.mark.parametrize(
    "name",
    [
        "Al",
        "Rahul Sharma",
        "A. P. J. Abdul Kalam",
        "Anne-Marie O'Neil",
        "José Álvarez",
        "O’Connor",
        "A" * 100,
    ],
)
def test_accepts_valid_names(name):
    result = validate_verification_request(_valid_payload(name=name))

    assert result.name == name


@pytest.mark.parametrize(
    "name",
    ["R", "Rahul123", "123456", "@", "Rahul\tSharma", "Rahul\nSharma", "A" * 101],
)
def test_rejects_invalid_names(name):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(name=name))

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == "name"


@pytest.mark.parametrize(
    ("field", "sensitive_value", "overrides"),
    [
        (
            "id_number",
            "SECRET-PAN-VALUE",
            {"id_type": "PAN", "id_number": "SECRET-PAN-VALUE"},
        ),
        (
            "name",
            "Sensitive123Name",
            {"name": "Sensitive123Name"},
        ),
    ],
)
def test_sensitive_values_are_not_exposed_in_format_errors(
    field, sensitive_value, overrides
):
    with pytest.raises(RequestValidationError) as exc_info:
        validate_verification_request(_valid_payload(**overrides))

    assert exc_info.value.reason == "INVALID_FORMAT"
    assert exc_info.value.field == field
    assert sensitive_value not in str(exc_info.value)


def test_returned_request_is_immutable():
    result = validate_verification_request(_valid_payload())

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed Name"
