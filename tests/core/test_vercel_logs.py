"""Tests for Vercel log store."""

from __future__ import annotations

import time

from splat.core.vercel_logs import VercelLogStore


class TestVercelLogStoreInit:
    """Test VercelLogStore initialization."""

    def test_init_creates_empty_store(self) -> None:
        """Test that initialization creates an empty store."""
        store = VercelLogStore()
        assert store.has_logs("any_request_id") is False

    def test_init_uses_default_ttl(self) -> None:
        """Test that initialization uses default TTL of 60 seconds."""
        store = VercelLogStore()
        assert store._ttl_seconds == 60

    def test_init_accepts_custom_ttl(self) -> None:
        """Test that initialization accepts custom TTL."""
        store = VercelLogStore(ttl_seconds=120)
        assert store._ttl_seconds == 120


class TestVercelLogStoreAddLogs:
    """Test VercelLogStore add_logs method."""

    def test_add_logs_stores_logs_by_request_id(self) -> None:
        """Test that add_logs stores logs keyed by requestId."""
        store = VercelLogStore()
        logs = [
            {"requestId": "req_123", "message": "Test message", "level": "info"}
        ]

        store.add_logs(logs)

        assert store.has_logs("req_123") is True

    def test_add_logs_groups_multiple_logs_by_request_id(self) -> None:
        """Test that add_logs groups multiple logs with same requestId."""
        store = VercelLogStore()
        logs = [
            {"requestId": "req_123", "message": "Message 1", "level": "info"},
            {"requestId": "req_123", "message": "Message 2", "level": "error"},
        ]

        store.add_logs(logs)

        retrieved = store.get_logs("req_123")
        assert len(retrieved) == 2

    def test_add_logs_separates_different_request_ids(self) -> None:
        """Test that add_logs separates logs with different requestIds."""
        store = VercelLogStore()
        logs = [
            {"requestId": "req_123", "message": "Message A", "level": "info"},
            {"requestId": "req_456", "message": "Message B", "level": "info"},
        ]

        store.add_logs(logs)

        assert len(store.get_logs("req_123")) == 1
        assert len(store.get_logs("req_456")) == 1

    def test_add_logs_skips_entries_without_request_id(self) -> None:
        """Test that add_logs skips entries that don't have requestId."""
        store = VercelLogStore()
        logs = [
            {"requestId": "req_123", "message": "Valid", "level": "info"},
            {"message": "No request ID", "level": "error"},
            {"requestId": "", "message": "Empty request ID", "level": "warn"},
        ]

        store.add_logs(logs)

        # Only one valid entry
        assert store.has_logs("req_123") is True
        assert store.has_logs("") is False

    def test_add_logs_appends_to_existing_logs(self) -> None:
        """Test that add_logs appends to existing logs for same requestId."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "First", "level": "info"}])
        store.add_logs([{"requestId": "req_123", "message": "Second", "level": "info"}])

        retrieved = store.get_logs("req_123")
        assert len(retrieved) == 2

    def test_add_logs_handles_empty_list(self) -> None:
        """Test that add_logs handles empty list gracefully."""
        store = VercelLogStore()
        store.add_logs([])
        # Should not raise


class TestVercelLogStoreGetLogs:
    """Test VercelLogStore get_logs method."""

    def test_get_logs_returns_logs_for_request_id(self) -> None:
        """Test that get_logs returns logs for a given requestId."""
        store = VercelLogStore()
        logs = [{"requestId": "req_123", "message": "Test", "level": "info"}]
        store.add_logs(logs)

        retrieved = store.get_logs("req_123")

        assert len(retrieved) == 1
        assert retrieved[0]["message"] == "Test"

    def test_get_logs_returns_empty_list_for_unknown_request_id(self) -> None:
        """Test that get_logs returns empty list for unknown requestId."""
        store = VercelLogStore()

        retrieved = store.get_logs("unknown_req")

        assert retrieved == []

    def test_get_logs_does_not_remove_logs(self) -> None:
        """Test that get_logs does not remove logs from store."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])

        store.get_logs("req_123")
        retrieved_again = store.get_logs("req_123")

        assert len(retrieved_again) == 1


class TestVercelLogStorePopLogs:
    """Test VercelLogStore pop_logs method."""

    def test_pop_logs_returns_logs_for_request_id(self) -> None:
        """Test that pop_logs returns logs for a given requestId."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])

        retrieved = store.pop_logs("req_123")

        assert len(retrieved) == 1
        assert retrieved[0]["message"] == "Test"

    def test_pop_logs_removes_logs_after_retrieval(self) -> None:
        """Test that pop_logs removes logs after retrieval."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])

        store.pop_logs("req_123")

        assert store.has_logs("req_123") is False
        assert store.get_logs("req_123") == []

    def test_pop_logs_returns_empty_list_for_unknown_request_id(self) -> None:
        """Test that pop_logs returns empty list for unknown requestId."""
        store = VercelLogStore()

        retrieved = store.pop_logs("unknown_req")

        assert retrieved == []


class TestVercelLogStoreHasLogs:
    """Test VercelLogStore has_logs method."""

    def test_has_logs_returns_true_when_logs_exist(self) -> None:
        """Test that has_logs returns True when logs exist for requestId."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])

        assert store.has_logs("req_123") is True

    def test_has_logs_returns_false_when_no_logs(self) -> None:
        """Test that has_logs returns False when no logs exist for requestId."""
        store = VercelLogStore()

        assert store.has_logs("req_123") is False

    def test_has_logs_returns_false_after_pop(self) -> None:
        """Test that has_logs returns False after logs are popped."""
        store = VercelLogStore()
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])
        store.pop_logs("req_123")

        assert store.has_logs("req_123") is False


class TestVercelLogStoreTTL:
    """Test VercelLogStore TTL expiration."""

    def test_expired_entries_are_cleaned_on_add(self) -> None:
        """Test that expired entries are cleaned when add_logs is called."""
        store = VercelLogStore(ttl_seconds=0)  # Immediate expiration
        store.add_logs([{"requestId": "req_old", "message": "Old", "level": "info"}])

        # Wait briefly to ensure expiration
        time.sleep(0.01)

        # Adding new logs should trigger cleanup
        store.add_logs([{"requestId": "req_new", "message": "New", "level": "info"}])

        assert store.has_logs("req_old") is False
        assert store.has_logs("req_new") is True

    def test_non_expired_entries_are_kept(self) -> None:
        """Test that non-expired entries are kept."""
        store = VercelLogStore(ttl_seconds=60)  # Long TTL
        store.add_logs([{"requestId": "req_123", "message": "Test", "level": "info"}])

        # Adding new logs should not remove non-expired entries
        store.add_logs([{"requestId": "req_456", "message": "Test2", "level": "info"}])

        assert store.has_logs("req_123") is True
        assert store.has_logs("req_456") is True


class TestVercelLogStoreFormatLogs:
    """Test VercelLogStore format_logs_as_string method."""

    def test_format_logs_includes_timestamp(self) -> None:
        """Test that formatted logs include timestamp."""
        store = VercelLogStore()
        store.add_logs([{
            "requestId": "req_123",
            "message": "Test message",
            "level": "info",
            "timestamp": 1706200000000,  # Unix timestamp in milliseconds
        }])

        formatted = store.format_logs_as_string("req_123")

        assert "2024-01-25" in formatted  # Date from timestamp

    def test_format_logs_includes_level(self) -> None:
        """Test that formatted logs include log level."""
        store = VercelLogStore()
        store.add_logs([{
            "requestId": "req_123",
            "message": "Test message",
            "level": "error",
            "timestamp": 1706200000000,
        }])

        formatted = store.format_logs_as_string("req_123")

        assert "ERROR" in formatted or "error" in formatted.lower()

    def test_format_logs_includes_message(self) -> None:
        """Test that formatted logs include message."""
        store = VercelLogStore()
        store.add_logs([{
            "requestId": "req_123",
            "message": "Test message content",
            "level": "info",
            "timestamp": 1706200000000,
        }])

        formatted = store.format_logs_as_string("req_123")

        assert "Test message content" in formatted

    def test_format_logs_handles_multiple_logs(self) -> None:
        """Test that formatting works with multiple logs."""
        store = VercelLogStore()
        store.add_logs([
            {
                "requestId": "req_123",
                "message": "First",
                "level": "info",
                "timestamp": 1706200000000,
            },
            {
                "requestId": "req_123",
                "message": "Second",
                "level": "error",
                "timestamp": 1706200001000,
            },
        ])

        formatted = store.format_logs_as_string("req_123")

        assert "First" in formatted
        assert "Second" in formatted
        assert "\n" in formatted

    def test_format_logs_returns_empty_for_unknown_request(self) -> None:
        """Test that format_logs_as_string returns empty string for unknown request."""
        store = VercelLogStore()

        formatted = store.format_logs_as_string("unknown_req")

        assert formatted == ""

    def test_format_logs_handles_missing_timestamp(self) -> None:
        """Test that format handles logs without timestamp."""
        store = VercelLogStore()
        store.add_logs([{
            "requestId": "req_123",
            "message": "No timestamp",
            "level": "info",
        }])

        formatted = store.format_logs_as_string("req_123")

        assert "No timestamp" in formatted

    def test_format_logs_handles_missing_level(self) -> None:
        """Test that format handles logs without level."""
        store = VercelLogStore()
        store.add_logs([{
            "requestId": "req_123",
            "message": "No level",
            "timestamp": 1706200000000,
        }])

        formatted = store.format_logs_as_string("req_123")

        assert "No level" in formatted
