"""Vercel log store for request-keyed storage with TTL expiration."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class VercelLogStore:
    """Store for Vercel runtime logs keyed by request ID with TTL expiration."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        """
        Initialize the log store.

        Args:
            ttl_seconds: Time-to-live for log entries in seconds (default: 60)
        """
        self._ttl_seconds = ttl_seconds
        self._logs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._timestamps: dict[str, float] = {}

    def add_logs(self, logs: list[dict[str, Any]]) -> None:
        """
        Add logs to the store, keyed by requestId.

        Logs without a requestId or with an empty requestId are skipped.
        Triggers cleanup of expired entries.

        Args:
            logs: List of log entry dictionaries
        """
        self._cleanup_expired()

        for log in logs:
            request_id = log.get("requestId")
            if not request_id:
                continue

            self._logs[request_id].append(log)
            self._timestamps[request_id] = time.time()

    def get_logs(self, request_id: str) -> list[dict[str, Any]]:
        """
        Get logs for a given request ID.

        Args:
            request_id: The request ID to look up

        Returns:
            List of log entries for the request, or empty list if not found
        """
        return list(self._logs.get(request_id, []))

    def pop_logs(self, request_id: str) -> list[dict[str, Any]]:
        """
        Get and remove logs for a given request ID.

        Args:
            request_id: The request ID to look up

        Returns:
            List of log entries for the request, or empty list if not found
        """
        logs = self._logs.pop(request_id, [])
        self._timestamps.pop(request_id, None)
        return logs

    def has_logs(self, request_id: str) -> bool:
        """
        Check if logs exist for a given request ID.

        Args:
            request_id: The request ID to check

        Returns:
            True if logs exist for the request ID, False otherwise
        """
        return request_id in self._logs and len(self._logs[request_id]) > 0

    def format_logs_as_string(self, request_id: str) -> str:
        """
        Format logs for a request ID as a human-readable string.

        Args:
            request_id: The request ID to format logs for

        Returns:
            Formatted log string with timestamp, level, and message per line
        """
        logs = self.get_logs(request_id)
        if not logs:
            return ""

        formatted_lines = []
        for log in logs:
            formatted_lines.append(self._format_log_entry(log))

        return "\n".join(formatted_lines)

    def _format_log_entry(self, log: dict[str, Any]) -> str:
        """
        Format a single log entry as a string.

        Args:
            log: Log entry dictionary

        Returns:
            Formatted string with timestamp, level, and message
        """
        # Format timestamp
        timestamp_str = ""
        if "timestamp" in log:
            timestamp_ms = log["timestamp"]
            try:
                dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, OSError):
                timestamp_str = str(timestamp_ms)

        # Format level
        level = log.get("level", "unknown").upper()

        # Get message
        message = log.get("message", "")

        # Build formatted line
        parts = []
        if timestamp_str:
            parts.append(timestamp_str)
        parts.append(f"[{level}]")
        parts.append(message)

        return " ".join(parts)

    def _cleanup_expired(self) -> None:
        """Remove entries that have exceeded their TTL."""
        current_time = time.time()
        expired_keys = [
            request_id
            for request_id, timestamp in self._timestamps.items()
            if current_time - timestamp > self._ttl_seconds
        ]

        for request_id in expired_keys:
            del self._logs[request_id]
            del self._timestamps[request_id]
