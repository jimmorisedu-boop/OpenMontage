"""Runtime enforcement for OpenMontage's air-gapped mode."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse


class OfflineViolation(RuntimeError):
    pass


def offline_enabled() -> bool:
    return os.environ.get("OPENMONTAGE_OFFLINE", "0") == "1"


def _remote_urls(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            found.extend(_remote_urls(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_remote_urls(child))
    elif isinstance(value, str):
        lowered = value.strip().lower()
        if lowered.startswith(("\\\\", "//")) and not lowered.startswith("\\\\?\\"):
            found.append(value)
        elif lowered.startswith("www."):
            found.append(value)
        elif lowered.startswith(("http://", "https://", "ftp://", "ftps://", "s3://", "gs://", "ws://", "wss://")):
            host = urlparse(value).hostname
            if host not in {"127.0.0.1", "localhost", "::1"}:
                found.append(value)
    return found


def ensure_tool_is_offline(tool: Any, inputs: Any) -> None:
    if not offline_enabled():
        return
    runtime = getattr(getattr(tool, "runtime", None), "value", getattr(tool, "runtime", None))
    profile = getattr(tool, "resource_profile", None)
    if runtime in {"api", "hybrid"} or bool(getattr(profile, "network_required", False)):
        raise OfflineViolation(f"Offline mode blocked network-capable tool: {getattr(tool, 'name', tool.__class__.__name__)}")
    urls = _remote_urls(inputs)
    if urls:
        raise OfflineViolation(f"Offline mode accepts local paths only; remote URL rejected: {urls[0]}")
