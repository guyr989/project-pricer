#!/usr/bin/env python3
"""
Website Project Pricing Calculator
CLI entry point — guides through client-facing and internal questions,
computes a price estimate, edits results, and outputs a PDF quote.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

import calculator
import pdf_export
import stats as stats_module

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
QUESTIONS_PATH = PROJECT_ROOT / "questions.json"
PRICING_PATH = PROJECT_ROOT / "pricing.json"
SESSIONS_DIR = PROJECT_ROOT / "sessions"
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

console = Console()

# ---------------------------------------------------------------------------
# Quick mode — defaults for skipped / IDK-answered questions
# ---------------------------------------------------------------------------
QUICK_DEFAULTS: dict = {
    "is_redesign":              False,
    "design_source":            "premium_template",
    "animations_level":         "basic",
    "revision_rounds":          "2",
    "content_writer":           "client",
    "content_ready":            "partial",
    "image_source":             "stock_free",
    "image_count":              8,
    "has_video":                False,
    "cms_required":             True,
    "cms_type":                 "wordpress",
    "contact_form":             True,
    "blog_section":             False,
    "ecommerce_required":       False,
    "booking_system":           False,
    "third_party_integrations": [],
    "multilingual":             False,
    "language_count":           1,
    "seo_setup":                True,
    "performance_optimization": False,
    "accessibility_compliance": False,
    "hosting_managed":          True,
    "ssl_setup":                True,
    "backup_service":           False,
    "email_hosting":            False,
    "payment_terms":            "50_50",
    "maintenance_retainer":     False,
    "ip_transfer":              False,
    "nda_required":             False,
    "vat_applicable":           "israel",
}

QUICK_PAGE_COUNT: dict = {
    "landing_page":  1,
    "brochure":      5,
    "business":      12,
    "ecommerce":     20,
    "blog_magazine": 10,
    "web_app":       15,
    "directory":     25,
}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("quote_calc")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(LOGS_DIR / "calculator.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(logging.Formatter("[ERROR] %(message)s"))
        logger.addHandler(ch)

    return logger


logger = _setup_logging()

# ---------------------------------------------------------------------------
# Bootstrap dirs
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    for d in (SESSIONS_DIR, LOGS_DIR, OUTPUTS_DIR):
        d.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def load_questions() -> list[dict]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def load_pricing() -> dict:
    with open(PRICING_PATH, encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

def should_ask(question: dict, answers: dict) -> bool:
    cond = question.get("condition")
    if not cond:
        return True
    dep_id = cond["question_id"]
    dep_val = cond["value"]
    actual = answers.get(dep_id)
    if isinstance(dep_val, bool):
        if isinstance(actual, str):
            actual = actual.lower() in ("yes", "true", "1", "y")
        elif isinstance(actual, int):
            actual = bool(actual)
    return actual == dep_val

# ---------------------------------------------------------------------------
# Ask a single question
# ---------------------------------------------------------------------------

def _get_default_number(q: dict, answers: dict) -> int:
    defaults = {
        "page_count": 5,
        "image_count": 10,
        "video_count": 1,
        "language_count": 2,
        "email_account_count": 3,
        "dev_hourly_rate": 350,
        "overhead_percentage": 15,
        "profit_margin": 25,
    }
    return defaults.get(q["id"], 0)


def ask_question(q: dict, answers: dict) -> object:
    label = q["label"]
    qtype = q["type"]

    if qtype == "yes_no":
        return inquirer.confirm(message=label, default=False).execute()

    elif qtype == "choice":
        choices = [Choice(value=opt["value"], name=opt["label"]) for opt in q.get("options", [])]
        return inquirer.select(message=label, choices=choices).execute()

    elif qtype == "multi_choice":
        choices = [Choice(value=opt["value"], name=opt["label"]) for opt in q.get("options", [])]
        result = inquirer.checkbox(message=label, choices=choices).execute()
        if "none" in result and len(result) == 1:
            return []
        return [v for v in result if v != "none"]

    elif qtype == "number":
        raw = inquirer.number(
            message=label,
            default=_get_default_number(q, answers),
            min_allowed=0,
        ).execute()
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0

    elif qtype in ("text", "currency"):
        if qtype == "currency":
            raw = inquirer.number(message=label, default=0, min_allowed=0).execute()
            try:
                return float(raw)
            except (ValueError, TypeError):
                return 0.0
        result = inquirer.text(message=label).execute()
        return result.strip()

    return None


# ---------------------------------------------------------------------------
# IDK wrapper
# ---------------------------------------------------------------------------

_IDK_SENTINEL = "__idk__"


def ask_with_idk(q: dict, answers: dict) -> tuple[object, bool]:
    """
    Wraps ask_question() adding "I'm not sure" to yes_no, choice, and
    multi_choice questions.  Returns (answer, is_idk).
    When IDK is selected, answer falls back to QUICK_DEFAULTS.get(q["id"]).
    """
    qtype = q["type"]
    label = q["label"]
    idk_choice = Choice(value=_IDK_SENTINEL, name="I'm not sure")

    if qtype == "yes_no":
        result = inquirer.select(
            message=label,
            choices=[
                Choice(value=True,  name="Yes"),
                Choice(value=False, name="No"),
                idk_choice,
            ],
            default=False,
        ).execute()
        if result == _IDK_SENTINEL:
            return QUICK_DEFAULTS.get(q["id"], False), True
        return result, False

    if qtype == "choice":
        choices = [Choice(value=opt["value"], name=opt["label"]) for opt in q.get("options", [])]
        choices.append(idk_choice)
        result = inquirer.select(message=label, choices=choices).execute()
        if result == _IDK_SENTINEL:
            return QUICK_DEFAULTS.get(q["id"]), True
        return result, False

    if qtype == "multi_choice":
        choices = [Choice(value=opt["value"], name=opt["label"]) for opt in q.get("options", [])]
        choices.append(idk_choice)
        results = inquirer.checkbox(message=label, choices=choices).execute()
        if _IDK_SENTINEL in results:
            return QUICK_DEFAULTS.get(q["id"], []), True
        if "none" in results and len(results) == 1:
            return [], False
        return [v for v in results if v != "none"], False

    # number, text, currency — no IDK option
    return ask_question(q, answers), False


# ---------------------------------------------------------------------------
# Session save / resume
# ---------------------------------------------------------------------------

def _session_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SESSIONS_DIR / f"session_{ts}.json"


def save_session(answers: dict) -> Path:
    path = _session_path()
    try:
        path.write_text(json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Session saved to %s", path)
    except OSError as exc:
        logger.error("Could not save session: %s", exc)
    return path


def list_sessions() -> list[Path]:
    return sorted(SESSIONS_DIR.glob("session_*.json"), reverse=True)


def load_session(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def offer_resume() -> dict | None:
    """
    If saved sessions exist, ask user whether to resume the most recent one.
    Returns pre-loaded answers dict or None (start fresh).
    """
    sessions = list_sessions()
    if not sessions:
        return None

    recent = sessions[0]
    ts_str = recent.stem.replace("session_", "")
    try:
        ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").strftime("%d %b %Y %H:%M")
    except ValueError:
        ts = ts_str

    console.print()
    console.print(Panel(
        f"[yellow]Saved session found[/yellow] from [bold]{ts}[/bold]\n"
        f"[dim]{recent.name}[/dim]",
        border_style="yellow",
        padding=(0, 2),
    ))

    choice = inquirer.select(
        message="What would you like to do?",
        choices=[
            Choice(value="resume", name="Resume saved session"),
            Choice(value="fresh",  name="Start a new quote"),
            Choice(value="discard", name="Discard saved session and start fresh"),
        ],
    ).execute()

    if choice == "resume":
        answers = load_session(recent)
        logger.info("Resumed session from %s", recent)
        console.print(f"[green]Session resumed.[/green] {len(answers)} answers pre-loaded.\n")
        return answers
    if choice == "discard":
        try:
            recent.unlink()
        except OSError:
            pass
    return None

# ---------------------------------------------------------------------------
# Interrupt handler (Ctrl+C mid-questionnaire)
# ---------------------------------------------------------------------------

def handle_interrupt(answers: dict) -> dict | None:
    """
    Called on KeyboardInterrupt during questionnaire.
    Returns the (possibly updated) answers dict if user chooses Resume,
    or exits the process otherwise.
    """
    console.print()
    try:
        choice = inquirer.select(
            message="Interrupted — what would you like to do?",
            choices=[
                Choice(value="resume",  name="Resume — continue answering"),
                Choice(value="save",    name="Save progress and exit"),
                Choice(value="discard", name="Discard and exit"),
            ],
        ).execute()
    except KeyboardInterrupt:
        # Second Ctrl+C: just exit
        sys.exit(0)

    if choice == "resume":
        return answers

    if choice == "save":
        path = save_session(answers)
        console.print(Panel(
            f"[green]Progress saved.[/green]\n[dim]{path}[/dim]\n\n"
            "Run [bold]python3 main.py[/bold] again to resume.",
            border_style="green",
            padding=(0, 2),
        ))

    sys.exit(0)

# ---------------------------------------------------------------------------
# Main questionnaire flow
# ---------------------------------------------------------------------------

def run_questionnaire(questions: list[dict], prefill: dict | None = None) -> tuple[dict, dict]:
    answers: dict = dict(prefill or {})
    idk_questions: dict = {}

    client_questions = [q for q in questions if not q.get("internal_only")]
    internal_questions = [q for q in questions if q.get("internal_only")]

    # --- Section 1: Client-facing ---
    console.print(Panel(
        "[bold cyan]SECTION 1 / 2[/bold cyan] — Client Information & Project Requirements\n"
        "[dim]Answer based on your conversation with the client.  "
        "Press Ctrl+C at any time to save/discard.[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()

    for q in client_questions:
        if not should_ask(q, answers):
            continue
        if q["id"] in answers:
            # Pre-filled from session — skip unless user is in revision mode
            continue
        while True:
            try:
                answer, is_idk = ask_with_idk(q, answers)
                if is_idk:
                    idk_questions[q["id"]] = q["label"]
                if answer is not None:
                    answers[q["id"]] = answer
                    logger.debug("Answered [%s] = %r (idk=%s)", q["id"], answer, is_idk)
                break
            except KeyboardInterrupt:
                result = handle_interrupt(answers)
                if result is not None:
                    answers = result
                else:
                    break
        console.print()

    # --- Section 2: Internal ---
    console.print()
    console.print(Panel(
        "[bold magenta]SECTION 2 / 2[/bold magenta] — Developer Self-Assessment\n"
        "[dim]These answers stay private — they won't appear on the client PDF.[/dim]",
        border_style="magenta",
        padding=(0, 2),
    ))
    console.print()

    for q in internal_questions:
        if not should_ask(q, answers):
            continue
        if q["id"] in answers:
            continue
        while True:
            try:
                answer = ask_question(q, answers)
                if answer is not None:
                    answers[q["id"]] = answer
                    logger.debug("Answered [%s] = %r", q["id"], answer)
                break
            except KeyboardInterrupt:
                result = handle_interrupt(answers)
                if result is not None:
                    answers = result
                else:
                    break
        console.print()

    return answers, idk_questions


# ---------------------------------------------------------------------------
# Quick questionnaire
# ---------------------------------------------------------------------------

def run_quick_questionnaire(questions: list[dict]) -> tuple[dict, dict]:
    """
    Simplified 6-question client-conversation flow.
    Returns (answers, idk_questions) in the same format as run_questionnaire.
    All unasked questions are pre-filled from QUICK_DEFAULTS.
    """
    idk_questions: dict = {}
    answers: dict = {}

    console.print(Panel(
        "[bold cyan]QUICK QUOTE[/bold cyan] — Let's get the basics\n"
        "[dim]6 questions. Press Ctrl+C at any time to save / exit.[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()

    # 1. Client name
    while True:
        try:
            name = inquirer.text(message="Client name (for the quote):").execute().strip()
            answers["client_name"] = name
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # 2. Site type
    while True:
        try:
            project_type = inquirer.select(
                message="What kind of website does the client need?",
                choices=[
                    Choice(value="landing_page", name="Just a landing page  (single page, one focused message)"),
                    Choice(value="brochure",      name="Small online presence  (4-5 pages: Home, About, Services, Contact)"),
                    Choice(value="business",      name="Full business website  (10+ pages)"),
                    Choice(value="ecommerce",     name="Online store"),
                    Choice(value=_IDK_SENTINEL,   name="Not sure yet"),
                ],
            ).execute()
            if project_type == _IDK_SENTINEL:
                idk_questions["project_type"] = "What kind of website does the client need?"
                project_type = "brochure"
            answers["project_type"] = project_type
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # 3. Brand identity
    while True:
        try:
            brand = inquirer.select(
                message="Does the client have a logo / brand kit ready?",
                choices=[
                    Choice(value="full_brand",  name="Yes — full brand kit (logo + colors + fonts)"),
                    Choice(value="logo_only",    name="Logo only"),
                    Choice(value="no_brand",     name="No — needs branding too"),
                    Choice(value=_IDK_SENTINEL,  name="Not sure"),
                ],
            ).execute()
            if brand == _IDK_SENTINEL:
                idk_questions["has_brand_identity"] = "Does the client have a logo / brand kit?"
                brand = QUICK_DEFAULTS.get("has_brand_identity", "logo_only")
            answers["has_brand_identity"] = brand
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # 4. Content writer
    while True:
        try:
            writer = inquirer.select(
                message="Who will write the website text content?",
                choices=[
                    Choice(value="client",      name="The client writes everything"),
                    Choice(value="developer",   name="You (the developer) write it"),
                    Choice(value="mixed",       name="Client drafts, you refine"),
                    Choice(value=_IDK_SENTINEL, name="Not sure yet"),
                ],
            ).execute()
            if writer == _IDK_SENTINEL:
                idk_questions["content_writer"] = "Who will write the website text content?"
                writer = QUICK_DEFAULTS.get("content_writer", "client")
            answers["content_writer"] = writer
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # 5. Deadline / urgency
    while True:
        try:
            deadline = inquirer.select(
                message="How urgent is this project?",
                choices=[
                    Choice(value="no_rush",         name="No rush — flexible timeline"),
                    Choice(value="within_3_months",  name="Within 3 months"),
                    Choice(value="within_6_weeks",   name="Within 6 weeks  (+25%)"),
                    Choice(value="within_3_weeks",   name="Within 3 weeks  (+50%)"),
                    Choice(value="asap",             name="ASAP  (+75%)"),
                    Choice(value=_IDK_SENTINEL,      name="Not sure yet"),
                ],
            ).execute()
            if deadline == _IDK_SENTINEL:
                idk_questions["deadline"] = "What is the project urgency / deadline?"
                deadline = QUICK_DEFAULTS.get("deadline", "no_rush")
            answers["deadline"] = deadline
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # 6. Special features
    while True:
        try:
            features = inquirer.checkbox(
                message="Any special features? (space to toggle, enter to confirm)",
                choices=[
                    Choice(value="blog",        name="Blog / news section"),
                    Choice(value="bilingual",   name="Hebrew + English  (bilingual)"),
                    Choice(value="booking",     name="Booking / appointment system"),
                    Choice(value="none",        name="None — keep it simple"),
                    Choice(value=_IDK_SENTINEL, name="Not sure"),
                ],
            ).execute()
            if _IDK_SENTINEL in features:
                idk_questions["extras"] = "Any special features needed? (blog, bilingual, booking, etc.)"
            else:
                if "blog" in features:
                    answers["blog_section"] = True
                if "bilingual" in features:
                    answers["multilingual"] = True
                    answers["language_count"] = 2
                if "booking" in features:
                    answers["booking_system"] = True
            break
        except KeyboardInterrupt:
            res = handle_interrupt(answers)
            if res is not None:
                answers = res
    console.print()

    # Merge defaults (explicit answers override defaults)
    full_answers = {**QUICK_DEFAULTS, **answers}

    # Derive page count from project type
    pt = full_answers.get("project_type", "brochure")
    full_answers.setdefault("page_count", QUICK_PAGE_COUNT.get(pt, 5))

    # Landing page doesn't need a CMS
    if pt == "landing_page":
        full_answers["cms_required"] = False

    full_answers["_quick_mode"] = True

    return full_answers, idk_questions


# ---------------------------------------------------------------------------
# Answer revision
# ---------------------------------------------------------------------------

def _format_answer_preview(val: object) -> str:
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) or "—"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    return str(val)


def revise_answers(answers: dict, questions: list[dict]) -> dict:
    """
    Offer a multi-select list of answered questions; re-ask the chosen ones.
    Loops until user confirms they're done.
    """
    q_by_id = {q["id"]: q for q in questions}

    while True:
        want_revise = inquirer.confirm(
            message="Would you like to revise any of your answers?",
            default=False,
        ).execute()

        if not want_revise:
            break

        # Build choices of all currently answered, visible questions
        answered_ids = [
            qid for qid in answers
            if qid in q_by_id and should_ask(q_by_id[qid], answers)
        ]

        if not answered_ids:
            console.print("[dim]No answers to revise.[/dim]")
            break

        choices = [
            Choice(
                value=qid,
                name=f"{q_by_id[qid]['label']}  [dim]({_format_answer_preview(answers[qid])})[/dim]",
            )
            for qid in answered_ids
        ]

        to_revise = inquirer.checkbox(
            message="Select questions to revise (space to toggle, enter to confirm):",
            choices=choices,
        ).execute()

        if not to_revise:
            break

        for qid in to_revise:
            q = q_by_id[qid]
            console.print(f"\n[bold]Re-asking:[/bold] {q['label']}")
            try:
                answer = ask_question(q, answers)
                if answer is not None:
                    answers[qid] = answer
                    logger.debug("Revised [%s] = %r", qid, answer)
            except KeyboardInterrupt:
                console.print("[yellow]Skipped.[/yellow]")
            console.print()

    return answers

# ---------------------------------------------------------------------------
# Display summary
# ---------------------------------------------------------------------------

def display_summary(result: calculator.PricingResult) -> None:
    sym = pdf_export.CURRENCY_SYMBOLS.get(result.currency, result.currency)

    def fmt(v: float) -> str:
        return f"{sym}{int(round(v)):,}"

    console.print()
    console.print(Panel(
        f"[bold green]Estimate complete for:[/bold green] [bold white]{result.client_name}[/bold white]",
        border_style="green",
    ))

    tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold white on #1e293b")
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("Item", style="white", min_width=38)
    tbl.add_column("Hours", justify="right", style="cyan")
    tbl.add_column("Cost", justify="right", style="yellow")

    for i, item in enumerate(result.line_items, 1):
        h = f"{item.hours:.1f}h" if item.hours > 0 else "—"
        c = fmt(item.cost) if item.cost > 0 else "—"
        tbl.add_row(str(i), item.label, h, c)

    console.print(tbl)

    mult_lines = []
    if result.rush_surcharge_pct:
        mult_lines.append(f"Rush: +{result.rush_surcharge_pct*100:.0f}%")
    if result.tech_multiplier_pct:
        mult_lines.append(f"Tech learning: +{result.tech_multiplier_pct*100:.0f}%")
    if result.client_difficulty_pct:
        mult_lines.append(f"Client complexity: +{result.client_difficulty_pct*100:.0f}%")
    mult_lines.append(f"Risk buffer: +{result.risk_buffer_pct*100:.0f}%")
    mult_lines.append(f"Overhead: +{result.overhead_pct*100:.0f}%")
    mult_lines.append(f"Profit: +{result.profit_margin_pct*100:.0f}%")
    if result.ip_premium_pct:
        mult_lines.append(f"IP transfer: +{result.ip_premium_pct*100:.0f}%")
    if result.long_term_discount_pct:
        mult_lines.append(f"[green]Long-term discount: -{result.long_term_discount_pct*100:.0f}%[/green]")
    if result.portfolio_discount_pct:
        mult_lines.append(f"[green]Portfolio discount: -{result.portfolio_discount_pct*100:.0f}%[/green]")

    console.print(f"\n[dim]Adjustments: {' · '.join(mult_lines)}[/dim]")

    _print_totals(result, sym)

    if result.recurring_items:
        console.print("[bold]Monthly recurring costs:[/bold]")
        for item in result.recurring_items:
            console.print(f"  • {item.label}: {sym}{int(round(item.cost)):,}/mo")

    console.print()


def _print_totals(result: calculator.PricingResult, sym: str) -> None:
    def fmt(v: float) -> str:
        return f"{sym}{int(round(v)):,}"

    totals = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    totals.add_column("", style="dim")
    totals.add_column("", justify="right")

    totals.add_row("Subtotal (before adjustments)", fmt(result.subtotal_before_multipliers))
    totals.add_row("After adjustments (pre-VAT)", fmt(result.pre_vat_total))
    if result.vat_pct > 0:
        totals.add_row(f"VAT ({result.vat_pct*100:.0f}%)", fmt(result.vat_amount))
    totals.add_row(
        Text("TOTAL", style="bold white"),
        Text(fmt(result.final_total), style="bold green"),
    )
    if result.currency != "ILS":
        totals.add_row("[dim]Also:[/dim]", f"[dim]₪{int(round(result.final_total_ils)):,} ILS[/dim]")
    if result.currency != "USD":
        totals.add_row("[dim]Also:[/dim]", f"[dim]${int(round(result.final_total_usd)):,} USD[/dim]")

    console.print(totals)

# ---------------------------------------------------------------------------
# Editable line items
# ---------------------------------------------------------------------------

def edit_line_items(result: calculator.PricingResult) -> calculator.PricingResult:
    """
    Let user select and adjust individual line items (hours or cost).
    Recomputes totals after each edit round.
    """
    sym = pdf_export.CURRENCY_SYMBOLS.get(result.currency, result.currency)

    while True:
        want_edit = inquirer.confirm(
            message="Would you like to manually adjust any line items?",
            default=False,
        ).execute()

        if not want_edit:
            break

        choices = [
            Choice(
                value=i,
                name=f"{item.label}  "
                     f"[dim]{item.hours:.1f}h / {sym}{int(round(item.cost)):,}[/dim]",
            )
            for i, item in enumerate(result.line_items)
        ]
        choices.append(Choice(value=-1, name="[dim]Done editing[/dim]"))

        idx = inquirer.select(
            message="Select a line item to adjust:",
            choices=choices,
        ).execute()

        if idx == -1:
            break

        item = result.line_items[idx]
        console.print(f"\n[bold]{item.label}[/bold]  "
                      f"current: {item.hours:.1f}h / {sym}{int(round(item.cost)):,}")

        edit_mode = inquirer.select(
            message="Edit:",
            choices=[
                Choice(value="hours", name=f"Hours  (current: {item.hours:.1f}h)"),
                Choice(value="cost",  name=f"Cost directly  (current: {sym}{int(round(item.cost)):,})"),
                Choice(value="cancel", name="Cancel"),
            ],
        ).execute()

        if edit_mode == "cancel":
            console.print()
            continue

        try:
            if edit_mode == "hours":
                new_hours = float(inquirer.number(
                    message="New hours:",
                    default=round(item.hours),
                    min_allowed=0,
                ).execute())
                item.hours = new_hours
                item.cost = new_hours * result.hourly_rate
            else:
                new_cost = float(inquirer.number(
                    message=f"New cost ({sym}):",
                    default=int(round(item.cost)),
                    min_allowed=0,
                ).execute())
                item.cost = new_cost

            # Mark as manually adjusted
            if not item.label.endswith("*"):
                item.label += "  *"

            logger.info("Line item '%s' adjusted to %.1fh / %.2f", item.label, item.hours, item.cost)

        except KeyboardInterrupt:
            console.print("[yellow]Edit cancelled.[/yellow]")
            console.print()
            continue

        # Recompute totals
        result = calculator.recompute_totals(result)

        # Show updated totals only
        console.print()
        console.print("[bold]Updated totals:[/bold]")
        _print_totals(result, sym)
        console.print()

    return result

# ---------------------------------------------------------------------------
# Client questions document
# ---------------------------------------------------------------------------

def generate_client_questions_doc(idk_questions: dict, client_name: str, output_dir: Path) -> Path | None:
    """
    Write a plain-text list of open questions to clarify with the client.
    Returns the output path, or None if idk_questions is empty.
    """
    if not idk_questions:
        return None

    date_str = datetime.now().strftime("%d %b %Y")
    lines = [
        f"Questions to clarify with: {client_name or 'client'}",
        f"Generated: {date_str}",
        "",
        "The following details were left open during the quote session.",
        "Please go over these with the client before finalising the quote.",
        "",
    ]
    for i, (_qid, label) in enumerate(idk_questions.items(), 1):
        lines.append(f" {i}. {label}")
    lines.append("")

    path = output_dir / "client_questions.txt"
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Client questions doc saved: %s", path)
        return path
    except OSError as exc:
        logger.warning("Could not write client_questions.txt: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _ensure_dirs()

    console.print()
    console.print(Panel(
        "[bold cyan]Website Project Pricing Calculator[/bold cyan]\n"
        "[dim]Answer the questions to generate a professional PDF quote.[/dim]\n"
        "[dim]Press Ctrl+C at any time — you can save your progress.[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    logger.info("=== New session started ===")

    # Check for saved session
    prefill = offer_resume()

    questions = load_questions()
    idk_questions: dict = {}

    # Determine mode (quick vs full) — only ask on fresh sessions
    quick_mode: bool = prefill.get("_quick_mode", False) if prefill else False
    if not prefill:
        try:
            mode = inquirer.select(
                message="How would you like to proceed?",
                choices=[
                    Choice(value="quick", name="Quick  — 6 questions, great for client calls"),
                    Choice(value="full",  name="Full   — detailed ~50-question flow"),
                ],
            ).execute()
        except KeyboardInterrupt:
            mode = "full"
        quick_mode = (mode == "quick")

    try:
        if quick_mode and not prefill:
            # Quick: 6 client questions, then internal section via run_questionnaire
            answers, idk_questions = run_quick_questionnaire(questions)
            answers, _ = run_questionnaire(questions, prefill=answers)
        else:
            answers, idk_questions = run_questionnaire(questions, prefill=prefill)
    except Exception as exc:
        logger.exception("Unexpected error during questionnaire")
        console.print(f"[red]Unexpected error:[/red] {exc}")
        console.print("[dim]Check logs/calculator.log for details.[/dim]")
        sys.exit(1)

    # Revise answers before calculating (not offered in quick mode)
    if not quick_mode:
        try:
            answers = revise_answers(answers, questions)
        except KeyboardInterrupt:
            handle_interrupt(answers)

    # Calculate
    try:
        result = calculator.calculate(answers, questions)
        logger.info("Calculation complete: %s total %.2f %s",
                    result.client_name, result.final_total, result.currency)
    except Exception as exc:
        logger.exception("Error during price calculation")
        console.print(f"[red]Calculation error:[/red] {exc}")
        sys.exit(1)

    # Show summary
    display_summary(result)

    # Allow line item edits
    try:
        result = edit_line_items(result)
    except KeyboardInterrupt:
        console.print("[dim]Skipping line item edits.[/dim]")

    # PDF language
    try:
        lang = inquirer.select(
            message="Generate PDF in which language?",
            choices=[
                Choice(value="en", name="English (default)"),
                Choice(value="he", name="Hebrew / עברית"),
            ],
            default="en",
        ).execute()
    except KeyboardInterrupt:
        lang = "en"

    # Generate PDF
    console.print()
    out_dir = pdf_export.get_output_dir(result.client_name or "client")
    try:
        with console.status("[bold cyan]Generating PDF...[/bold cyan]"):
            output_path = pdf_export.render_pdf(result, language=lang, output_dir=out_dir)
        logger.info("PDF saved: %s", output_path)
        console.print(Panel(
            f"[bold green]Quote saved![/bold green]\n[white]{output_path}[/white]",
            border_style="green",
            padding=(0, 2),
        ))
    except Exception as exc:
        logger.exception("PDF generation failed")
        console.print(f"[red]PDF generation failed:[/red] {exc}")
        # Fallback: save HTML
        try:
            html_path = out_dir / f"quote_{result.project_type_label}_{lang}.html"
            html_path.write_text(pdf_export.render_html(result, lang), encoding="utf-8")
            console.print(f"[yellow]Saved HTML fallback instead:[/yellow] {html_path}")
        except Exception as html_exc:
            logger.exception("HTML fallback also failed")
            console.print(f"[red]HTML fallback also failed:[/red] {html_exc}")

    # Save client questions doc if any IDKs were recorded
    if idk_questions:
        doc_path = generate_client_questions_doc(idk_questions, result.client_name or "client", out_dir)
        if doc_path:
            console.print(Panel(
                f"[bold yellow]Open questions saved:[/bold yellow]\n[white]{doc_path}[/white]",
                border_style="yellow",
                padding=(0, 2),
            ))

    # Record stats
    try:
        stats_module.record_run(result, answers)
    except Exception as exc:
        logger.warning("Stats recording failed: %s", exc)

    # Display stats panel
    try:
        stats_module.display_stats()
    except Exception as exc:
        logger.warning("Stats display failed: %s", exc)

    console.print()
    logger.info("=== Session complete ===")


if __name__ == "__main__":
    main()
