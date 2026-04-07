"""Cookie parsing for SAP authentication.

Supports Netscape-format cookie files and cookie strings.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("vsp.adt.cookies")


def parse_cookie_file(path: str) -> dict[str, str]:
    """Parse a Netscape-format cookie file.

    Format: domain\\tinclude_subdomains\\tpath\\tsecure\\texpires\\tname\\tvalue
    Lines starting with # are comments. Empty lines are skipped.

    Args:
        path: Path to the cookie file.

    Returns:
        Dictionary of cookie name → value pairs.
    """
    cookies: dict[str, str] = {}
    file_path = Path(path)

    if not file_path.exists():
        logger.warning("Cookie file not found: %s", path)
        return cookies

    with file_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Netscape format: tab-separated, 7 fields
            parts = line.split("\t")
            if len(parts) < 7:
                logger.debug("Skipping malformed cookie line %d: expected 7 fields, got %d", line_no, len(parts))
                continue

            name = parts[5]
            value = parts[6]
            if name:
                cookies[name] = value

    logger.debug("Loaded %d cookies from %s", len(cookies), path)
    return cookies


def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """Parse a cookie string in the format 'key1=val1; key2=val2'.

    Args:
        cookie_string: Semicolon-separated cookie key=value pairs.

    Returns:
        Dictionary of cookie name → value pairs.
    """
    cookies: dict[str, str] = {}

    if not cookie_string:
        return cookies

    for pair in cookie_string.split(";"):
        pair = pair.strip()
        if not pair:
            continue

        if "=" in pair:
            name, _, value = pair.partition("=")
            name = name.strip()
            value = value.strip()
            if name:
                cookies[name] = value
        else:
            logger.debug("Skipping malformed cookie pair: %s", pair)

    logger.debug("Parsed %d cookies from string", len(cookies))
    return cookies
