"""Shared utilities for parsing CLI options and computing metrics."""

from __future__ import annotations

import re

# --- Size Parsing ---

_SIZE_UNITS = {
    "B": 1,
    "KB": 1_000,
    "MB": 1_000_000,
    "GB": 1_000_000_000,
    "TB": 1_000_000_000_000,
}

_DURATION_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
}


def parse_size(size_str: str) -> int:
    """Parse a human-readable size string (e.g. '10GB', '500MB') into bytes."""
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$", size_str)
    if not match:
        raise ValueError(f"Invalid size format: '{size_str}'. Expected e.g. '10GB', '500MB'.")
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit: '{unit}'. Supported: {list(_SIZE_UNITS.keys())}")
    return int(value * _SIZE_UNITS[unit])


def parse_duration(dur_str: str) -> float:
    """Parse a duration string (e.g. '5m', '30s', '1h') into seconds."""
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$", dur_str)
    if not match:
        raise ValueError(f"Invalid duration format: '{dur_str}'. Expected e.g. '5m', '30s', '1h'.")
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit not in _DURATION_UNITS:
        raise ValueError(f"Unknown duration unit: '{unit}'. Supported: {list(_DURATION_UNITS.keys())}")
    return value * _DURATION_UNITS[unit]


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.2f} GB"
    elif size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.2f} MB"
    elif size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.2f} KB"
    return f"{size_bytes} B"


def format_throughput(bytes_per_sec: float) -> str:
    """Format throughput as human-readable MB/s or GB/s."""
    if bytes_per_sec >= 1_000_000_000:
        return f"{bytes_per_sec / 1_000_000_000:.2f} GB/s"
    elif bytes_per_sec >= 1_000_000:
        return f"{bytes_per_sec / 1_000_000:.2f} MB/s"
    elif bytes_per_sec >= 1_000:
        return f"{bytes_per_sec / 1_000:.2f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"
