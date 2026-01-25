"""Tests for log buffer capture."""

import logging

from splat.core.log_buffer import LogBuffer, get_recent_logs, install_log_buffer


class TestLogBuffer:
    """Test LogBuffer class."""

    def test_buffer_captures_log_messages(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_capture")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Test message")

        logs = buffer.get_logs()
        assert len(logs) == 1
        assert "Test message" in logs[0]

    def test_buffer_respects_capacity(self) -> None:
        buffer = LogBuffer(capacity=3)
        logger = logging.getLogger("test_capacity")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        for i in range(5):
            logger.info(f"Message {i}")

        logs = buffer.get_logs()
        assert len(logs) == 3
        assert "Message 2" in logs[0]
        assert "Message 4" in logs[2]

    def test_buffer_formats_with_timestamp(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_format")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Formatted message")

        logs = buffer.get_logs()
        assert "INFO" in logs[0]
        assert "Formatted message" in logs[0]

    def test_get_logs_as_string_joins_entries(self) -> None:
        buffer = LogBuffer(capacity=10)
        logger = logging.getLogger("test_string")
        logger.addHandler(buffer)
        logger.setLevel(logging.INFO)

        logger.info("Line 1")
        logger.info("Line 2")

        log_string = buffer.get_logs_as_string()
        assert "Line 1" in log_string
        assert "Line 2" in log_string
        assert "\n" in log_string


class TestInstallLogBuffer:
    """Test global log buffer installation."""

    def test_install_creates_global_buffer(self) -> None:
        buffer = install_log_buffer(capacity=50)
        assert buffer is not None

    def test_get_recent_logs_returns_captured_logs(self) -> None:
        install_log_buffer(capacity=50)
        logger = logging.getLogger("test_global")
        logger.setLevel(logging.INFO)

        logger.info("Global test message")

        logs = get_recent_logs()
        # May contain other logs too, just check ours is there
        assert any("Global test message" in log for log in logs)
