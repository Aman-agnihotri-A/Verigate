"""Client IP extraction and whitelist validation utilities."""
from __future__ import annotations

from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address, ip_address

IPAddress = IPv4Address | IPv6Address


class ClientIPError(ValueError):
    """Safe client-IP validation error for gateway-level handling."""

    def __init__(self, *, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _parse_ip(value: str, *, reason: str, message: str) -> IPAddress:
    """Parse one IP address and translate parser failures into safe errors."""
    try:
        return ip_address(value)
    except ValueError as exc:
        raise ClientIPError(reason=reason, message=message) from exc


def extract_client_ip(
    forwarded_for: str | None,
    remote_addr: str | None,
) -> str:
    """Return the normalized originating IP from forwarding or socket data.

    When ``X-Forwarded-For`` is present, the first comma-separated value is
    treated as the originating client address, matching the assignment's
    local-testing contract. Production code must only pass this header when
    the immediate peer is a trusted reverse proxy.
    """
    candidate: str | None = None

    if forwarded_for is not None and forwarded_for.strip():
        candidate = forwarded_for.split(",", maxsplit=1)[0].strip()
    elif remote_addr is not None and remote_addr.strip():
        candidate = remote_addr.strip()

    if not candidate:
        raise ClientIPError(
            reason="MISSING_CLIENT_IP",
            message="Client IP address is unavailable",
        )

    parsed = _parse_ip(
        candidate,
        reason="INVALID_CLIENT_IP",
        message="Client IP address is invalid",
    )
    return str(parsed)


def _normalized_whitelist(whitelisted_ips: Iterable[str]) -> set[IPAddress]:
    """Parse whitelist entries without mutating the caller-owned collection."""
    normalized: set[IPAddress] = set()
    for entry in whitelisted_ips:
        if not isinstance(entry, str) or not entry.strip():
            raise ClientIPError(
                reason="INVALID_WHITELIST_ENTRY",
                message="Client IP whitelist contains an invalid entry",
            )
        normalized.add(
            _parse_ip(
                entry.strip(),
                reason="INVALID_WHITELIST_ENTRY",
                message="Client IP whitelist contains an invalid entry",
            )
        )
    return normalized


def is_ip_whitelisted(
    client_ip: str,
    whitelisted_ips: Iterable[str],
) -> bool:
    """Return whether a valid client IP exactly matches a whitelist entry."""
    if not isinstance(client_ip, str) or not client_ip.strip():
        raise ClientIPError(
            reason="INVALID_CLIENT_IP",
            message="Client IP address is invalid",
        )

    parsed_client_ip = _parse_ip(
        client_ip.strip(),
        reason="INVALID_CLIENT_IP",
        message="Client IP address is invalid",
    )
    return parsed_client_ip in _normalized_whitelist(whitelisted_ips)


def validate_client_ip(
    forwarded_for: str | None,
    remote_addr: str | None,
    whitelisted_ips: Iterable[str],
) -> str:
    """Return the normalized client IP when allowed; otherwise raise safely."""
    client_ip = extract_client_ip(forwarded_for, remote_addr)
    if not is_ip_whitelisted(client_ip, whitelisted_ips):
        raise ClientIPError(
            reason="IP_NOT_WHITELISTED",
            message="Source IP is not whitelisted for this client",
        )
    return client_ip
