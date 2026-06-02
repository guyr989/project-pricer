"""Tests for non-interactive helpers in main.py."""
from __future__ import annotations

from pathlib import Path

import pytest
import main
from main import (
    QUICK_DEFAULTS,
    QUICK_PAGE_COUNT,
    generate_client_questions_doc,
    should_ask,
)


# ---------------------------------------------------------------------------
# should_ask()
# ---------------------------------------------------------------------------

class TestShouldAsk:
    def test_no_condition_always_true(self):
        q = {"condition": None}
        assert should_ask(q, {}) is True

    def test_missing_condition_key_always_true(self):
        assert should_ask({}, {}) is True

    def test_bool_condition_true_when_matches(self):
        q = {"condition": {"question_id": "has_video", "value": True}}
        assert should_ask(q, {"has_video": True}) is True

    def test_bool_condition_false_when_no_match(self):
        q = {"condition": {"question_id": "has_video", "value": True}}
        assert should_ask(q, {"has_video": False}) is False

    def test_bool_condition_missing_parent_is_false(self):
        q = {"condition": {"question_id": "has_video", "value": True}}
        assert should_ask(q, {}) is False

    def test_string_yes_treated_as_true(self):
        q = {"condition": {"question_id": "cms_required", "value": True}}
        assert should_ask(q, {"cms_required": "yes"}) is True

    def test_string_no_treated_as_false(self):
        q = {"condition": {"question_id": "cms_required", "value": True}}
        assert should_ask(q, {"cms_required": "no"}) is False

    def test_string_value_condition_matches(self):
        q = {"condition": {"question_id": "cms_type", "value": "wordpress"}}
        assert should_ask(q, {"cms_type": "wordpress"}) is True

    def test_string_value_condition_no_match(self):
        q = {"condition": {"question_id": "cms_type", "value": "wordpress"}}
        assert should_ask(q, {"cms_type": "custom"}) is False


# ---------------------------------------------------------------------------
# QUICK_DEFAULTS
# ---------------------------------------------------------------------------

class TestQuickDefaults:
    def test_is_dict(self):
        assert isinstance(QUICK_DEFAULTS, dict)

    def test_has_expected_keys(self):
        required = {
            "is_redesign", "design_source", "animations_level", "revision_rounds",
            "content_writer", "content_ready", "image_source", "image_count",
            "has_video", "cms_required", "cms_type", "contact_form",
            "blog_section", "ecommerce_required", "booking_system",
            "third_party_integrations", "multilingual", "language_count",
            "seo_setup", "hosting_managed", "ssl_setup", "payment_terms",
            "maintenance_retainer", "ip_transfer", "vat_applicable",
        }
        assert required.issubset(QUICK_DEFAULTS.keys())

    def test_is_redesign_defaults_false(self):
        assert QUICK_DEFAULTS["is_redesign"] is False

    def test_has_video_defaults_false(self):
        assert QUICK_DEFAULTS["has_video"] is False

    def test_multilingual_defaults_false(self):
        assert QUICK_DEFAULTS["multilingual"] is False

    def test_integrations_defaults_to_empty_list(self):
        assert QUICK_DEFAULTS["third_party_integrations"] == []


# ---------------------------------------------------------------------------
# QUICK_PAGE_COUNT
# ---------------------------------------------------------------------------

class TestQuickPageCount:
    def test_covers_all_project_types(self):
        expected_types = {
            "landing_page", "brochure", "business", "ecommerce",
            "blog_magazine", "web_app", "directory",
        }
        assert expected_types == set(QUICK_PAGE_COUNT.keys())

    def test_landing_page_is_one(self):
        assert QUICK_PAGE_COUNT["landing_page"] == 1

    def test_all_values_positive(self):
        assert all(v > 0 for v in QUICK_PAGE_COUNT.values())

    def test_landing_page_smallest(self):
        assert QUICK_PAGE_COUNT["landing_page"] == min(QUICK_PAGE_COUNT.values())


# ---------------------------------------------------------------------------
# generate_client_questions_doc()
# ---------------------------------------------------------------------------

class TestGenerateClientQuestionsDoc:
    def test_returns_none_for_empty_idk(self, tmp_path):
        result = generate_client_questions_doc({}, "Test", tmp_path)
        assert result is None

    def test_creates_file(self, tmp_path):
        idk = {"project_type": "What kind of website?"}
        path = generate_client_questions_doc(idk, "Roni", tmp_path)
        assert path is not None
        assert path.exists()

    def test_file_named_client_questions(self, tmp_path):
        idk = {"q1": "Some question"}
        path = generate_client_questions_doc(idk, "Test", tmp_path)
        assert path.name == "client_questions.txt"

    def test_client_name_in_file(self, tmp_path):
        idk = {"q1": "Question A"}
        path = generate_client_questions_doc(idk, "Roni Bakery", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "Roni Bakery" in content

    def test_all_questions_listed(self, tmp_path):
        idk = {
            "project_type": "What kind of website?",
            "deadline": "What is the deadline?",
            "has_video": "Will there be video content?",
        }
        path = generate_client_questions_doc(idk, "Test", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "What kind of website?" in content
        assert "What is the deadline?" in content
        assert "Will there be video content?" in content

    def test_numbered_list(self, tmp_path):
        idk = {"a": "Q1", "b": "Q2", "c": "Q3"}
        path = generate_client_questions_doc(idk, "X", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert " 1." in content
        assert " 2." in content
        assert " 3." in content

    def test_empty_client_name_fallback(self, tmp_path):
        idk = {"q": "Some question"}
        path = generate_client_questions_doc(idk, "", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "client" in content
