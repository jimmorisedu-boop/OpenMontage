"""Central network authorization for local OpenMontage runtimes."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class NetworkMode(str, Enum):
    STRICT_OFFLINE = "strict-offline"
    URL_IMPORT_ONLY = "url-import-only"


class NetworkViolation(RuntimeError):
    """Raised when a component attempts network access outside the policy."""


@dataclass(frozen=True)
class NetworkRequest:
    component: str
    submitted_url: str | None = None


_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}
_REMOTE_SCHEMES = {"http", "https", "ftp", "ftps", "s3", "gs", "ws", "wss", "file"}


def current_network_mode() -> NetworkMode | None:
    """Return the active restriction, preserving legacy unrestricted sessions."""
    if os.environ.get("OPENMONTAGE_OFFLINE") == "1":
        return NetworkMode.STRICT_OFFLINE
    raw = os.environ.get("OPENMONTAGE_NETWORK_MODE", "").strip().lower()
    if not raw:
        return None
    try:
        return NetworkMode(raw)
    except ValueError as exc:
        raise NetworkViolation(f"Unknown OPENMONTAGE_NETWORK_MODE: {raw}") from exc


def _host_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None


def is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    address = _host_ip(host)
    return parsed.scheme in {"http", "https"} and (
        host in _LOOPBACK_NAMES or bool(address and address.is_loopback)
    )


def validate_public_import_url(url: str) -> None:
    if url.startswith(("\\\\", "//")):
        raise NetworkViolation("URL import rejects UNC and network-share paths")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise NetworkViolation("URL import accepts only explicit HTTP(S) URLs")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkViolation("URL import rejects credentials embedded in URLs")
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise NetworkViolation("URL import requires a hostname")
    address = _host_ip(host)
    if host in _LOOPBACK_NAMES or (address and not address.is_global):
        raise NetworkViolation("URL import requires a public source host")


def authorize_network(request: NetworkRequest, mode: NetworkMode | None = None) -> None:
    active = current_network_mode() if mode is None else mode
    if active is None or request.submitted_url is None:
        return

    if request.component != "url_import_gateway" and is_loopback_url(request.submitted_url):
        return
    if active is NetworkMode.STRICT_OFFLINE:
        raise NetworkViolation("strict-offline mode rejects all public network access")
    if request.component != "url_import_gateway":
        raise NetworkViolation("url-import-only mode permits only url_import_gateway")
    validate_public_import_url(request.submitted_url)


def urls_in(value: Any) -> list[str]:
    """Find URL-like or UNC strings in a nested tool input."""
    found: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            found.extend(urls_in(child))
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            found.extend(urls_in(child))
    elif isinstance(value, str):
        stripped = value.strip()
        parsed = urlparse(stripped)
        if stripped.startswith(("\\\\", "//", "www.")) or parsed.scheme.lower() in _REMOTE_SCHEMES:
            found.append(stripped)
    return found


def tool_is_network_capable(tool: Any) -> bool:
    runtime = getattr(getattr(tool, "runtime", None), "value", getattr(tool, "runtime", None))
    profile = getattr(tool, "resource_profile", None)
    return runtime in {"api", "hybrid"} or bool(getattr(profile, "network_required", False))


def tool_allowed(tool: Any, mode: NetworkMode | None = None) -> bool:
    active = current_network_mode() if mode is None else mode
    if active is None:
        return True
    name = getattr(tool, "name", tool.__class__.__name__)
    if name == "url_import_gateway":
        return active is NetworkMode.URL_IMPORT_ONLY
    return not tool_is_network_capable(tool)

