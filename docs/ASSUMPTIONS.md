# Assumptions

## Verification payload validation

The assignment defines the required verification fields and supported ID types,
but it does not specify exact length limits or authoritative document-number
formats. VeriGate therefore applies the following documented validation rules.

### `client_ref_id`

- Length: 3–64 characters.
- Must begin with a letter or digit.
- Letters, numbers, dots, underscores, slashes, and hyphens are accepted.
- Spaces are rejected.

This keeps client-generated references flexible while rejecting control
characters and unusual punctuation.

### PAN

PAN is validated using its stable ten-character structure:

- Five uppercase letters.
- Four digits.
- One uppercase letter.

Example: `ABCDE1234F`.

### Driving licence

Driving licence formats differ across Indian states and legacy systems, so
validation is intentionally conservative:

- Length: 6–25 characters.
- Uppercase letters and numbers are accepted.
- Spaces, slashes, and hyphens are permitted.
- The first character must be a letter or digit.

The API does not attempt state-specific semantic validation.

### Voter ID

Voter IDs use a broad synthetic-data-friendly format:

- Length: 6–20 characters.
- Uppercase letters and numbers are accepted.
- Slashes and hyphens are permitted.
- Spaces are rejected.
- The first character must be a letter or digit.

A strict EPIC-only pattern is not enforced because the assignment does not
define a specific voter-ID format and may use synthetic identifiers.

### Name

- Length: 2–100 characters.
- Must contain at least one alphabetic Unicode character.
- Digits and control characters are rejected.
- Unicode letters and combining marks are accepted.
- Spaces, apostrophes, periods, and hyphens are accepted.

The application performs structural validation only. It does not attempt to
determine whether a person's name is real.
