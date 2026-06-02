"""Tests for calculator.py — pricing engine."""
from __future__ import annotations

import pytest
import calculator
from calculator import LineItem, PricingResult, calculate, recompute_totals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(line_costs: list[float], rush=0.0, risk=0.15, overhead=0.15, profit=0.25) -> PricingResult:
    """Build a minimal PricingResult with given line costs and multipliers."""
    r = PricingResult(currency="ILS", hourly_rate=350.0)
    r.line_items = [LineItem(label=f"item{i}", hours=0, cost=c) for i, c in enumerate(line_costs)]
    r.rush_surcharge_pct = rush
    r.risk_buffer_pct = risk
    r.overhead_pct = overhead
    r.profit_margin_pct = profit
    return r


# ---------------------------------------------------------------------------
# calculate() — end-to-end
# ---------------------------------------------------------------------------

class TestCalculateBasic:
    def test_returns_pricing_result(self, questions, minimal_answers):
        result = calculate(minimal_answers, questions)
        assert isinstance(result, PricingResult)

    def test_client_name_propagated(self, questions, minimal_answers):
        minimal_answers["client_name"] = "Roni Bakery"
        result = calculate(minimal_answers, questions)
        assert result.client_name == "Roni Bakery"

    def test_currency_propagated(self, questions, minimal_answers):
        minimal_answers["currency"] = "ILS"
        result = calculate(minimal_answers, questions)
        assert result.currency == "ILS"

    def test_final_total_positive(self, questions, minimal_answers):
        result = calculate(minimal_answers, questions)
        assert result.final_total > 0

    def test_final_total_ils_equals_final_total_for_ils_currency(self, questions, minimal_answers):
        result = calculate(minimal_answers, questions)
        assert result.final_total_ils == pytest.approx(result.final_total)

    def test_final_total_usd_less_than_ils(self, questions, minimal_answers):
        """USD total should be lower than ILS total at current FX rates."""
        result = calculate(minimal_answers, questions)
        assert result.final_total_usd < result.final_total_ils

    def test_has_line_items(self, questions, minimal_answers):
        result = calculate(minimal_answers, questions)
        assert len(result.line_items) > 0

    def test_base_hours_positive(self, questions, minimal_answers):
        result = calculate(minimal_answers, questions)
        assert result.base_hours > 0


class TestCalculateProjectTypes:
    def test_landing_page_cheaper_than_ecommerce(self, questions, minimal_answers):
        minimal_answers["project_type"] = "landing_page"
        minimal_answers["page_count"] = 1
        minimal_answers["cms_required"] = False
        r_landing = calculate(dict(minimal_answers), questions)

        minimal_answers["project_type"] = "ecommerce"
        minimal_answers["page_count"] = 20
        minimal_answers["cms_required"] = True
        r_ecommerce = calculate(dict(minimal_answers), questions)

        assert r_landing.final_total < r_ecommerce.final_total

    def test_extra_pages_add_cost(self, questions, minimal_answers):
        minimal_answers["page_count"] = 5
        r_few = calculate(dict(minimal_answers), questions)

        minimal_answers["page_count"] = 20
        r_many = calculate(dict(minimal_answers), questions)

        assert r_many.final_total > r_few.final_total

    def test_redesign_adds_cost(self, questions, minimal_answers):
        r_no = calculate(dict(minimal_answers), questions)

        minimal_answers["is_redesign"] = True
        r_yes = calculate(dict(minimal_answers), questions)

        assert r_yes.final_total > r_no.final_total


class TestCalculateMultipliers:
    def test_rush_asap_increases_total(self, questions, minimal_answers):
        r_no_rush = calculate(dict(minimal_answers), questions)

        minimal_answers["deadline"] = "asap"
        r_rush = calculate(dict(minimal_answers), questions)

        assert r_rush.final_total > r_no_rush.final_total

    def test_rush_surcharge_pct_set_for_asap(self, questions, minimal_answers):
        minimal_answers["deadline"] = "asap"
        result = calculate(minimal_answers, questions)
        assert result.rush_surcharge_pct > 0

    def test_no_rush_surcharge_for_no_rush(self, questions, minimal_answers):
        minimal_answers["deadline"] = "no_rush"
        result = calculate(minimal_answers, questions)
        assert result.rush_surcharge_pct == 0.0

    def test_high_risk_more_expensive_than_low(self, questions, minimal_answers):
        minimal_answers["project_risk"] = "low"
        r_low = calculate(dict(minimal_answers), questions)

        minimal_answers["project_risk"] = "very_high"
        r_high = calculate(dict(minimal_answers), questions)

        assert r_high.final_total > r_low.final_total

    def test_multilingual_two_languages_costs_more(self, questions, minimal_answers):
        r_mono = calculate(dict(minimal_answers), questions)

        minimal_answers["multilingual"] = True
        minimal_answers["language_count"] = 2
        r_bi = calculate(dict(minimal_answers), questions)

        assert r_bi.final_total > r_mono.final_total

    def test_long_term_discount_reduces_total(self, questions, minimal_answers):
        r_no = calculate(dict(minimal_answers), questions)

        minimal_answers["long_term_client"] = True
        r_yes = calculate(dict(minimal_answers), questions)

        assert r_yes.final_total < r_no.final_total


class TestCalculateVAT:
    def test_israel_vat_applied(self, questions, minimal_answers):
        minimal_answers["vat_applicable"] = "israel"
        result = calculate(minimal_answers, questions)
        assert result.vat_pct == pytest.approx(0.18)
        assert result.vat_amount > 0

    def test_no_vat_zero_vat_amount(self, questions, minimal_answers):
        minimal_answers["vat_applicable"] = "none"
        result = calculate(minimal_answers, questions)
        assert result.vat_pct == 0.0
        assert result.vat_amount == 0.0

    def test_vat_adds_to_pre_vat_total(self, questions, minimal_answers):
        minimal_answers["vat_applicable"] = "israel"
        result = calculate(minimal_answers, questions)
        assert result.final_total == pytest.approx(result.pre_vat_total + result.vat_amount)


class TestCalculateCMS:
    def test_cms_required_adds_line_item(self, questions, minimal_answers):
        minimal_answers["cms_required"] = True
        result = calculate(minimal_answers, questions)
        labels = [li.label for li in result.line_items]
        assert any("CMS" in l for l in labels)

    def test_no_cms_no_cms_line_item(self, questions, minimal_answers):
        minimal_answers["cms_required"] = False
        result = calculate(minimal_answers, questions)
        labels = [li.label for li in result.line_items]
        assert not any("CMS" in l for l in labels)


class TestCalculateDesign:
    def test_developer_designs_adds_hours(self, questions, minimal_answers):
        minimal_answers["design_source"] = "client_mockups"
        r_no = calculate(dict(minimal_answers), questions)

        minimal_answers["design_source"] = "developer_designs"
        r_yes = calculate(dict(minimal_answers), questions)

        assert r_yes.base_hours > r_no.base_hours

    def test_no_brand_adds_branding_hours(self, questions, minimal_answers):
        minimal_answers["has_brand_identity"] = "full_brand"
        r_has = calculate(dict(minimal_answers), questions)

        minimal_answers["has_brand_identity"] = "no_brand"
        r_none = calculate(dict(minimal_answers), questions)

        assert r_none.base_hours > r_has.base_hours


class TestCalculateHourlyRate:
    def test_higher_rate_increases_total(self, questions, minimal_answers):
        minimal_answers["dev_hourly_rate"] = 200
        r_low = calculate(dict(minimal_answers), questions)

        minimal_answers["dev_hourly_rate"] = 600
        r_high = calculate(dict(minimal_answers), questions)

        assert r_high.final_total > r_low.final_total

    def test_non_numeric_rate_falls_back_to_default(self, questions, minimal_answers):
        minimal_answers["dev_hourly_rate"] = "not_a_number"
        result = calculate(minimal_answers, questions)
        assert result.hourly_rate == pytest.approx(350.0)

    def test_zero_rate_accepted_as_zero(self, questions, minimal_answers):
        minimal_answers["dev_hourly_rate"] = 0
        result = calculate(minimal_answers, questions)
        assert result.hourly_rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# recompute_totals()
# ---------------------------------------------------------------------------

class TestRecomputeTotals:
    def test_recalculates_after_cost_change(self):
        r = _make_result([1000, 2000])
        original_total = r.final_total

        # Modify a line item
        r.line_items[0].cost = 3000
        r = recompute_totals(r)

        assert r.final_total != original_total
        assert r.subtotal_before_multipliers == pytest.approx(5000.0)

    def test_subtotal_sums_line_items(self):
        r = _make_result([500, 1500, 2000])
        r = recompute_totals(r)
        assert r.subtotal_before_multipliers == pytest.approx(4000.0)

    def test_no_line_items_gives_zero_total(self):
        r = _make_result([])
        r = recompute_totals(r)
        assert r.final_total == pytest.approx(0.0)

    def test_rush_surcharge_applied(self):
        r = _make_result([1000], rush=0.50)
        r = recompute_totals(r)
        # subtotal 1000, rush *1.5, overhead *1.15, profit *1.25
        expected_subtotal_after = 1000 * 1.50 * (1 + r.risk_buffer_pct)
        assert r.subtotal_after_multipliers == pytest.approx(expected_subtotal_after)

    def test_vat_added_to_pre_vat(self):
        r = _make_result([10000])
        r.vat_pct = 0.18
        r = recompute_totals(r)
        assert r.final_total == pytest.approx(r.pre_vat_total * 1.18)

    def test_ils_secondary_currency_equals_final_for_ils(self):
        r = _make_result([5000])
        r.currency = "ILS"
        r = recompute_totals(r)
        assert r.final_total_ils == pytest.approx(r.final_total)

    def test_usd_secondary_currency_less_than_ils(self):
        r = _make_result([50000])
        r.currency = "ILS"
        r = recompute_totals(r)
        assert r.final_total_usd < r.final_total_ils
