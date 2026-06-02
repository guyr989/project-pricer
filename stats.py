"""
Stats tracking — records every completed run to stats.json
and displays a cumulative statistics panel at the end of each session.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)
console = Console()

STATS_PATH = Path(__file__).parent / "stats.json"


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

def record_run(result: Any, answers: dict) -> None:
    """Append one entry to stats.json for the current completed run."""
    integrations = answers.get("third_party_integrations", [])
    if not isinstance(integrations, list):
        integrations = []
    integrations = [i for i in integrations if i != "none"]

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "client_name": result.client_name or "",
        "project_type": answers.get("project_type", "unknown"),
        "final_total_ils": round(result.final_total_ils, 2),
        "final_total_usd": round(result.final_total_usd, 2),
        "total_hours": round(result.base_hours, 1),
        "hourly_rate": result.hourly_rate,
        "currency": result.currency,
        "cms_type": answers.get("cms_type", "none") if answers.get("cms_required") else "none",
        "has_ecommerce": bool(answers.get("ecommerce_required", False)),
        "has_video": bool(answers.get("has_video", False)),
        "deadline": answers.get("deadline", "no_rush"),
        "risk_level": answers.get("project_risk", "medium"),
        "vat_type": answers.get("vat_applicable", "none"),
        "integrations": integrations,
        "integrations_count": len(integrations),
        "rush": answers.get("deadline", "no_rush") in ("within_6_weeks", "within_3_weeks", "asap"),
    }

    data = _load_stats()
    data.append(entry)

    try:
        STATS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Stats recorded for run: %s", entry["client_name"])
    except OSError as exc:
        logger.warning("Could not write stats.json: %s", exc)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_stats() -> None:
    """Load stats.json and print a cumulative statistics panel."""
    data = _load_stats()
    if not data:
        return

    total = len(data)

    # Project type distribution
    type_counter: Counter = Counter(e.get("project_type", "unknown") for e in data)
    top_type, top_type_count = type_counter.most_common(1)[0]
    top_type_pct = top_type_count / total * 100

    # Price averages (ILS)
    avg_ils = sum(e.get("final_total_ils", 0) for e in data) / total
    avg_usd = sum(e.get("final_total_usd", 0) for e in data) / total

    # Hours average
    avg_hours = sum(e.get("total_hours", 0) for e in data) / total

    # Rush %
    rush_count = sum(1 for e in data if e.get("rush"))
    rush_pct = rush_count / total * 100

    # Most common CMS (excluding "none")
    cms_counter: Counter = Counter(
        e.get("cms_type", "none") for e in data if e.get("cms_type") not in (None, "none", "")
    )
    top_cms = cms_counter.most_common(1)[0][0] if cms_counter else "—"

    # Most common risk level
    risk_counter: Counter = Counter(e.get("risk_level", "medium") for e in data)
    top_risk = risk_counter.most_common(1)[0][0]

    # Top integrations
    all_integrations: list[str] = []
    for e in data:
        all_integrations.extend(e.get("integrations", []))
    int_counter: Counter = Counter(all_integrations)
    top_integrations = [name for name, _ in int_counter.most_common(3)]

    # Build table
    tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold white on #1e293b", expand=True)
    tbl.add_column("Metric", style="dim", min_width=30)
    tbl.add_column("Value", style="bold white", justify="right")

    tbl.add_row("Total quotes generated", str(total))
    tbl.add_row(
        "Most common project type",
        f"{top_type.replace('_', ' ').title()} ({top_type_pct:.0f}%)",
    )
    tbl.add_row("Average price", f"₪{avg_ils:,.0f}  /  ${avg_usd:,.0f}")
    tbl.add_row("Average total hours", f"{avg_hours:.1f}h")
    tbl.add_row("Rush jobs", f"{rush_count}/{total} ({rush_pct:.0f}%)")
    tbl.add_row("Most common CMS", top_cms.replace("_", " ").title())
    tbl.add_row("Most common risk level", top_risk.replace("_", " ").title())
    tbl.add_row(
        "Top integrations",
        ", ".join(i.replace("_", " ").title() for i in top_integrations) or "—",
    )

    console.print()
    console.print(Panel(
        tbl,
        title="[bold cyan]Your Quote Statistics[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    ))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_stats() -> list[dict]:
    if not STATS_PATH.exists():
        return []
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read stats.json: %s", exc)
        return []
