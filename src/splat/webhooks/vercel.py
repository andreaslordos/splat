"""Vercel webhook signature verification and log parsing."""

import hashlib
import hmac
import json
from typing import Any


def verify_signature(body: bytes, secret: str, signature: str | None) -> bool:
    """
    Verify Vercel webhook signature using HMAC SHA1.

    Args:
        body: The raw request body as bytes.
        secret: The webhook secret configured in Vercel.
        signature: The signature from the x-vercel-signature header.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature:
        return False

    expected_signature = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def parse_logs(body: bytes, filter_sources: bool = True) -> list[dict[str, Any]]:
    """
    Parse Vercel log drain webhook body.

    Supports:
    - JSON array format
    - NDJSON (newline-delimited JSON) format
    - Single JSON object

    Args:
        body: The raw request body as bytes.
        filter_sources: If True, only return logs where source is "lambda" or "edge".
                       Defaults to True.

    Returns:
        List of log dictionaries. Returns empty list for invalid/empty body.
    """
    if not body or not body.strip():
        return []

    decoded = body.decode("utf-8").strip()

    logs: list[dict[str, Any]] = []

    try:
        # Try parsing as JSON (array or single object)
        parsed = json.loads(decoded)

        if isinstance(parsed, list):
            logs = parsed
        elif isinstance(parsed, dict):
            logs = [parsed]
        else:
            return []

    except json.JSONDecodeError:
        # Try parsing as NDJSON (newline-delimited JSON)
        try:
            for line in decoded.split("\n"):
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
        except json.JSONDecodeError:
            return []

    if filter_sources:
        logs = [log for log in logs if log.get("source") in ("lambda", "edge")]

    return logs
