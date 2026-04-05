# ══════════════════════════════════════════════════════════════
# DEAL CONTEXT ENGINE — v12.1
#
# Provides structured deal context that dynamically adjusts:
#   • Benchmark thresholds (floor/standard/ceiling) based on
#     contract value, industry risk tier, and counterparty type
#   • Precedent clause variable values (months, amounts, days)
#   • Risk weight multipliers per clause category
#   • Narrative context injected into the system prompt
#
# This is the layer that makes recommendations feel tailored
# rather than generic. A $500k SaaS enterprise deal gets
# different liability cap guidance than a $15k consulting gig.
# ══════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import Optional
import math
import re

# ── Industry risk tiers ──────────────────────────────────────
# HIGH = significant liability exposure, regulated, or IP-heavy
# MEDIUM = standard commercial services
# LOW = low-value, commodity, or low-regulatory environments
INDUSTRY_RISK_TIERS = {
    "Financial Services / Banking":    "HIGH",
    "Healthcare / Life Sciences":      "HIGH",
    "Construction / Engineering":      "HIGH",
    "Technology / SaaS":               "HIGH",
    "Legal / Professional Services":   "HIGH",
    "Government / Public Sector":      "HIGH",
    "Manufacturing / Industrial":      "MEDIUM",
    "Real Estate":                     "MEDIUM",
    "Retail / Consumer":               "MEDIUM",
    "Media / Entertainment":           "MEDIUM",
    "Hospitality / Food & Beverage":   "MEDIUM",
    "Non-Profit / Charity":            "LOW",
    "Education":                       "LOW",
    "Staffing / Recruitment":          "LOW",
    "General / Other":                 "MEDIUM",
}

# ── Counterparty type risk modifiers ────────────────────────
COUNTERPARTY_RISK = {
    "Large Enterprise (500+ employees)":  1.3,   # higher stakes, more aggressive terms
    "Mid-Market (50-500 employees)":      1.1,
    "SMB (< 50 employees)":              1.0,
    "Startup / Early Stage":             0.9,   # less aggressive, but cash risk
    "Government / Crown Corporation":    1.2,   # strict statutory requirements
    "Individual / Sole Proprietor":      0.85,
    "Non-Profit":                        0.8,
}

# ── Risk weights per clause category ────────────────────────
# Base weights (sum to 100). Adjusted by industry tier.
BASE_RISK_WEIGHTS = {
    "liability_cap":             25,
    "indemnity":                 20,
    "ip_ownership":              15,
    "termination":               10,
    "governing_law":              8,
    "non_compete":                7,
    "confidentiality":            5,
    "payment_terms":              4,
    "data_protection":            3,
    "force_majeure":              1,
    "dispute_resolution":         1,
    "auto_renewal":               1,
}

# Industry-specific weight multipliers
INDUSTRY_WEIGHT_OVERRIDES = {
    "Technology / SaaS": {
        "ip_ownership": 2.0,       # IP is core asset
        "data_protection": 2.5,    # PIPEDA / privacy critical
        "liability_cap": 1.2,
    },
    "Construction / Engineering": {
        "liability_cap": 1.5,      # defect exposure
        "payment_terms": 1.8,      # Construction Act holdback
        "termination": 1.3,
        "force_majeure": 2.0,      # site conditions
    },
    "Healthcare / Life Sciences": {
        "indemnity": 1.8,          # patient/liability exposure
        "data_protection": 2.5,    # PHI / PHIPA
        "governing_law": 1.5,
    },
    "Financial Services / Banking": {
        "governing_law": 2.0,      # regulatory jurisdiction critical
        "data_protection": 2.0,
        "liability_cap": 1.5,
    },
    "Employment Contract": {
        "non_compete": 2.5,        # Bill 27 ban — high risk if included
        "termination": 2.0,        # ESA floors
        "ip_ownership": 1.5,
    },
}


@dataclass
class DealContext:
    """Structured deal context that drives dynamic recommendations."""
    contract_value_cad: Optional[float] = None     # e.g. 250000.0
    annual_fees_cad:    Optional[float] = None     # recurring fee base for caps
    industry:           str = "General / Other"
    counterparty_type:  str = "SMB (< 50 employees)"
    client_is_vendor:   bool = False               # True = client selling services
    risk_tolerance:     str = "Standard"           # "Conservative" | "Standard" | "Aggressive"
    duration_months:    Optional[int] = None       # contract term in months
    is_template_deal:   bool = False               # True = high-volume, standardised
    province:           str = "Ontario"            # governing law — Quebec triggers CCQ adjustments

    # Derived fields populated by post_init
    industry_risk_tier:    str = field(default="MEDIUM", init=False)
    counterparty_modifier: float = field(default=1.0, init=False)
    deal_size_tier:        str = field(default="MEDIUM", init=False)
    adjusted_weights:      dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.industry_risk_tier = INDUSTRY_RISK_TIERS.get(self.industry, "MEDIUM")
        self.counterparty_modifier = COUNTERPARTY_RISK.get(self.counterparty_type, 1.0)

        # Validate and clamp contract value — reject negatives, treat zero as None
        if self.contract_value_cad is not None:
            if self.contract_value_cad < 0:
                # Negative values are data-entry errors; treat as unknown
                self.contract_value_cad = None
            elif self.contract_value_cad == 0:
                self.contract_value_cad = None  # zero means "not provided"

        if self.annual_fees_cad is not None:
            if self.annual_fees_cad < 0:
                self.annual_fees_cad = None
            elif self.annual_fees_cad == 0:
                self.annual_fees_cad = None

        # Deal size tiers — UNKNOWN when no value provided
        cv = self.contract_value_cad
        if cv is None:
            self.deal_size_tier = "UNKNOWN"
        elif cv >= 1_000_000:
            self.deal_size_tier = "ENTERPRISE"
        elif cv >= 100_000:
            self.deal_size_tier = "LARGE"
        elif cv >= 25_000:
            self.deal_size_tier = "MEDIUM"
        else:
            self.deal_size_tier = "SMALL"

        # Compute adjusted risk weights
        overrides = INDUSTRY_WEIGHT_OVERRIDES.get(self.industry, {})
        weights = {}
        for clause, base_w in BASE_RISK_WEIGHTS.items():
            mult = overrides.get(clause, 1.0)
            if self.industry_risk_tier == "HIGH":
                mult *= 1.1
            weights[clause] = round(base_w * mult)
        # Normalise to 100
        total = sum(weights.values())
        if total > 0:
            self.adjusted_weights = {k: round(v * 100 / total) for k, v in weights.items()}
        else:
            self.adjusted_weights = BASE_RISK_WEIGHTS.copy()

        # Warn on unrecognised input values that silently fall back to defaults
        import logging as _log
        _logger = _log.getLogger("contractcheck_audit")
        if self.industry not in INDUSTRY_RISK_TIERS:
            _logger.warning(
                f"DealContext: unrecognised industry {self.industry!r} — "
                f"falling back to MEDIUM risk tier")
        if self.counterparty_type not in COUNTERPARTY_RISK:
            _logger.warning(
                f"DealContext: unrecognised counterparty_type {self.counterparty_type!r} — "
                f"falling back to modifier 1.0")
        if self.duration_months is not None and (
                not isinstance(self.duration_months, int) or self.duration_months <= 0):
            _logger.warning(
                f"DealContext: invalid duration_months {self.duration_months!r} — ignoring")
            self.duration_months = None

        # Quebec civil law adjustments — CCQ principles affect relative clause importance
        if self.province == "Quebec":
            # CCQ 1437: abusive clauses doctrine makes indemnity more scrutinised
            self.adjusted_weights["indemnity"] = round(
                self.adjusted_weights.get("indemnity", 20) * 1.3)
            # CCQ 1474: cannot exclude liability for bodily injury or gross fault
            # → limitation of liability clauses need stricter review
            self.adjusted_weights["liability_cap"] = round(
                self.adjusted_weights.get("liability_cap", 25) * 1.2)
            # CCQ 2089: non-compete clauses strictly scrutinised
            self.adjusted_weights["non_compete"] = round(
                self.adjusted_weights.get("non_compete", 7) * 2.0)
            # CCQ 1375: good faith mandatory — governing law critical to preserve
            self.adjusted_weights["governing_law"] = round(
                self.adjusted_weights.get("governing_law", 8) * 1.5)


def compute_dynamic_thresholds(ctx: DealContext, clause_category: str) -> dict:
    """
    Return dynamically adjusted floor/standard/ceiling for a clause category,
    based on deal context. Returns a dict with 'floor', 'standard', 'ceiling',
    and 'rationale' explaining the adjustment.
    """
    base = _BASE_THRESHOLDS.get(clause_category, {})
    # Return base thresholds unchanged when no deal context value was provided
    # (contract_value_cad is None when zero, negative, or not entered).
    if not base or ctx.deal_size_tier == "UNKNOWN" or ctx.contract_value_cad is None:
        return dict(base)  # return a copy so callers can't mutate the base

    # Quebec-specific threshold adjustments
    if ctx.province == "Quebec":
        if clause_category == "non_compete":
            # CCQ 2089 requires all three elements — courts are stricter
            base = dict(base)
            base["standard_months"] = min(base.get("standard_months", 12), 12)
            base["ceiling_months"]  = 18  # Quebec courts rarely enforce > 18 months
            base["rationale_note"]  = "CCQ 2089: must be limited in time AND territory AND activity"
        elif clause_category == "confidentiality_term":
            # Quebec prescription is 3 years (CCQ 2925) not 2
            base = dict(base)
            base["standard_years"] = 3
            base["floor_years"]    = 2
        elif clause_category == "late_fees":
            # Quebec courts may reduce excessive penalties under CCQ 1623
            base = dict(base)
            base["ceiling_pct_month"] = 1.5  # more conservative ceiling in QC

    result = dict(base)
    rationale_parts = []
    cv = ctx.contract_value_cad
    af = ctx.annual_fees_cad or cv
    tier = ctx.deal_size_tier
    rtol = ctx.risk_tolerance

    if clause_category == "liability_cap":
        # Scale cap recommendation to deal size
        if tier == "ENTERPRISE":
            result["standard_months"] = 24
            result["floor_months"]    = 12
            result["ceiling_months"]  = 36
            rationale_parts.append("Enterprise deal: higher cap recommended")
        elif tier == "LARGE":
            result["standard_months"] = 18
            result["floor_months"]    = 12
            result["ceiling_months"]  = 24
        elif tier == "SMALL":
            result["standard_months"] = 6
            result["floor_months"]    = 3
            result["ceiling_months"]  = 12
            rationale_parts.append("Small deal: shorter cap period acceptable")

        if ctx.industry_risk_tier == "HIGH":
            result["floor_months"] = max(result.get("floor_months", 6), 12)
            rationale_parts.append(f"High-risk industry ({ctx.industry}): floor raised to 12 months")

        if rtol == "Conservative":
            result["floor_months"] = result.get("floor_months", 6) + 6
            rationale_parts.append("Conservative risk tolerance: floor increased by 6 months")
        elif rtol == "Aggressive":
            result["standard_months"] = max(result.get("standard_months", 12) - 6, 3)
            rationale_parts.append("Aggressive risk tolerance: standard reduced by 6 months")

        # Add dollar amounts for clarity
        if af:
            std_m = result.get("standard_months", 12)
            fl_m  = result.get("floor_months", 6)
            ceil_m = result.get("ceiling_months", 24)
            result["standard_cad"] = round(af * std_m / 12)
            result["floor_cad"]    = round(af * fl_m / 12)
            result["ceiling_cad"]  = round(af * ceil_m / 12)

    elif clause_category == "termination_notice":
        if tier in ("ENTERPRISE", "LARGE"):
            result["standard_days"] = 60
            result["floor_days"]    = 30
            rationale_parts.append("Large deal: longer notice period expected")
        elif tier == "SMALL":
            result["standard_days"] = 30
            result["floor_days"]    = 15
        if ctx.duration_months and ctx.duration_months <= 3:
            result["standard_days"] = min(result.get("standard_days", 30), 15)
            rationale_parts.append("Short-term contract: reduced notice acceptable")

    elif clause_category == "payment_terms":
        if tier == "ENTERPRISE" and not ctx.client_is_vendor:
            result["standard_days"] = 45
            result["ceiling_days"]  = 60
            rationale_parts.append("Enterprise buyers commonly negotiate Net-45")
        elif tier == "SMALL":
            result["standard_days"] = 14
            result["floor_days"]    = 7
            rationale_parts.append("Small deal: shorter payment terms protect cash flow")

    elif clause_category == "late_fees":
        if ctx.industry == "Construction / Engineering":
            result["note"] = (
                "Ontario Construction Act mandates prompt payment. "
                "Late interest under Construction Act is at prescribed rate. "
                "Criminal Code s.347.1 commercial cap 35% APR (Bill C-46, Jan 1 2025) applies.")

    elif clause_category == "non_compete":
        if ctx.industry_risk_tier == "HIGH":
            result["standard_months"] = 12
            result["ceiling_months"]  = 18
            rationale_parts.append(f"High-risk industry: longer non-compete may be justified")
        if tier == "ENTERPRISE":
            result["standard_months"] = 18
            rationale_parts.append("Enterprise sale-of-business context: 18 months arguable")

    result["rationale"] = "; ".join(rationale_parts) if rationale_parts else ""
    return result


# ── Base numeric thresholds (fallback when no deal context) ──
_BASE_THRESHOLDS = {
    "liability_cap": {
        "floor_months": 6, "standard_months": 12, "ceiling_months": 24,
        "standard_cad": None, "floor_cad": None, "ceiling_cad": None,
    },
    "termination_notice": {
        "floor_days": 15, "standard_days": 30, "ceiling_days": 90,
    },
    "payment_terms": {
        "floor_days": 15, "standard_days": 30, "ceiling_days": 60,
    },
    "non_compete": {
        "floor_months": 6, "standard_months": 12, "ceiling_months": 18,
    },
    "late_fees": {
        "floor_pct_month": 1.0, "standard_pct_month": 1.5, "ceiling_pct_month": 2.0,
        "max_apr": 35.0,  # Bill C-46 / s.347.1: 35% APR cap for commercial lending (Jan 1 2025)
    },
    "confidentiality_term": {
        "floor_years": 2, "standard_years": 3, "ceiling_years": 5,
    },
}


def format_deal_context_for_prompt(ctx: DealContext) -> str:
    """
    Format deal context as a structured section to inject into the system prompt.
    The AI uses this to calibrate all recommendations to the specific deal.
    """
    lines = ["DEAL CONTEXT — calibrate ALL recommendations to this specific deal:\n"]

    if ctx.contract_value_cad:
        lines.append(f"Contract Value: CAD ${ctx.contract_value_cad:,.0f} ({ctx.deal_size_tier} deal)")
    if ctx.annual_fees_cad:
        lines.append(f"Annual Fees: CAD ${ctx.annual_fees_cad:,.0f}")
    lines.append(f"Industry: {ctx.industry} (Risk Tier: {ctx.industry_risk_tier})")
    lines.append(f"Counterparty Type: {ctx.counterparty_type}")
    lines.append(f"Client Position: {'Vendor/Service Provider' if ctx.client_is_vendor else 'Purchaser/Client'}")
    lines.append(f"Risk Tolerance: {ctx.risk_tolerance}")
    if ctx.duration_months:
        lines.append(f"Contract Duration: {ctx.duration_months} months")

    lines.append("\nDYNAMIC THRESHOLDS (use these instead of generic market benchmarks):")

    for cat in ["liability_cap","termination_notice","payment_terms","non_compete","late_fees"]:
        thresh = compute_dynamic_thresholds(ctx, cat)
        if not thresh: continue
        label = cat.replace("_", " ").title()
        parts = []
        if thresh.get("floor_months"): parts.append(f"Floor={thresh['floor_months']}mo")
        if thresh.get("standard_months"): parts.append(f"Standard={thresh['standard_months']}mo")
        if thresh.get("ceiling_months"): parts.append(f"Ceiling={thresh['ceiling_months']}mo")
        if thresh.get("floor_days"): parts.append(f"Floor={thresh['floor_days']}d")
        if thresh.get("standard_days"): parts.append(f"Standard={thresh['standard_days']}d")
        if thresh.get("ceiling_days"): parts.append(f"Ceiling={thresh['ceiling_days']}d")
        if thresh.get("floor_pct_month"): parts.append(f"Floor={thresh['floor_pct_month']}%/mo")
        if thresh.get("standard_pct_month"): parts.append(f"Standard={thresh['standard_pct_month']}%/mo")
        if thresh.get("standard_cad"): parts.append(f"Standard≈CAD${thresh['standard_cad']:,}")
        if thresh.get("floor_cad"): parts.append(f"Floor≈CAD${thresh['floor_cad']:,}")
        if thresh.get("rationale"): parts.append(f"[{thresh['rationale']}]")
        if parts:
            lines.append(f"  {label}: {' | '.join(parts)}")

    lines.append("\nRISK WEIGHTS (clause importance for this deal — higher = flag more aggressively):")
    sorted_weights = sorted(ctx.adjusted_weights.items(), key=lambda x: -x[1])
    for clause, weight in sorted_weights[:8]:
        label = clause.replace("_", " ").title()
        bar = "█" * (weight // 5) + "░" * ((20 - weight // 5))
        lines.append(f"  {label}: {weight} pts  {bar}")

    # Quebec civil law specific section
    if ctx.province == "Quebec":
        lines.append("\nQUEBEC CIVIL LAW — MANDATORY ADJUSTMENTS (CCQ applies):")
        lines.append("  CCQ 1375: Good faith mandatory in all contracts — clause must be balanced.")
        lines.append("  CCQ 1437: Courts may void abusive clauses in contracts of adhesion.")
        lines.append("  CCQ 1474: CANNOT exclude liability for bodily injury or gross fault — any such clause is VOID.")
        lines.append("  CCQ 2089: Non-compete clauses must be limited in time, territory, AND activity type — all three.")
        lines.append("  CCQ 1623: Courts may reduce excessive penalty/liquidated damages clauses.")
        lines.append("  Prescription: 3 years (CCQ 2925) — NOT the 2-year Ontario/BC limitation period.")
        lines.append("  Law 25 (Quebec privacy law) applies — stricter than PIPEDA in several respects.")
        lines.append("  Charter of the French Language (Bill 96): consumer contracts MUST be in French.")
        lines.append("  When flagging issues, cite CCQ articles, not common law precedents.")
        lines.append("  CRITICAL: If governing law is NOT Quebec despite Quebec parties, flag as HIGH risk")
        lines.append("  because CCQ mandatory rules (1375, 1437, 1474, 2089) apply regardless of choice-of-law.")

    lines.append(
        "\nIMPORTANT: When proposing replacement clauses, use the DYNAMIC THRESHOLDS above, "
        "not generic market figures. A liability cap recommendation must cite the dollar amount "
        f"(e.g. '≈CAD${int(ctx.annual_fees_cad or 0):,} = {compute_dynamic_thresholds(ctx, 'liability_cap').get('standard_months', 12)} months annual fees') "
        "rather than just 'X months of fees'."
    )

    return "\n".join(lines)


def compute_clause_risk_score(clause_category: str, contract_provision: str,
                               ctx: DealContext) -> dict:
    """
    Score a specific clause provision against dynamic thresholds.
    Returns: {status: GREEN|AMBER|RED, score: 0-10, rationale: str}
    This is called by the Python layer, not the AI — giving an objective
    pre-AI score that feeds into the prompt as ground truth.
    """
    thresh = compute_dynamic_thresholds(ctx, clause_category)
    provision = contract_provision.lower().strip()
    weight = ctx.adjusted_weights.get(clause_category, 10)

    if clause_category == "liability_cap":
        # Try to extract a month count from the provision
        month_match = re.search(r'(\d+)\s*month', provision)
        dollar_match = re.search(r'\$\s*([\d,]+)', provision)

        if "uncapped" in provision or "unlimited" in provision or "no limit" in provision:
            return {"status": "RED", "score": weight,
                    "rationale": f"Uncapped liability — no limit at all. Standard for this deal: {thresh.get('standard_months',12)} months fees."}

        if month_match:
            months = int(month_match.group(1))
            floor_m  = thresh.get("floor_months", 6)
            std_m    = thresh.get("standard_months", 12)
            if months < floor_m:
                return {"status": "RED", "score": round(weight * 0.9),
                        "rationale": f"{months} months is below floor of {floor_m} months for this deal size."}
            elif months < std_m:
                return {"status": "AMBER", "score": round(weight * 0.5),
                        "rationale": f"{months} months is below standard of {std_m} months but above floor."}
            else:
                return {"status": "GREEN", "score": 0,
                        "rationale": f"{months} months meets or exceeds standard of {std_m} months."}

        if dollar_match:
            amount = float(dollar_match.group(1).replace(",",""))
            std_cad = thresh.get("standard_cad")
            if std_cad and amount < thresh.get("floor_cad", std_cad * 0.5):
                return {"status": "RED", "score": round(weight * 0.9),
                        "rationale": f"CAD ${amount:,.0f} is below the deal-calibrated floor of CAD ${thresh.get('floor_cad',0):,.0f}."}
            elif std_cad and amount < std_cad:
                return {"status": "AMBER", "score": round(weight * 0.5),
                        "rationale": f"CAD ${amount:,.0f} is below deal-calibrated standard of CAD ${std_cad:,.0f}."}
            elif std_cad:
                return {"status": "GREEN", "score": 0,
                        "rationale": f"CAD ${amount:,.0f} meets deal-calibrated standard."}

    elif clause_category == "payment_terms":
        day_match = re.search(r'net[\s-]?(\d+)', provision)
        if day_match:
            days = int(day_match.group(1))
            std_d = thresh.get("standard_days", 30)
            ceil_d = thresh.get("ceiling_days", 60)
            # From client_is_vendor perspective: longer is worse (they wait longer to be paid)
            if ctx.client_is_vendor:
                if days > ceil_d:
                    return {"status": "RED", "score": round(weight * 0.8),
                            "rationale": f"Net-{days} exceeds ceiling of Net-{ceil_d} — unfavourable to payee."}
                elif days > std_d:
                    return {"status": "AMBER", "score": round(weight * 0.4),
                            "rationale": f"Net-{days} is above standard of Net-{std_d}."}
                else:
                    return {"status": "GREEN", "score": 0,
                            "rationale": f"Net-{days} is at or below standard of Net-{std_d}."}

    elif clause_category == "late_fees":
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*per\s*month', provision)
        apr_match  = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:per annum|per year|annually)', provision)
        if pct_match:
            pct = float(pct_match.group(1))
            if pct > 2.0:
                return {"status": "RED", "score": weight,
                        "rationale": f"{pct}%/month ({pct*12:.0f}% APR). Bill C-46 / s.347.1 commercial lending ceiling: 35% APR (effective Jan 1 2025). Original s.347 ceiling: 60% APR. "}
            elif pct > 1.5:
                return {"status": "AMBER", "score": round(weight * 0.4),
                        "rationale": f"{pct}%/month is above market standard of 1.5%/month."}
            else:
                return {"status": "GREEN", "score": 0,
                        "rationale": f"{pct}%/month is within market standard."}

    # Default: unknown provision — flag for human review
    return {"status": "AMBER", "score": round(weight * 0.3),
            "rationale": "Could not extract numeric terms. Manual review required."}


def get_variable_values(ctx: DealContext, clause_category: str) -> dict:
    """
    Return the variable values to inject into a precedent clause template.
    Templates use {variable_name} placeholders.
    """
    thresh = compute_dynamic_thresholds(ctx, clause_category)
    af_str = f"CAD ${ctx.annual_fees_cad:,.0f}" if ctx.annual_fees_cad else "the annual fees"
    cv_str = f"CAD ${ctx.contract_value_cad:,.0f}" if ctx.contract_value_cad else "the contract value"

    vars_map = {
        # Liability cap
        "liability_cap_months":      str(thresh.get("standard_months", 12)),
        "liability_cap_floor_months":str(thresh.get("floor_months", 6)),
        "liability_cap_amount":      f"CAD ${thresh.get('standard_cad'):,}" if thresh.get("standard_cad") else f"{thresh.get('standard_months',12)} months of annual fees",
        "annual_fees":               af_str,
        "contract_value":            cv_str,
        # Notice periods
        "notice_days":               str(thresh.get("standard_days", 30)),
        "notice_floor_days":         str(thresh.get("floor_days", 15)),
        "cure_period_days":          "15",
        # Non-compete
        "non_compete_months":        str(thresh.get("standard_months", 12)),
        "non_solicitation_months":   "12",
        # Payment
        "payment_days":              str(thresh.get("standard_days", 30)),
        "late_fee_pct":              "1.5",
        # late_fee_pct_x12 = annual equivalent of monthly rate (used in payment clause template)
        "late_fee_pct_x12":          f"{1.5 * 12:.1f}",  # 18.0
        # Confidentiality
        "confidentiality_years":     "5" if ctx.industry_risk_tier == "HIGH" else "3",
        # Auto-renewal
        "renewal_notice_days":       "60" if ctx.deal_size_tier in ("ENTERPRISE","LARGE") else "30",
        "initial_term":              f"{ctx.duration_months} months" if ctx.duration_months else "one (1) year",
        # Insurance
        "cgl_amount":                "5,000,000" if ctx.industry_risk_tier == "HIGH" else "2,000,000",
        "eo_amount":                 "5,000,000" if ctx.deal_size_tier in ("ENTERPRISE","LARGE") else "1,000,000",
    }
    return vars_map
