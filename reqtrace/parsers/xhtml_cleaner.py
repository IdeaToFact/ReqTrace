# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
XHTML and HTML sanitizer for ReqIF.Text attributes.
Strips presentation tags, converts line breaks, unescapes XML entities,
and normalizes whitespace so markup does not distort semantic embeddings.
"""

import html
import re
from typing import Optional


class XHTMLCleaner:
    # Regex to match XML/HTML tags
    _TAG_RE = re.compile(r"<[^>]+>")
    # Regex to match multiple whitespace/newlines
    _WHITESPACE_RE = re.compile(r"[ \t]+")
    _MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

    @classmethod
    def clean(cls, text: Optional[str], normalize_whitespace: bool = True) -> str:
        """
        Cleans an XHTML fragment into plain textual requirement content.
        Handles nested tags, <br/>, <p>, <li> elements, and HTML entities.
        """
        if not text:
            return ""

        raw = text.strip()
        if not raw:
            return ""

        # Replace block breaks with newlines
        processed = re.sub(r"<\s*/?\s*(?:p|div|tr|h[1-6])\b[^>]*>", "\n", raw, flags=re.IGNORECASE)
        processed = re.sub(r"<\s*br\s*/?>", "\n", processed, flags=re.IGNORECASE)
        processed = re.sub(r"<\s*li\b[^>]*>", "\n• ", processed, flags=re.IGNORECASE)

        # Inline tags can be removed directly without extra spaces
        processed = re.sub(r"<\s*/?\s*(?:b|i|u|em|strong|span|small|mark|sub|sup)\b[^>]*>", "", processed, flags=re.IGNORECASE)

        # Remove all remaining HTML/XML tags with space
        clean_text = cls._TAG_RE.sub(" ", processed)

        # Fix spaces before punctuation (e.g. "word ." -> "word.")
        clean_text = re.sub(r"\s+([.,;:!?])", r"\1", clean_text)

        # Unescape standard HTML / XML entities (&amp;, &lt;, &gt;, &quot;, &#39;, &nbsp;)
        clean_text = html.unescape(clean_text)
        # Replace non-breaking spaces
        clean_text = clean_text.replace("\xa0", " ")

        if normalize_whitespace:
            lines = [cls._WHITESPACE_RE.sub(" ", line).strip() for line in clean_text.splitlines()]
            clean_text = "\n".join(line for line in lines if line)
            clean_text = cls._MULTI_NEWLINE_RE.sub("\n\n", clean_text)

        return clean_text.strip()
