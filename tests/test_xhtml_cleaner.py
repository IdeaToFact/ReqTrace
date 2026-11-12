# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for XHTMLCleaner.
"""

from reqtrace.parsers.xhtml_cleaner import XHTMLCleaner


def test_clean_xhtml_tags_and_entities() -> None:
    raw = """
    <div>
        <p><b>REQ-01:</b> The system shall monitor <i>GPS signal status</i>.</p>
        <p>In case of loss &amp; degradation:</p>
        <ul>
            <li>Trigger alert within &lt;200ms&gt;</li>
            <li>Switch to inertial navigation</li>
        </ul>
    </div>
    """
    cleaned = XHTMLCleaner.clean(raw)
    assert "REQ-01: The system shall monitor GPS signal status." in cleaned
    assert "loss & degradation:" in cleaned
    assert "• Trigger alert within <200ms>" in cleaned
    assert "• Switch to inertial navigation" in cleaned
    assert "<p>" not in cleaned
    assert "<div>" not in cleaned
    assert "<b>" not in cleaned


def test_clean_empty_and_whitespace() -> None:
    assert XHTMLCleaner.clean("") == ""
    assert XHTMLCleaner.clean(None) == ""
    assert XHTMLCleaner.clean("   \n\t  ") == ""
    assert XHTMLCleaner.clean("<p>&nbsp;&nbsp;</p>") == ""

