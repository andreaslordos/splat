"""Tests for GitHub issue formatting."""

from __future__ import annotations

from splat.core.formatter import format_issue_body, format_issue_title


class TestFormatIssueTitle:
    """Test issue title formatting."""

    def test_title_includes_splat_prefix(self) -> None:
        """Title should start with [Splat] prefix."""
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert title.startswith("[Splat]")

    def test_title_includes_exception_type(self) -> None:
        """Title should include the exception type name."""
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert "ValueError" in title

    def test_title_includes_filename_and_line(self) -> None:
        """Title should include filename:line format."""
        try:
            raise ValueError("test")
        except ValueError as e:
            title = format_issue_title(e)
            assert "test_formatter.py" in title
            assert ":" in title  # filename:line format

    def test_title_format_with_different_exception_types(self) -> None:
        """Title should work with various exception types."""
        try:
            raise TypeError("wrong type")
        except TypeError as e:
            title = format_issue_title(e)
            assert "TypeError" in title
            assert title.startswith("[Splat]")

    def test_title_with_no_traceback(self) -> None:
        """Title should handle exception with no traceback gracefully."""
        exc = RuntimeError("no tb")
        exc.__traceback__ = None
        title = format_issue_title(exc)
        assert title.startswith("[Splat]")
        assert "RuntimeError" in title
        assert "unknown" in title


class TestFormatIssueBody:
    """Test issue body formatting."""

    def test_body_includes_error_section(self) -> None:
        """Body should include Error section with type and message."""
        try:
            raise ValueError("test message")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Error" in body
            assert "ValueError" in body
            assert "test message" in body

    def test_body_includes_traceback(self) -> None:
        """Body should include Traceback section."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Traceback" in body
            assert "ValueError" in body

    def test_body_includes_signature(self) -> None:
        """Body should include the error signature."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "abc12345" in body

    def test_body_includes_context_when_provided(self) -> None:
        """Body should include Context section when context dict provided."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                context={"user_id": 123, "endpoint": "/api"},
            )
            assert "## Context" in body
            assert "user_id" in body
            assert "123" in body

    def test_body_includes_logs_when_provided(self) -> None:
        """Body should include Recent Logs section when logs provided."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                logs="2025-01-25 INFO Test log",
            )
            assert "## Recent Logs" in body
            assert "Test log" in body

    def test_body_omits_context_when_empty(self) -> None:
        """Body should not include Context section when no context."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "## Context" not in body

    def test_body_omits_logs_when_empty(self) -> None:
        """Body should not include Recent Logs section when logs empty."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345", logs="")
            assert "## Recent Logs" not in body

    def test_body_omits_logs_when_none(self) -> None:
        """Body should not include Recent Logs section when logs is None."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345", logs=None)
            assert "## Recent Logs" not in body

    def test_body_includes_file_location(self) -> None:
        """Body should include file path and line number."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "**File:**" in body
            assert "**Line:**" in body
            assert "test_formatter.py" in body

    def test_body_includes_function_name(self) -> None:
        """Body should include the function name where exception occurred."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "**Function:**" in body
            assert "test_body_includes_function_name" in body

    def test_body_with_no_traceback(self) -> None:
        """Body should handle exception with no traceback gracefully."""
        exc = RuntimeError("no tb")
        exc.__traceback__ = None
        body = format_issue_body(exc, signature="abc12345")
        assert "## Error" in body
        assert "RuntimeError" in body
        assert "unknown" in body

    def test_body_includes_splat_attribution(self) -> None:
        """Body should include Splat attribution in footer."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(e, signature="abc12345")
            assert "Splat" in body
            assert "Signature:" in body

    def test_body_context_as_table(self) -> None:
        """Context should be formatted as a markdown table."""
        try:
            raise ValueError("test")
        except ValueError as e:
            body = format_issue_body(
                e,
                signature="abc12345",
                context={"key1": "value1", "key2": "value2"},
            )
            assert "| Key | Value |" in body
            assert "| key1 | value1 |" in body
            assert "| key2 | value2 |" in body
