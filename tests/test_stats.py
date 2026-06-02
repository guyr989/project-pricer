"""Tests for stats.py — run statistics tracking."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import calculator
import stats as stats_module
from calculator import LineItem, PricingResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_stats_path(tmp_path) -> Path:
    return tmp_path / "stats.json"


@pytest.fixture
def sample_result() -> PricingResult:
    r = PricingResult(currency="ILS", hourly_rate=350.0)
    r.line_items = [LineItem(label="Base dev", hours=40, cost=14000)]
    r.base_hours = 40.0
    r.final_total = 35000.0
    r.final_total_ils = 35000.0
    r.final_total_usd = 9333.0
    r.client_name = "Roni Bakery"
    r.pre_vat_total = 29661.0
    r.vat_pct = 0.18
    r.vat_amount = 5338.98
    return r


@pytest.fixture
def sample_answers() -> dict:
    return {
        "project_type": "brochure",
        "deadline": "no_rush",
        "project_risk": "medium",
        "vat_applicable": "israel",
        "cms_required": True,
        "cms_type": "wordpress",
        "has_video": False,
        "third_party_integrations": ["crm_integration"],
        "currency": "ILS",
    }


# ---------------------------------------------------------------------------
# _load_stats()
# ---------------------------------------------------------------------------

class TestLoadStats:
    def test_returns_empty_list_when_file_missing(self, tmp_stats_path):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            data = stats_module._load_stats()
        assert data == []

    def test_returns_empty_list_on_corrupt_json(self, tmp_stats_path):
        tmp_stats_path.write_text("not valid json", encoding="utf-8")
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            data = stats_module._load_stats()
        assert data == []

    def test_returns_list_of_entries(self, tmp_stats_path):
        entries = [{"client_name": "A"}, {"client_name": "B"}]
        tmp_stats_path.write_text(json.dumps(entries), encoding="utf-8")
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            data = stats_module._load_stats()
        assert data == entries


# ---------------------------------------------------------------------------
# record_run()
# ---------------------------------------------------------------------------

class TestRecordRun:
    def test_creates_stats_file(self, tmp_stats_path, sample_result, sample_answers):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
        assert tmp_stats_path.exists()

    def test_appends_one_entry(self, tmp_stats_path, sample_result, sample_answers):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            data = json.loads(tmp_stats_path.read_text())
        assert len(data) == 1

    def test_appends_multiple_entries(self, tmp_stats_path, sample_result, sample_answers):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            stats_module.record_run(sample_result, sample_answers)
            data = json.loads(tmp_stats_path.read_text())
        assert len(data) == 2

    def test_entry_contains_expected_keys(self, tmp_stats_path, sample_result, sample_answers):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]

        required_keys = {
            "timestamp", "client_name", "project_type", "final_total_ils",
            "final_total_usd", "total_hours", "hourly_rate", "currency",
            "rush", "risk_level",
        }
        assert required_keys.issubset(entry.keys())

    def test_client_name_recorded(self, tmp_stats_path, sample_result, sample_answers):
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]
        assert entry["client_name"] == "Roni Bakery"

    def test_rush_false_for_no_rush_deadline(self, tmp_stats_path, sample_result, sample_answers):
        sample_answers["deadline"] = "no_rush"
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]
        assert entry["rush"] is False

    def test_rush_true_for_asap_deadline(self, tmp_stats_path, sample_result, sample_answers):
        sample_answers["deadline"] = "asap"
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]
        assert entry["rush"] is True

    def test_integrations_exclude_none_value(self, tmp_stats_path, sample_result, sample_answers):
        sample_answers["third_party_integrations"] = ["crm_integration", "none"]
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]
        assert "none" not in entry["integrations"]

    def test_non_list_integrations_recorded_as_empty(self, tmp_stats_path, sample_result, sample_answers):
        sample_answers["third_party_integrations"] = "crm_integration"
        with patch.object(stats_module, "STATS_PATH", tmp_stats_path):
            stats_module.record_run(sample_result, sample_answers)
            entry = json.loads(tmp_stats_path.read_text())[0]
        assert entry["integrations"] == []
