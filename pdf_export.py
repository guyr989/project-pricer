"""
PDF export — renders a Jinja2 HTML template via weasyprint.
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from calculator import PricingResult

TEMPLATES_DIR = Path(__file__).parent / "templates"

CURRENCY_SYMBOLS = {"ILS": "₪", "USD": "$", "EUR": "€"}


def _format_number(value: int | float) -> str:
    """Add thousands separator (e.g. 12500 → 12,500)."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def get_output_dir(client_name: str) -> Path:
    """
    Return (and create) the per-run output directory:
    outputs/<slugified_client_name>_<YYYYMMDD>/
    """
    project_root = Path(__file__).parent
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", client_name.lower()).strip("_")[:30] or "client"
    folder_name = f"{slug}_{date.today().strftime('%Y%m%d')}"
    out_dir = project_root / "outputs" / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def render_html(result: PricingResult, language: str = "en") -> str:
    """Render the Jinja2 template to an HTML string (used as PDF fallback)."""
    template_file = f"quote_{language}.html"
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["format_number"] = _format_number
    template = env.get_template(template_file)

    quote_date = date.today().strftime("%d %B %Y") if language == "en" else date.today().strftime("%d/%m/%Y")
    quote_number = f"QT-{date.today().strftime('%Y%m%d')}-{abs(hash(result.client_name)) % 1000:03d}"
    currency_sym = CURRENCY_SYMBOLS.get(result.currency, result.currency)

    context = {
        "client_name": result.client_name or "Client",
        "project_type_label": result.project_type_label,
        "quote_date": quote_date,
        "quote_number": quote_number,
        "currency": result.currency,
        "currency_sym": currency_sym,
        "hourly_rate": result.hourly_rate,
        "base_hours": result.base_hours,
        "page_count": _get_page_count(result),
        "payment_schedule": result.payment_schedule,
        "additional_notes": result.additional_notes,
        "line_items": result.line_items,
        "recurring_items": result.recurring_items,
        "rush_surcharge_pct": result.rush_surcharge_pct,
        "tech_multiplier_pct": result.tech_multiplier_pct,
        "client_difficulty_pct": result.client_difficulty_pct,
        "risk_buffer_pct": result.risk_buffer_pct,
        "overhead_pct": result.overhead_pct,
        "profit_margin_pct": result.profit_margin_pct,
        "ip_premium_pct": result.ip_premium_pct,
        "long_term_discount_pct": result.long_term_discount_pct,
        "portfolio_discount_pct": result.portfolio_discount_pct,
        "subtotal_before_multipliers": result.subtotal_before_multipliers,
        "pre_vat_total": result.pre_vat_total,
        "vat_pct": result.vat_pct,
        "vat_amount": result.vat_amount,
        "final_total": result.final_total,
        "final_total_ils": result.final_total_ils,
        "final_total_usd": result.final_total_usd,
    }
    return template.render(**context)


def render_pdf(result: PricingResult, language: str = "en", output_path: str | None = None, output_dir: Path | None = None) -> Path:
    """
    Render the pricing result to a PDF file.

    Args:
        result: PricingResult from calculator.calculate()
        language: "en" for English, "he" for Hebrew
        output_path: optional explicit full path (overrides output_dir)
        output_dir: optional directory; if omitted defaults to outputs/<client>_<date>/

    Returns:
        Path to the generated PDF.
    """
    # Sanitize project_type_label for filename
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", result.project_type_label.lower()).strip("_")[:30]
    if not output_path:
        if output_dir is None:
            output_dir = get_output_dir(result.client_name or "client")
        filename = f"quote_{date.today().strftime('%Y%m%d')}_{slug}_{language}.pdf"
        output_path = str(output_dir / filename)

    html_content = render_html(result, language)
    HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(output_path)
    return Path(output_path)


def _get_page_count(result: PricingResult) -> int:
    """Extract page count from line items as a best-effort fallback."""
    for item in result.line_items:
        if "Additional pages" in item.label:
            import re as _re
            m = _re.search(r"\((\d+) ×", item.label)
            if m:
                return int(m.group(1))
    return 1
