"""Rolling log buffer that captures recent log entries."""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque

_global_buffer: LogBuffer | None = None


class LogBuffer(logging.Handler):
    """A logging handler that maintains a rolling buffer of recent entries."""

    def __init__(self, capacity: int = 200) -> None:
        """
        Initialize the log buffer.

        Args:
            capacity: Maximum number of log entries to retain
        """
        super().__init__()
        self._buffer: Deque[str] = deque(maxlen=capacity)
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s")
        )

    def emit(self, record: logging.LogRecord) -> None:
        """
        Add a log record to the buffer.

        Args:
            record: The log record to add
        """
        try:
            msg = self.format(record)
            self._buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self) -> list[str]:
        """
        Get all buffered log entries.

        Returns:
            List of formatted log strings, oldest first
        """
        return list(self._buffer)

    def get_logs_as_string(self) -> str:
        """
        Get all buffered log entries as a single string.

        Returns:
            Newline-joined log entries
        """
        return "\n".join(self._buffer)


def install_log_buffer(capacity: int = 200) -> LogBuffer:
    """
    Install a global log buffer on the root logger.

    Args:
        capacity: Maximum number of log entries to retain

    Returns:
        The installed LogBuffer instance
    """
    global _global_buffer
    _global_buffer = LogBuffer(capacity=capacity)
    logging.getLogger().addHandler(_global_buffer)
    return _global_buffer


def get_recent_logs() -> list[str]:
    """
    Get recent logs from the global buffer.

    Returns:
        List of recent log entries, or empty list if not installed
    """
    if _global_buffer is None:
        return []
    return _global_buffer.get_logs()


def get_recent_logs_as_string() -> str:
    """
    Get recent logs from the global buffer as a string.

    Returns:
        Newline-joined log entries, or empty string if not installed
    """
    if _global_buffer is None:
        return ""
    return _global_buffer.get_logs_as_string()
