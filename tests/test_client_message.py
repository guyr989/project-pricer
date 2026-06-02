"""Tests for client_message module."""
from __future__ import annotations

from pathlib import Path

import pytest

from client_message import (
    WEIGHT_ORDER,
    MessageOptions,
    generate_client_message,
    sort_by_weight,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _q(id_: str, label: str, label_he: str, weight: str = "medium",
       category: str = "scope", internal_only: bool = False) -> dict:
    return {
        "id": id_,
        "label": label,
        "label_he": label_he,
        "weight": weight,
        "category": category,
        "internal_only": internal_only,
    }


@pytest.fixture
def sample_idk():
    """3 IDK questions of different weights."""
    return {
        "deadline": _q("deadline", "What is the deadline?", "מה הדדליין?", "high"),
        "project_type": _q("project_type", "What type of website?", "מה סוג האתר?", "critical"),
        "has_video": _q("has_video", "Will there be video?", "האם יהיה וידאו?", "low"),
    }


@pytest.fixture
def large_idk():
    """7 IDK questions to test overflow (>5)."""
    return {
        "q1": _q("q1", "Question 1", "שאלה 1", "critical"),
        "q2": _q("q2", "Question 2", "שאלה 2", "critical"),
        "q3": _q("q3", "Question 3", "שאלה 3", "high"),
        "q4": _q("q4", "Question 4", "שאלה 4", "high"),
        "q5": _q("q5", "Question 5", "שאלה 5", "medium"),
        "q6": _q("q6", "Question 6", "שאלה 6", "medium"),
        "q7": _q("q7", "Question 7", "שאלה 7", "low"),
    }


# ── sort_by_weight ────────────────────────────────────────────────────

class TestSortByWeight:
    def test_critical_before_low(self, sample_idk):
        result = sort_by_weight(sample_idk)
        weights = [q["weight"] for q in result]
        assert weights == ["critical", "high", "low"]

    def test_excludes_internal_only(self):
        idk = {
            "rate": _q("rate", "Hourly rate?", "תעריף?", "critical", internal_only=True),
            "deadline": _q("deadline", "Deadline?", "דדליין?", "high"),
        }
        result = sort_by_weight(idk)
        assert len(result) == 1
        assert result[0]["id"] == "deadline"

    def test_empty_dict(self):
        assert sort_by_weight({}) == []

    def test_stable_within_same_weight(self):
        idk = {
            "a": _q("a", "A?", "א?", "high"),
            "b": _q("b", "B?", "ב?", "high"),
            "c": _q("c", "C?", "ג?", "high"),
        }
        result = sort_by_weight(idk)
        assert [q["id"] for q in result] == ["a", "b", "c"]


# ── generate_client_message — all 8 combos ───────────────────────────

_ALL_COMBOS = [
    ("en", "formal", "email"),
    ("en", "formal", "sms"),
    ("en", "casual", "email"),
    ("en", "casual", "sms"),
    ("he", "formal", "email"),
    ("he", "formal", "sms"),
    ("he", "casual", "email"),
    ("he", "casual", "sms"),
]


class TestGenerateClientMessage:
    @pytest.mark.parametrize("lang,tone,fmt", _ALL_COMBOS)
    def test_all_combos_produce_output(self, sample_idk, lang, tone, fmt):
        opts = MessageOptions(language=lang, tone=tone, format=fmt, client_name="Roni")
        msg = generate_client_message(sample_idk, opts)
        assert len(msg) > 0

    def test_empty_idk_returns_empty(self):
        msg = generate_client_message({})
        assert msg == ""

    def test_all_internal_returns_empty(self):
        idk = {"r": _q("r", "Rate?", "תעריף?", "high", internal_only=True)}
        msg = generate_client_message(idk)
        assert msg == ""

    def test_client_name_in_email(self, sample_idk):
        opts = MessageOptions(language="en", tone="formal", format="email", client_name="Roni")
        msg = generate_client_message(sample_idk, opts)
        assert "Roni" in msg

    def test_no_greeting_in_sms(self, sample_idk):
        opts = MessageOptions(language="en", tone="formal", format="sms", client_name="Roni")
        msg = generate_client_message(sample_idk, opts)
        assert "Dear" not in msg

    def test_hebrew_uses_label_he(self, sample_idk):
        opts = MessageOptions(language="he", tone="formal", format="email", client_name="רוני")
        msg = generate_client_message(sample_idk, opts)
        assert "מה סוג האתר?" in msg
        assert "What type of website?" not in msg

    def test_english_uses_label(self, sample_idk):
        opts = MessageOptions(language="en", tone="casual", format="email", client_name="Roni")
        msg = generate_client_message(sample_idk, opts)
        assert "What type of website?" in msg

    def test_weight_ordering_in_output(self, sample_idk):
        opts = MessageOptions(language="en", tone="formal", format="email")
        msg = generate_client_message(sample_idk, opts)
        pos_critical = msg.index("What type of website?")
        pos_low = msg.index("Will there be video?")
        assert pos_critical < pos_low

    # ── Overflow (>5 questions) ───────────────────────────────────────

    def test_overflow_splits_correctly(self, large_idk):
        opts = MessageOptions(language="en", tone="formal", format="email", max_primary=5)
        msg = generate_client_message(large_idk, opts)
        # Top 5 are numbered
        assert "1." in msg
        assert "5." in msg
        # Overflow uses bullet
        assert "•" in msg
        # Overflow header present
        assert "later" in msg.lower() or "discuss" in msg.lower()

    def test_exactly_5_no_overflow(self):
        idk = {f"q{i}": _q(f"q{i}", f"Q{i}?", f"ש{i}?", "medium") for i in range(5)}
        opts = MessageOptions(language="en", tone="formal", format="email", max_primary=5)
        msg = generate_client_message(idk, opts)
        assert "•" not in msg

    def test_less_than_5_no_overflow(self, sample_idk):
        opts = MessageOptions(language="en", tone="formal", format="email")
        msg = generate_client_message(sample_idk, opts)
        assert "•" not in msg

    # ── File output ───────────────────────────────────────────────────

    def test_writes_to_file(self, sample_idk, tmp_path):
        out = tmp_path / "msg.txt"
        msg = generate_client_message(sample_idk, MessageOptions(), out)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == msg

    def test_returns_string_without_file(self, sample_idk):
        msg = generate_client_message(sample_idk, MessageOptions())
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_sender_name_in_signoff(self, sample_idk):
        opts = MessageOptions(language="en", tone="formal", format="email", sender_name="Guy")
        msg = generate_client_message(sample_idk, opts)
        assert "Guy" in msg

    def test_sms_format_uses_dashes(self, sample_idk):
        opts = MessageOptions(language="en", tone="casual", format="sms")
        msg = generate_client_message(sample_idk, opts)
        assert "- " in msg
