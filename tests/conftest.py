"""Shared fixtures for the test suite."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the project root importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

QUESTIONS_PATH = PROJECT_ROOT / "questions.json"


@pytest.fixture(scope="session")
def questions() -> list[dict]:
    """Load the real questions.json once for the whole test session."""
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]


@pytest.fixture
def minimal_answers() -> dict:
    """
    Minimal valid answers dict for a brochure site.
    Sets every key the calculator reads so no defaults are needed.
    """
    return {
        "client_name": "Test Client",
        "project_type": "brochure",
        "is_redesign": False,
        "page_count": 5,
        "deadline": "no_rush",
        "design_source": "premium_template",
        "has_brand_identity": "full_brand",
        "animations_level": "none",
        "revision_rounds": "2",
        "content_writer": "client",
        "content_ready": "all_ready",
        "image_source": "client_provides",
        "image_count": 0,
        "has_video": False,
        "multilingual": False,
        "language_count": 1,
        "cms_required": True,
        "cms_type": "wordpress",
        "ecommerce_required": False,
        "third_party_integrations": [],
        "hosting_managed": True,
        "vat_applicable": "israel",
        "payment_terms": "50_50",
        "currency": "ILS",
        "dev_hourly_rate": 350,
        "overhead_percentage": 15,
        "profit_margin": 25,
        "project_risk": "medium",
        "tech_familiarity": "expert",
        "client_communication": "normal",
        "ip_transfer": False,
        "long_term_client": False,
        "portfolio_value": False,
    }
