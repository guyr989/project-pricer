# freelance-quote-cli

A terminal CLI tool for freelance web developers to calculate fair project pricing and generate professional PDF quotes — in English or Hebrew.

---

## Features

- **~50-question guided flow** — split into client-facing and internal developer sections
- **Smart conditional branching** — only asks relevant follow-up questions
- **Full pricing engine** — base hours + rush surcharges, risk buffers, overhead, profit margin, VAT (Israeli 18% or other)
- **Editable results** — adjust individual line item hours/costs before generating the PDF
- **Answer revision** — go back and change any answer before the final calculation
- **Session save/resume** — Ctrl+C at any time to save progress and continue later
- **Dual-currency output** — always shows totals in both ILS (₪) and USD ($)
- **PDF quotes** — professional layout in English (LTR) or Hebrew RTL (Heebo font)
- **Run statistics** — cumulative stats panel shown at the end of every session
- **File logging** — all activity logged to `logs/calculator.log`

---

## Requirements

- Python 3.11+
- `gh` CLI (only needed for `git_setup.py`) — install from https://cli.github.com

---

## Installation

```bash
# Clone or download the project, then:
pip install -r requirements.txt
```

> On Debian/Ubuntu systems that restrict system pip, use:
> ```bash
> pip install --break-system-packages -r requirements.txt
> ```
> Or create a virtual environment first:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt
> ```

---

## Usage

### Run the calculator

```bash
python3 main.py
```

The tool guides you through two sections:

1. **Client questions** — project type, design, content, technical requirements, hosting, business terms
2. **Developer self-assessment** — hourly rate, tech familiarity, client difficulty, risk level, margins

At the end you can:
- Edit individual line items (override hours or cost)
- Revise any earlier answers
- Choose English or Hebrew PDF output

### Set up git + push to GitHub (one-time)

```bash
python3 git_setup.py
```

Offers several repo name suggestions, optionally renames the project directory, then runs `git init` and pushes to a new GitHub repository via the `gh` CLI.

---

## Customisation

### Edit questions — `questions.json`

Each question entry:
```json
{
  "id": "unique_id",
  "category": "scope | design | content | technical | hosting | business | internal",
  "label": "Question shown in English",
  "label_he": "שאלה בעברית",
  "type": "yes_no | choice | multi_choice | number | text",
  "options": [
    { "value": "option_value", "label": "Display label", "label_he": "תווית עברית", "base_hours": 20 }
  ],
  "condition": { "question_id": "parent_question_id", "value": true },
  "internal_only": false
}
```

- Set `"internal_only": true` to keep a question out of the client-facing section
- Set `"condition"` to show a question only when a parent answer matches

### Edit rates — `pricing.json`

Key fields to customise:
```json
{
  "base_rates": {
    "developer_hourly_rate_ils": 350,
    "overhead_percentage": 0.15,
    "profit_margin": 0.25
  },
  "currencies": {
    "fx_rates": { "USD_to_ILS": 3.75 }
  },
  "vat": { "israel": 0.18 }
}
```

---

## Output Structure

Every run creates a folder under `outputs/`:

```
outputs/
└── client_name_20260602/
    ├── quote_20260602_business_en.pdf
    └── quote_20260602_business_he.pdf

sessions/
└── session_20260602_143022.json   ← saved progress (resumed on next run)

logs/
└── calculator.log                  ← full debug log

stats.json                          ← cumulative run history (local only)
```

---

## Statistics

After every completed run, a stats panel is shown summarising all your historical quotes:

- Total quotes generated
- Most common project type
- Average price (ILS + USD)
- Average estimated hours
- Rush job percentage
- Most common CMS
- Top integrations used

Stats are stored in `stats.json` (excluded from git by default).

---

## Licence

MIT — free to use, modify, and distribute.
