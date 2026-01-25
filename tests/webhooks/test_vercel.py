"""Tests for Vercel webhook signature verification and log parsing."""

import hmac
import hashlib
import json

import pytest

from splat.webhooks.vercel import verify_signature, parse_logs


class TestVerifySignature:
    """Test Vercel webhook signature verification."""

    def test_valid_signature_returns_true(self) -> None:
        """Test that a valid HMAC SHA1 signature is accepted."""
        body = b'{"test": "data"}'
        secret = "test_secret"
        # Generate valid signature
        expected_sig = hmac.new(
            secret.encode(), body, hashlib.sha1
        ).hexdigest()

        result = verify_signature(body, secret, expected_sig)

        assert result is True

    def test_invalid_signature_returns_false(self) -> None:
        """Test that an invalid signature is rejected."""
        body = b'{"test": "data"}'
        secret = "test_secret"
        invalid_sig = "invalid_signature_here"

        result = verify_signature(body, secret, invalid_sig)

        assert result is False

    def test_none_signature_returns_false(self) -> None:
        """Test that None signature returns False."""
        body = b'{"test": "data"}'
        secret = "test_secret"

        result = verify_signature(body, secret, None)

        assert result is False

    def test_empty_signature_returns_false(self) -> None:
        """Test that empty string signature returns False."""
        body = b'{"test": "data"}'
        secret = "test_secret"

        result = verify_signature(body, secret, "")

        assert result is False

    def test_different_body_produces_different_signature(self) -> None:
        """Test that different bodies produce different valid signatures."""
        body1 = b'{"test": "data1"}'
        body2 = b'{"test": "data2"}'
        secret = "test_secret"

        sig1 = hmac.new(secret.encode(), body1, hashlib.sha1).hexdigest()
        sig2 = hmac.new(secret.encode(), body2, hashlib.sha1).hexdigest()

        # sig1 is valid for body1
        assert verify_signature(body1, secret, sig1) is True
        # sig1 is NOT valid for body2
        assert verify_signature(body2, secret, sig1) is False
        # sig2 is valid for body2
        assert verify_signature(body2, secret, sig2) is True

    def test_different_secret_produces_different_signature(self) -> None:
        """Test that different secrets produce different valid signatures."""
        body = b'{"test": "data"}'
        secret1 = "secret1"
        secret2 = "secret2"

        sig1 = hmac.new(secret1.encode(), body, hashlib.sha1).hexdigest()

        # sig1 is valid for secret1
        assert verify_signature(body, secret1, sig1) is True
        # sig1 is NOT valid for secret2
        assert verify_signature(body, secret2, sig1) is False

    def test_timing_safe_comparison(self) -> None:
        """Test that signature comparison is timing-safe (uses hmac.compare_digest)."""
        # This test verifies the behavior rather than the implementation.
        # If the comparison is timing-safe, it should still work correctly.
        body = b'{"test": "data"}'
        secret = "test_secret"
        valid_sig = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

        # Valid signature should pass
        assert verify_signature(body, secret, valid_sig) is True

        # Signature with one character different should fail
        # Change last character
        wrong_sig = valid_sig[:-1] + ("0" if valid_sig[-1] != "0" else "1")
        assert verify_signature(body, secret, wrong_sig) is False


class TestParseLogs:
    """Test Vercel log parsing."""

    def test_parse_json_array(self) -> None:
        """Test parsing JSON array format."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "edge"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body)

        assert len(result) == 2
        assert result[0]["message"] == "log1"
        assert result[1]["message"] == "log2"

    def test_parse_ndjson(self) -> None:
        """Test parsing NDJSON (newline-delimited JSON) format."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "edge"},
        ]
        body = "\n".join(json.dumps(log) for log in logs).encode()

        result = parse_logs(body)

        assert len(result) == 2
        assert result[0]["message"] == "log1"
        assert result[1]["message"] == "log2"

    def test_parse_single_json_object(self) -> None:
        """Test parsing single JSON object."""
        log = {"message": "single log", "source": "lambda"}
        body = json.dumps(log).encode()

        result = parse_logs(body)

        assert len(result) == 1
        assert result[0]["message"] == "single log"

    def test_empty_body_returns_empty_list(self) -> None:
        """Test that empty body returns empty list."""
        result = parse_logs(b"")

        assert result == []

    def test_invalid_json_returns_empty_list(self) -> None:
        """Test that invalid JSON returns empty list."""
        body = b"not valid json {"

        result = parse_logs(body)

        assert result == []

    def test_whitespace_only_body_returns_empty_list(self) -> None:
        """Test that whitespace-only body returns empty list."""
        result = parse_logs(b"   \n\t  ")

        assert result == []

    def test_filter_sources_lambda(self) -> None:
        """Test filtering keeps logs with source='lambda'."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "build"},
            {"message": "log3", "source": "static"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=True)

        assert len(result) == 1
        assert result[0]["source"] == "lambda"

    def test_filter_sources_edge(self) -> None:
        """Test filtering keeps logs with source='edge'."""
        logs = [
            {"message": "log1", "source": "edge"},
            {"message": "log2", "source": "build"},
            {"message": "log3", "source": "static"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=True)

        assert len(result) == 1
        assert result[0]["source"] == "edge"

    def test_filter_sources_lambda_and_edge(self) -> None:
        """Test filtering keeps both lambda and edge sources."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "edge"},
            {"message": "log3", "source": "build"},
            {"message": "log4", "source": "static"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=True)

        assert len(result) == 2
        sources = {log["source"] for log in result}
        assert sources == {"lambda", "edge"}

    def test_filter_sources_false_returns_all(self) -> None:
        """Test filter_sources=False returns all logs."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "build"},
            {"message": "log3", "source": "static"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=False)

        assert len(result) == 3

    def test_filter_sources_default_is_true(self) -> None:
        """Test that filter_sources defaults to True."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "build"},
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body)  # No filter_sources argument

        assert len(result) == 1
        assert result[0]["source"] == "lambda"

    def test_logs_without_source_filtered_out(self) -> None:
        """Test that logs without 'source' field are filtered out when filtering."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2"},  # No source field
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=True)

        assert len(result) == 1
        assert result[0]["source"] == "lambda"

    def test_logs_without_source_kept_when_not_filtering(self) -> None:
        """Test that logs without 'source' field are kept when not filtering."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2"},  # No source field
        ]
        body = json.dumps(logs).encode()

        result = parse_logs(body, filter_sources=False)

        assert len(result) == 2

    def test_ndjson_with_empty_lines(self) -> None:
        """Test NDJSON parsing handles empty lines."""
        logs = [
            {"message": "log1", "source": "lambda"},
            {"message": "log2", "source": "edge"},
        ]
        # NDJSON with empty lines
        body = (
            json.dumps(logs[0]) + "\n\n" + json.dumps(logs[1]) + "\n"
        ).encode()

        result = parse_logs(body, filter_sources=False)

        assert len(result) == 2

    def test_ndjson_with_trailing_newline(self) -> None:
        """Test NDJSON parsing handles trailing newline."""
        log = {"message": "log1", "source": "lambda"}
        body = (json.dumps(log) + "\n").encode()

        result = parse_logs(body)

        assert len(result) == 1

    def test_mixed_valid_invalid_ndjson_lines(self) -> None:
        """Test NDJSON with some invalid lines returns empty list."""
        # If any line is invalid JSON, the whole parsing should handle gracefully
        body = b'{"message": "valid", "source": "lambda"}\nnot json\n'

        # The function should return empty list on invalid body
        result = parse_logs(body)

        # Based on requirements, invalid JSON returns empty list
        assert result == []

    def test_json_primitive_returns_empty_list(self) -> None:
        """Test that JSON primitives (not objects/arrays) return empty list."""
        # JSON string
        result = parse_logs(b'"just a string"')
        assert result == []

        # JSON number
        result = parse_logs(b'123')
        assert result == []

        # JSON boolean
        result = parse_logs(b'true')
        assert result == []

        # JSON null
        result = parse_logs(b'null')
        assert result == []
