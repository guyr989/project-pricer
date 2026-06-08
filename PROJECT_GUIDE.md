# Project Pricer — Developer & LLM Onboarding Guide

**Freelance website quote calculator.** Interactive CLI questionnaire → pricing engine → bilingual PDF quotes (EN/HE).

Built for freelance web developers who need to quickly scope a project during or after a client call, then hand over a professional quote PDF.

---

## Quick Start

```bash
git clone https://github.com/guyr989/project-pricer.git
cd project-pricer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

> **Note:** On this machine the venv has no `pip` binary. Use:
> `python3 -m pip install --target=.venv/lib/python3.13/site-packages <pkg>`

---

## Architecture / File Map

```
project-pricer/
├── main.py                  # CLI entry point — questionnaire flow, session mgmt, output orchestration
├── calculator.py            # Pricing engine — PricingResult/LineItem dataclasses, calculate(), recompute_totals()
├── pdf_export.py            # Jinja2 + WeasyPrint PDF/HTML rendering, client & internal templates
├── internal_summary.py      # Plain-text internal pricing report (rates, multipliers, flags)
├── client_message.py        # Client follow-up message generator — 8 format combos (EN/HE × Formal/Casual × SMS/Email)
├── generate_message.py      # Standalone CLI to regenerate client messages from session/IDK files
├── stats.py                 # Records runs to stats.json, displays cumulative analytics via Rich
├── demo.py                  # Non-interactive demo with hardcoded scenario (in .gitignore)
├── git_setup.py             # One-time repo setup script (in .gitignore)
│
├── questions.json           # ~50 conditional scoping questions (7 categories, bilingual labels)
├── pricing.json             # All rates, multipliers, FX, VAT, hosting estimates (config-driven)
├── requirements.txt         # InquirerPy, rich, weasyprint, jinja2
│
├── templates/
│   ├── quote_en.html        # Client-facing PDF template (English, LTR)
│   ├── quote_he.html        # Client-facing PDF template (Hebrew, RTL, Heebo font)
│   ├── internal_en.html     # Internal PDF template with full breakdown + red banner
│   └── internal_he.html     # Internal PDF template (Hebrew)
│
├── tests/
│   ├── conftest.py          # Shared fixtures (questions, minimal_answers)
│   ├── test_calculator.py   # ~50 pricing engine tests
│   ├── test_pdf_export.py   # PDF/HTML rendering tests
│   ├── test_stats.py        # Stats recording/display tests
│   ├── test_main_helpers.py # Helper function tests
│   ├── test_client_message.py   # 26 message generator tests
│   └── test_internal_summary.py # 9 internal summary tests
│
├── outputs/                 # Generated quotes (per-client folders, gitignored)
├── sessions/                # Saved session JSON files (gitignored)
├── logs/                    # calculator.log debug log (gitignored)
└── stats.json               # Cumulative run history (gitignored)
```

**Total: ~133 tests across 7 test files.**

---

## How It Works — Step by Step

### 1. Launch

```bash
python3 main.py
```

You're offered to resume a saved session (if any exist), then choose a mode:

| Mode | Questions | Best for |
|------|-----------|----------|
| **Quick** | 6 client questions + internal section | During a client call |
| **Full** | ~50 conditional questions | After a detailed discovery call |

### 2. Questionnaire (two sections)

**Section 1 — Client Information** (not marked internal)
- Project type, pages, deadline, design, content, technical, hosting, business terms
- Every yes/no, choice, and multi-choice question has an **"I'm not sure" (IDK)** option
- IDK answers fall back to sensible defaults and get queued for client follow-up

**Section 2 — Developer Self-Assessment** (marked `internal_only: true`)
- Hourly rate, tech familiarity, client difficulty, risk level, overhead, profit margin
- These never appear on the client PDF

### 3. Answer Revision (Full mode only)

Multi-select which answers to change, re-answer them, loop until satisfied.

### 4. Price Calculation

`calculator.calculate()` builds line items from answers, then applies multipliers:

```
base line items (hours × rate)
  × rush surcharge
  × tech familiarity
  × client difficulty
  × risk buffer
  × multi-language
  → subtotal after multipliers
  × overhead
  × profit margin
  × IP transfer premium
  − discounts (long-term client, portfolio)
  → pre-VAT total
  + VAT
  = final total (shown in ILS + USD always)
```

### 5. Line-Item Editing

Select any line item → override hours or cost directly → totals recompute automatically.

### 6. Output Generation

| Output | Description |
|--------|-------------|
| **Client PDF** | Clean quote — line items + totals only, no rates/multipliers |
| **Internal PDF** | Full breakdown with red "INTERNAL" banner, all multipliers visible |
| **Internal TXT** | Plain-text summary (rates, effective rate, multipliers, flags) |
| **Client Message** | Follow-up message for IDK questions (if any), customizable language/tone/format |

All outputs land in `outputs/<client_name>_<YYYYMMDD>/`.

### 7. Stats

After each run, stats are recorded to `stats.json` and a Rich panel shows cumulative analytics (total quotes, avg price, rush %, top CMS, etc.).

---

## Key Design Decisions

| Pattern | Details |
|---------|---------|
| **Config-driven pricing** | All rates, multipliers, and costs live in `pricing.json` — no code changes needed to adjust pricing |
| **Conditional branching** | Questions have a `condition` field (`{question_id, value}`) — only shown when the parent answer matches |
| **IDK fallback** | Unanswered questions use `QUICK_DEFAULTS` for pricing and get tracked for client follow-up messages |
| **Client/Internal split** | `internal_only: true` questions stay off client PDFs. Two separate template sets |
| **Multiplicative multipliers** | Rush, tech, difficulty, risk compose multiplicatively (not additive) — prevents underpricing on stacked risks |
| **Dual currency** | Final total always shows both ILS and USD regardless of primary currency |
| **Session persistence** | Ctrl+C mid-questionnaire → save/resume/discard menu. Sessions stored as JSON |
| **Weight-based question sorting** | Client messages sort IDK questions by weight (critical → high → medium → low) |

---

## Configuration

### questions.json

Each question has:
```
id, category, label, label_he, type, options[], condition, weight, internal_only
```

- **Types:** `yes_no`, `choice`, `multi_choice`, `number`, `text`
- **Categories:** scope, design, content, technical, hosting, business, internal
- **Options** can carry pricing metadata: `base_hours`, `extra_hours`, `rush_key`, `familiarity_key`, etc.

### pricing.json

Key sections: `base_rates`, `multipliers`, `additive_costs`, `vat`, `currencies.fx_rates`, `hosting_estimates`, `maintenance_retainer`

To change default hourly rate: edit `base_rates.developer_hourly_rate_ils`.
To update FX: edit `currencies.fx_rates.USD_to_ILS`.

---

## Output Structure

```
outputs/
└── ronis_bakery_20260602/
    ├── quote_20260602_business_en.pdf         # Client PDF
    ├── internal_20260602_business_en.pdf      # Internal PDF
    ├── internal_summary_en.txt                # Internal text report
    └── client_questions_en_formal_email.txt   # Follow-up message (if IDKs exist)

sessions/
└── session_20260602_143022.json               # Resumable session

logs/
└── calculator.log                             # Full debug log
```

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Full questionnaire (~50q) | Done | Conditional branching, 7 categories |
| Quick mode (6q) | Done | Great for live client calls |
| Pricing engine | Done | 11+ multipliers, line items, recurring costs |
| Client PDF (EN/HE) | Done | WeasyPrint, RTL support with Heebo font |
| Internal PDF (EN/HE) | Done | Red "INTERNAL" banner, full breakdown |
| Internal TXT summary | Done | Plain-text rates/multipliers/flags report |
| Client message generator | Done | 8 format combos, weight-sorted |
| Standalone message CLI | Done | `generate_message.py` — regenerate from session files |
| Session save/resume | Done | Ctrl+C handling, JSON persistence |
| Answer revision | Done | Multi-select re-ask loop |
| Line-item editing | Done | Hours or cost override, auto-recompute |
| Run statistics | Done | stats.json + Rich panel |
| IDK fallback | Done | QUICK_DEFAULTS + client follow-up tracking |
| Demo mode | Done | `demo.py` with hardcoded scenario |
| CI pipeline | Not started | No GitHub Actions yet |
| Web UI | Not started | — |

---

## Known Bugs & Quirks

- **Fragile page count extraction:** `pdf_export.py:_get_page_count()` parses page count from line-item label strings via regex — breaks if label format changes
- **`generate_message.py` not tracked:** exists on disk but isn't in .gitignore or committed — will be lost on fresh clone unless committed
- **Venv quirk:** `.venv` on this machine lacks a `pip` binary; use `python3 -m pip install --target=...` instead
- **Quick mode extras gap:** `contact_form`, `blog_section`, `booking_system` are in `QUICK_DEFAULTS` but have no matching questions in `questions.json` — they're implicitly set via the quick mode "extras" checkbox
- **No input validation on text fields:** `client_name` and `additional_notes` accept any input including empty strings
- **FX rates are static:** `pricing.json` has hardcoded `USD_to_ILS: 3.75` — not auto-updated

---

## TODOs & Feature Ideas

- **CI pipeline** — GitHub Actions for pytest + linting on push
- **Web UI** — Streamlit or Flask wrapper for non-CLI users
- **PDF template theming** — custom colors/logos per client or brand
- **Quote comparison mode** — side-by-side view of two scenarios
- **XLSX export** — spreadsheet output alongside PDF
- **API mode** — JSON input → quote output (headless, no CLI)
- **More languages** — localization beyond EN/HE
- **Auto FX rates** — fetch live rates from an API
- **Session browser** — list and pick from multiple saved sessions (currently only offers the most recent)
- **Undo/redo for line-item edits** — currently edits are one-way
- **Question weight visualization** — show which unanswered questions have the most pricing impact
- **PDF preview in terminal** — render a text-mode preview before generating

---

## Testing

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run with coverage
.venv/bin/python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Run a specific test file
.venv/bin/python -m pytest tests/test_calculator.py -v
```

**Conventions:**
- Fixtures in `tests/conftest.py` (`questions`, `minimal_answers`)
- Parametric tests for cheaper-vs-expensive scenario comparisons
- Test file naming: `test_*.py`

---

## Claude Model Recommendations

| Task | Recommended Model | Why |
|------|-------------------|-----|
| Bug fixes, small features | **Sonnet** | Fast, accurate, cost-effective for targeted code changes |
| Documentation, README updates | **Sonnet** | Great at structured writing without overthinking |
| Architecture changes, new modules | **Opus** | Better at holding full-system context and design tradeoffs |
| Complex pricing logic changes | **Opus** | Multiplicative math + edge cases benefit from deeper reasoning |
| Quick questions, config edits | **Haiku** | Instant answers for simple lookups and tweaks |
| Test generation | **Sonnet** | Good balance of coverage thinking and speed |

For most day-to-day work on this project, **Sonnet is the default choice**. Switch to Opus for anything that touches `calculator.py` multiplier logic or cross-cutting architectural changes.
