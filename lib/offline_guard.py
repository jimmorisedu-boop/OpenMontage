"""Compatibility facade for OpenMontage's explicit network policy."""

from __future__ import annotations

from typing import Any

from lib.network_policy import (
    NetworkRequest,
    NetworkViolation,
    authorize_network,
    current_network_mode,
    is_loopback_url,
    tool_allowed,
    tool_is_network_capable,
    urls_in,
)


class OfflineViolation(NetworkViolation):
    pass


def offline_enabled() -> bool:
    from lib.network_policy import NetworkMode

    return current_network_mode() is NetworkMode.STRICT_OFFLINE


def ensure_tool_is_offline(tool: Any, inputs: Any) -> None:
    mode = current_network_mode()
    if mode is None:
        return
    name = getattr(tool, "name", tool.__class__.__name__)
    urls = urls_in(inputs)
    if not tool_allowed(tool, mode):
        raise OfflineViolation(f"Network policy blocked network-capable tool: {name}")
    for url in urls:
        try:
            authorize_network(NetworkRequest(component=name, submitted_url=url), mode)
        except NetworkViolation as exc:
            if mode.value == "strict-offline" and not is_loopback_url(url):
                raise OfflineViolation(
                    f"Offline mode accepts local paths only; remote URL rejected: {url}"
                ) from exc
            raise OfflineViolation(str(exc)) from exc
