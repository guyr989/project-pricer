"""
Pricing engine — reads answers dict and pricing.json config,
returns an itemized breakdown and final totals.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PRICING_PATH = Path(__file__).parent / "pricing.json"


def load_pricing() -> dict:
    with open(PRICING_PATH, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class LineItem:
    label: str
    hours: float = 0.0
    cost: float = 0.0
    is_recurring: bool = False
    recurring_period: str = "month"  # "month" or "year"
    note: str = ""


@dataclass
class PricingResult:
    currency: str
    hourly_rate: float
    line_items: list[LineItem] = field(default_factory=list)
    recurring_items: list[LineItem] = field(default_factory=list)

    base_hours: float = 0.0
    base_cost: float = 0.0

    rush_surcharge_pct: float = 0.0
    tech_multiplier_pct: float = 0.0
    client_difficulty_pct: float = 0.0
    risk_buffer_pct: float = 0.0
    overhead_pct: float = 0.0
    profit_margin_pct: float = 0.0
    ip_premium_pct: float = 0.0
    long_term_discount_pct: float = 0.0
    portfolio_discount_pct: float = 0.0
    vat_pct: float = 0.0

    subtotal_before_multipliers: float = 0.0
    subtotal_after_multipliers: float = 0.0
    pre_vat_total: float = 0.0
    vat_amount: float = 0.0
    final_total: float = 0.0

    # Secondary currency amounts (always show both ILS and USD)
    final_total_ils: float = 0.0
    final_total_usd: float = 0.0

    payment_schedule: str = ""
    client_name: str = ""
    project_type_label: str = ""
    additional_notes: str = ""


def recompute_totals(result: "PricingResult") -> "PricingResult":
    """
    Re-sum line_items and reapply all stored multiplier percentages.
    Called after manual line-item edits so totals stay consistent.
    """
    new_subtotal = sum(li.cost for li in result.line_items)
    result.subtotal_before_multipliers = new_subtotal

    combined_mult = (
        (1 + result.rush_surcharge_pct)
        * (1 + result.tech_multiplier_pct)
        * (1 + result.client_difficulty_pct)
        * (1 + result.risk_buffer_pct)
    )
    subtotal_after = new_subtotal * combined_mult
    result.subtotal_after_multipliers = subtotal_after

    pre_vat = subtotal_after * (1 + result.overhead_pct) * (1 + result.profit_margin_pct)
    pre_vat *= (1 + result.ip_premium_pct)
    total_discount = result.long_term_discount_pct + result.portfolio_discount_pct
    pre_vat *= (1 - total_discount)
    result.pre_vat_total = pre_vat

    result.vat_amount = pre_vat * result.vat_pct
    result.final_total = pre_vat + result.vat_amount

    # Recompute secondary currencies using the same FX rates
    cfg = load_pricing()
    usd_to_ils = cfg["currencies"]["fx_rates"]["USD_to_ILS"]
    eur_to_ils = cfg["currencies"]["fx_rates"]["EUR_to_ILS"]

    if result.currency == "ILS":
        result.final_total_ils = result.final_total
        result.final_total_usd = result.final_total / usd_to_ils
    elif result.currency == "USD":
        result.final_total_ils = result.final_total * usd_to_ils
        result.final_total_usd = result.final_total
    elif result.currency == "EUR":
        result.final_total_ils = result.final_total * eur_to_ils
        result.final_total_usd = result.final_total * (eur_to_ils / usd_to_ils)

    return result


def calculate(answers: dict[str, Any], questions: list[dict]) -> PricingResult:
    cfg = load_pricing()
    p = PricingResult(currency="ILS", hourly_rate=350.0)

    # -----------------------------------------------------------------
    # Resolve hourly rate and currency
    # -----------------------------------------------------------------
    currency = answers.get("currency", "ILS")
    p.currency = currency

    raw_rate = answers.get("dev_hourly_rate", 0)
    try:
        hourly_rate = float(raw_rate)
    except (ValueError, TypeError):
        hourly_rate = cfg["base_rates"]["developer_hourly_rate_ils"] if currency == "ILS" else cfg["base_rates"]["developer_hourly_rate_usd"]
    p.hourly_rate = hourly_rate

    def cost(hours: float) -> float:
        return hours * hourly_rate

    # FX for secondary display
    usd_to_ils = cfg["currencies"]["fx_rates"]["USD_to_ILS"]
    eur_to_ils = cfg["currencies"]["fx_rates"]["EUR_to_ILS"]

    def to_ils(amount: float) -> float:
        if currency == "ILS":
            return amount
        if currency == "USD":
            return amount * usd_to_ils
        if currency == "EUR":
            return amount * eur_to_ils
        return amount

    def to_usd(amount: float) -> float:
        if currency == "USD":
            return amount
        if currency == "ILS":
            return amount / usd_to_ils
        if currency == "EUR":
            return amount * (eur_to_ils / usd_to_ils)
        return amount

    # Quick lookup for question options by value
    q_by_id: dict[str, dict] = {q["id"]: q for q in questions}

    def get_option(question_id: str, selected_value: Any) -> dict | None:
        q = q_by_id.get(question_id)
        if not q or "options" not in q:
            return None
        for opt in q["options"]:
            if opt["value"] == selected_value:
                return opt
        return None

    # -----------------------------------------------------------------
    # 1. Base hours from project type
    # -----------------------------------------------------------------
    project_type_val = answers.get("project_type", "brochure")
    project_opt = get_option("project_type", project_type_val)
    base_hours = float(project_opt.get("base_hours", 40)) if project_opt else 40.0
    project_label = project_opt.get("label", project_type_val) if project_opt else project_type_val
    p.project_type_label = project_label

    p.line_items.append(LineItem(
        label=f"Base development — {project_label}",
        hours=base_hours,
        cost=cost(base_hours),
    ))

    # -----------------------------------------------------------------
    # 2. Extra pages beyond base
    # -----------------------------------------------------------------
    PAGE_BASE = {
        "landing_page": 1, "brochure": 6, "business": 14, "ecommerce": 10,
        "blog_magazine": 8, "web_app": 5, "directory": 12,
    }
    base_page_count = PAGE_BASE.get(project_type_val, 5)
    page_count = int(answers.get("page_count", base_page_count))
    extra_pages = max(0, page_count - base_page_count)
    if extra_pages > 0:
        extra_page_hours = float(extra_pages) * 1.5
        p.line_items.append(LineItem(
            label=f"Additional pages ({extra_pages} × 1.5h)",
            hours=extra_page_hours,
            cost=cost(extra_page_hours),
        ))

    # -----------------------------------------------------------------
    # 3. Redesign flag
    # -----------------------------------------------------------------
    if answers.get("is_redesign"):
        redesign_hours = base_hours * 0.20
        p.line_items.append(LineItem(
            label="Redesign audit & content migration (+20%)",
            hours=redesign_hours,
            cost=cost(redesign_hours),
        ))

    # -----------------------------------------------------------------
    # 4. Design
    # -----------------------------------------------------------------
    design_opt = get_option("design_source", answers.get("design_source", "developer_designs"))
    if design_opt:
        dh = float(design_opt.get("extra_hours", 0))
        if dh:
            p.line_items.append(LineItem(label=f"Design — {design_opt['label']}", hours=dh, cost=cost(dh)))

    brand_opt = get_option("has_brand_identity", answers.get("has_brand_identity", "full_brand"))
    if brand_opt:
        bh = float(brand_opt.get("extra_hours", 0))
        if bh:
            p.line_items.append(LineItem(label=f"Branding — {brand_opt['label']}", hours=bh, cost=cost(bh)))

    anim_opt = get_option("animations_level", answers.get("animations_level", "none"))
    if anim_opt:
        ah = float(anim_opt.get("extra_hours", 0))
        if ah:
            p.line_items.append(LineItem(label=f"Animations — {anim_opt['label']}", hours=ah, cost=cost(ah)))

    rev_opt = get_option("revision_rounds", answers.get("revision_rounds", "2"))
    if rev_opt:
        rh = float(rev_opt.get("extra_hours", 0))
        if rh:
            p.line_items.append(LineItem(label=f"Revision rounds — {rev_opt['label']}", hours=rh, cost=cost(rh)))

    # -----------------------------------------------------------------
    # 5. Content
    # -----------------------------------------------------------------
    content_opt = get_option("content_writer", answers.get("content_writer", "client"))
    if content_opt and content_opt.get("copywriting") is True:
        cph = float(cfg["additive_costs"]["copywriting_per_page_hours"])
        copy_hours = cph * max(page_count, 1)
        p.line_items.append(LineItem(label=f"Copywriting ({page_count} pages × {cph}h)", hours=copy_hours, cost=cost(copy_hours)))
    elif content_opt and content_opt.get("copywriting") == "partial":
        cph = float(cfg["additive_costs"]["copywriting_per_page_hours"]) * 0.5
        copy_hours = cph * max(page_count, 1)
        p.line_items.append(LineItem(label=f"Content refinement ({page_count} pages × {cph}h)", hours=copy_hours, cost=cost(copy_hours)))

    img_src_opt = get_option("image_source", answers.get("image_source", "client_provides"))
    if img_src_opt and img_src_opt.get("image_sourcing"):
        img_count = int(answers.get("image_count", 0))
        if img_count > 0:
            iph = float(cfg["additive_costs"]["image_sourcing_per_image_hours"])
            img_hours = iph * img_count
            p.line_items.append(LineItem(label=f"Image sourcing / editing ({img_count} × {iph}h)", hours=img_hours, cost=cost(img_hours)))

    if answers.get("has_video"):
        video_count = int(answers.get("video_count", 1))
        v_host_opt = get_option("video_hosting", answers.get("video_hosting", "youtube_vimeo"))
        hpv = float(v_host_opt.get("hours_per_video", 1)) if v_host_opt else 1.0
        video_hours = hpv * video_count
        label_suffix = v_host_opt["label"] if v_host_opt else "video"
        p.line_items.append(LineItem(label=f"Video integration ({video_count} × {hpv}h) — {label_suffix}", hours=video_hours, cost=cost(video_hours)))

    if answers.get("multilingual"):
        lang_count = int(answers.get("language_count", 2))
        extra_langs = max(0, lang_count - 1)
        if extra_langs > 0:
            # Tracked as a multiplier later; add a note line here
            p.line_items.append(LineItem(
                label=f"Multi-language support ({extra_langs} extra language(s))",
                hours=0,
                cost=0,
                note=f"+{extra_langs * 35}% added as multiplier below",
            ))

    # -----------------------------------------------------------------
    # 6. Technical
    # -----------------------------------------------------------------
    if answers.get("cms_required"):
        cms_opt = get_option("cms_type", answers.get("cms_type", "wordpress"))
        if cms_opt:
            ch = float(cms_opt.get("extra_hours", 12))
            p.line_items.append(LineItem(label=f"CMS setup — {cms_opt['label']}", hours=ch, cost=cost(ch)))

    if answers.get("database_required"):
        db_hours = 30.0
        p.line_items.append(LineItem(label="Custom database design + API", hours=db_hours, cost=cost(db_hours)))

    if answers.get("ecommerce_required"):
        ec_opt = get_option("ecommerce_platform", answers.get("ecommerce_platform", "woocommerce"))
        if ec_opt:
            ech = float(ec_opt.get("extra_hours", 35))
            p.line_items.append(LineItem(label=f"E-commerce — {ec_opt['label']}", hours=ech, cost=cost(ech)))

    if answers.get("user_accounts"):
        p.line_items.append(LineItem(label="User registration / authentication system", hours=20.0, cost=cost(20.0)))

    seo_opt = get_option("seo_level", answers.get("seo_level", "basic"))
    if seo_opt:
        sh = float(seo_opt.get("extra_hours", 0))
        if sh:
            p.line_items.append(LineItem(label=f"SEO — {seo_opt['label']}", hours=sh, cost=cost(sh)))

    integrations = answers.get("third_party_integrations", [])
    if isinstance(integrations, list):
        for iv in integrations:
            if iv == "none":
                continue
            int_opt = get_option("third_party_integrations", iv)
            if int_opt:
                ih = float(int_opt.get("hours", 0))
                if ih:
                    p.line_items.append(LineItem(label=f"Integration — {int_opt['label']}", hours=ih, cost=cost(ih)))

    # -----------------------------------------------------------------
    # 7. Hosting & domain (one-time costs)
    # -----------------------------------------------------------------
    domain_opt = get_option("domain_status", answers.get("domain_status", "owns_domain"))
    if domain_opt and domain_opt.get("domain_cost"):
        domain_cost_val = cfg["additive_costs"]["domain_purchase_ils"] if currency == "ILS" else cfg["additive_costs"]["domain_purchase_usd"]
        p.line_items.append(LineItem(label="Domain name purchase (1 year)", hours=0, cost=domain_cost_val, note="annual renewal not included"))

    hosting_opt = get_option("hosting_responsibility", answers.get("hosting_responsibility", "client_manages"))
    if hosting_opt and hosting_opt.get("hosting_type") in ("setup", "managed", "serverless"):
        setup_h = float(cfg["additive_costs"]["hosting_setup_hours"])
        p.line_items.append(LineItem(label="Hosting setup & configuration", hours=setup_h, cost=cost(setup_h)))

    if answers.get("backup_needed"):
        backup_h = float(cfg["additive_costs"]["backup_setup_hours"])
        p.line_items.append(LineItem(label="Backup solution setup", hours=backup_h, cost=cost(backup_h)))

    if answers.get("staging_needed"):
        staging_h = float(cfg["additive_costs"]["staging_environment_hours"])
        p.line_items.append(LineItem(label="Staging environment setup", hours=staging_h, cost=cost(staging_h)))

    # -----------------------------------------------------------------
    # 8. Training
    # -----------------------------------------------------------------
    training_opt = get_option("training_needed", answers.get("training_needed", "none"))
    if training_opt:
        sessions = int(training_opt.get("training_sessions", 0))
        if sessions:
            t_hours = sessions * float(cfg["additive_costs"]["training_per_session_hours"])
            p.line_items.append(LineItem(label=f"CMS training ({sessions} session(s))", hours=t_hours, cost=cost(t_hours)))

    # -----------------------------------------------------------------
    # 9. Recurring items (not in base calculation — shown separately)
    # -----------------------------------------------------------------
    traffic_opt = get_option("expected_traffic", answers.get("expected_traffic", "low"))
    hosting_tier = traffic_opt.get("hosting_tier", "shared") if traffic_opt else "shared"
    h_type = hosting_opt.get("hosting_type", "client") if hosting_opt else "client"
    if h_type in ("setup", "managed"):
        key_mo = f"{hosting_tier}_monthly_{'ils' if currency == 'ILS' else 'usd'}"
        monthly_hosting = cfg["hosting_estimates"].get(key_mo, 0)
        if monthly_hosting:
            p.recurring_items.append(LineItem(
                label=f"Hosting — {hosting_tier} server",
                cost=monthly_hosting,
                is_recurring=True,
                recurring_period="month",
                note="estimate — actual cost depends on provider",
            ))

    if answers.get("email_hosting"):
        email_count = int(answers.get("email_account_count", 1))
        key_email = f"email_hosting_per_account_monthly_{'ils' if currency == 'ILS' else 'usd'}"
        monthly_email = cfg["additive_costs"].get(key_email, 0) * email_count
        if monthly_email:
            p.recurring_items.append(LineItem(
                label=f"Email hosting ({email_count} account(s))",
                cost=monthly_email,
                is_recurring=True,
                recurring_period="month",
            ))

    maint_opt = get_option("maintenance_plan", answers.get("maintenance_plan", "none"))
    if maint_opt and maint_opt.get("retainer_key"):
        rk = maint_opt["retainer_key"]
        key_retainer = f"{rk}_monthly_{'ils' if currency == 'ILS' else 'usd'}"
        monthly_retainer = cfg["maintenance_retainer"].get(key_retainer, 0)
        if monthly_retainer:
            p.recurring_items.append(LineItem(
                label=f"Maintenance retainer — {maint_opt['label']}",
                cost=monthly_retainer,
                is_recurring=True,
                recurring_period="month",
            ))

    # -----------------------------------------------------------------
    # 10. Compute base total
    # -----------------------------------------------------------------
    total_hours = sum(li.hours for li in p.line_items)
    subtotal = sum(li.cost for li in p.line_items)
    p.base_hours = total_hours
    p.base_cost = subtotal
    p.subtotal_before_multipliers = subtotal

    # -----------------------------------------------------------------
    # 11. Apply multipliers
    # -----------------------------------------------------------------
    mult = cfg["multipliers"]

    # Rush
    deadline_val = answers.get("deadline", "no_rush")
    deadline_opt = get_option("deadline", deadline_val)
    rush_key = deadline_opt.get("rush_key", "no_rush") if deadline_opt else "no_rush"
    p.rush_surcharge_pct = mult["rush_surcharges"].get(rush_key, 0.0)

    # Tech familiarity
    fam_opt = get_option("tech_familiarity", answers.get("tech_familiarity", "expert"))
    fam_key = fam_opt.get("familiarity_key", "expert") if fam_opt else "expert"
    p.tech_multiplier_pct = mult["tech_familiarity"].get(fam_key, 0.0)

    # Client difficulty
    diff_opt = get_option("client_communication", answers.get("client_communication", "normal"))
    diff_key = diff_opt.get("difficulty_key", "normal") if diff_opt else "normal"
    p.client_difficulty_pct = mult["client_difficulty"].get(diff_key, 0.0)

    # Risk buffer
    risk_opt = get_option("project_risk", answers.get("project_risk", "medium"))
    risk_key = risk_opt.get("risk_key", "medium") if risk_opt else "medium"
    p.risk_buffer_pct = cfg["base_rates"]["risk_buffers"].get(risk_key, 0.15)

    # Multi-language multiplier
    ml_extra = 0.0
    if answers.get("multilingual"):
        lang_count = int(answers.get("language_count", 2))
        extra_langs = max(0, lang_count - 1)
        ml_extra = extra_langs * cfg["additive_costs"]["translation_per_language_multiplier"]

    combined_mult = (
        (1 + p.rush_surcharge_pct) *
        (1 + p.tech_multiplier_pct) *
        (1 + p.client_difficulty_pct) *
        (1 + p.risk_buffer_pct) *
        (1 + ml_extra)
    )
    p.subtotal_after_multipliers = subtotal * combined_mult

    # Overhead + profit
    raw_overhead = answers.get("overhead_percentage", cfg["base_rates"]["overhead_percentage"] * 100)
    raw_profit = answers.get("profit_margin", cfg["base_rates"]["profit_margin"] * 100)
    try:
        p.overhead_pct = float(raw_overhead) / 100.0
        p.profit_margin_pct = float(raw_profit) / 100.0
    except (ValueError, TypeError):
        p.overhead_pct = cfg["base_rates"]["overhead_percentage"]
        p.profit_margin_pct = cfg["base_rates"]["profit_margin"]

    pre_adjustments = p.subtotal_after_multipliers * (1 + p.overhead_pct) * (1 + p.profit_margin_pct)

    # IP transfer premium
    if answers.get("ip_transfer"):
        p.ip_premium_pct = mult["ip_transfer_premium"]
    else:
        p.ip_premium_pct = 0.0

    # Subcontractor markup
    if answers.get("subcontractors_needed"):
        pre_adjustments *= (1 + cfg["additive_costs"]["subcontractor_markup"])

    pre_adjustments *= (1 + p.ip_premium_pct)

    # Discounts
    if answers.get("long_term_client"):
        p.long_term_discount_pct = mult["long_term_client_discount"]
    if answers.get("portfolio_value"):
        p.portfolio_discount_pct = mult["portfolio_discount"]

    total_discount = p.long_term_discount_pct + p.portfolio_discount_pct
    pre_vat = pre_adjustments * (1 - total_discount)
    p.pre_vat_total = pre_vat

    # VAT
    vat_opt = get_option("vat_applicable", answers.get("vat_applicable", "none"))
    vat_key = vat_opt.get("vat_key", "none") if vat_opt else "none"
    p.vat_pct = cfg["vat"].get(vat_key, 0.0)
    p.vat_amount = pre_vat * p.vat_pct
    p.final_total = pre_vat + p.vat_amount

    # Secondary currency
    p.final_total_ils = to_ils(p.final_total)
    p.final_total_usd = to_usd(p.final_total)

    # Misc
    payment_opt = get_option("payment_schedule", answers.get("payment_schedule", "50_50"))
    p.payment_schedule = payment_opt["label"] if payment_opt else "50% upfront / 50% on delivery"
    p.client_name = answers.get("client_name", "")
    p.additional_notes = answers.get("additional_notes", "")

    return p
