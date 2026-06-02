"""Tests for pdf_export.py — output dir and HTML rendering."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import pdf_export
from calculator import LineItem, PricingResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_result() -> PricingResult:
    r = PricingResult(currency="ILS", hourly_rate=350.0)
    r.client_name = "Test Client"
    r.project_type_label = "Brochure / Portfolio (3-8 pages)"
    r.line_items = [
        LineItem(label="Base development", hours=40, cost=14000),
        LineItem(label="CMS setup — WordPress", hours=12, cost=4200),
    ]
    r.base_hours = 52.0
    r.subtotal_before_multipliers = 18200.0
    r.pre_vat_total = 29661.0
    r.vat_pct = 0.18
    r.vat_amount = 5338.98
    r.final_total = 34999.98
    r.final_total_ils = 34999.98
    r.final_total_usd = 9333.0
    r.rush_surcharge_pct = 0.0
    r.risk_buffer_pct = 0.15
    r.overhead_pct = 0.15
    r.profit_margin_pct = 0.25
    r.payment_schedule = "50% upfront / 50% on delivery"
    return r


# ---------------------------------------------------------------------------
# _format_number()
# ---------------------------------------------------------------------------

class TestFormatNumber:
    def test_integer_with_thousands(self):
        assert pdf_export._format_number(12500) == "12,500"

    def test_zero(self):
        assert pdf_export._format_number(0) == "0"

    def test_float_truncated(self):
        assert pdf_export._format_number(9999.99) == "9,999"

    def test_large_number(self):
        assert pdf_export._format_number(1_000_000) == "1,000,000"

    def test_invalid_returns_string(self):
        assert pdf_export._format_number("bad") == "bad"


# ---------------------------------------------------------------------------
# get_output_dir()
# ---------------------------------------------------------------------------

class TestGetOutputDir:
    def test_creates_directory(self, tmp_path):
        with patch.object(pdf_export, "Path") as _:
            # Use the real function but redirect outputs/ to tmp_path
            pass

        # Call directly and check the real path is created
        out = pdf_export.get_output_dir("Test Client")
        assert out.exists()
        assert out.is_dir()

    def test_directory_name_contains_slug(self):
        out = pdf_export.get_output_dir("Roni's Bakery!!")
        assert "roni" in out.name
        assert "bakery" in out.name

    def test_directory_name_contains_today(self):
        out = pdf_export.get_output_dir("Test Co")
        assert date.today().strftime("%Y%m%d") in out.name

    def test_special_chars_stripped_from_name(self):
        out = pdf_export.get_output_dir("A & B / C")
        # Only alphanumeric and underscores in slug
        slug_part = out.name.split("_202")[0]
        assert all(c.isalnum() or c == "_" for c in slug_part)

    def test_empty_name_defaults_to_client(self):
        out = pdf_export.get_output_dir("")
        assert out.name.startswith("client_")


# ---------------------------------------------------------------------------
# render_html()
# ---------------------------------------------------------------------------

class TestRenderHtml:
    def test_returns_string(self, sample_result):
        html = pdf_export.render_html(sample_result, language="en")
        assert isinstance(html, str)

    def test_html_non_empty(self, sample_result):
        html = pdf_export.render_html(sample_result, language="en")
        assert len(html) > 100

    def test_client_name_in_html(self, sample_result):
        html = pdf_export.render_html(sample_result, language="en")
        assert "Test Client" in html

    def test_hebrew_template_uses_rtl(self, sample_result):
        html = pdf_export.render_html(sample_result, language="he")
        assert 'dir="rtl"' in html or "direction: rtl" in html

    def test_english_template_has_no_rtl(self, sample_result):
        html = pdf_export.render_html(sample_result, language="en")
        assert 'dir="rtl"' not in html

    def test_currency_symbol_present(self, sample_result):
        html = pdf_export.render_html(sample_result, language="en")
        assert "₪" in html
