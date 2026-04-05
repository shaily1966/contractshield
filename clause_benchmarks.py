# ══════════════════════════════════════════════════════════════
# CLAUSE BENCHMARKS — Canadian Market Standards
# Used by the benchmark engine to compare contract terms
# against industry-specific norms.
# ══════════════════════════════════════════════════════════════

CLAUSE_BENCHMARKS = {
    "liability_cap": {
        "SaaS / Technology": {"standard": "12 months of fees paid or payable", "floor": "6 months fees", "ceiling": "24 months fees", "note": "Uncapped liability is non-standard. Caps below 6 months fees are aggressive."},
        "Service Agreement": {"standard": "12 months of fees", "floor": "6 months fees", "ceiling": "Total contract value", "note": "Single-month caps heavily favour the service provider."},
        "Independent Contractor": {"standard": "6 months of fees", "floor": "3 months fees", "ceiling": "12 months fees", "note": "Ensure cap applies to both parties or is mutual."},
        "Employment Contract": {"standard": "N/A — statutory liability cannot be capped", "floor": "N/A", "ceiling": "N/A", "note": "ESA minimums are non-waivable."},
        "Commercial Lease": {"standard": "Total rent for remaining term", "floor": "12 months rent", "ceiling": "Uncapped for property damage", "note": "Landlord typically excludes caps for property damage."},
        "Construction Contract": {"standard": "Total contract value", "floor": "Contract value", "ceiling": "Uncapped for defects", "note": "Construction Act holdback rules apply."},
        "NDA / Confidentiality": {"standard": "Typically uncapped for breach of confidentiality", "floor": "12 months fees", "ceiling": "Uncapped", "note": "Confidentiality breach caps are unusual."},
        "Franchise Agreement": {"standard": "Initial franchise fee", "floor": "Franchise fee", "ceiling": "Total fees paid", "note": "Arthur Wishart Act disclosure claims may be uncapped."},
        "default": {"standard": "12 months of fees or contract value", "floor": "6 months", "ceiling": "24 months", "note": "General Canadian commercial standard."},
    },
    "indemnity": {
        "default": {"standard": "Mutual indemnification", "note": "One-sided indemnification is a significant departure from market norms. Indemnifying party should control defence."},
        "SaaS / Technology": {"standard": "Mutual. Provider indemnifies for IP infringement; customer indemnifies for misuse.", "note": "IP indemnity from the provider is market standard for SaaS."},
        "Service Agreement": {"standard": "Mutual indemnification for third-party claims arising from breach or negligence.", "note": "Service provider typically indemnifies for professional negligence."},
        "Independent Contractor": {"standard": "Contractor indemnifies for negligence and third-party IP claims. Client indemnifies for instruction-caused harm.", "note": "One-sided indemnity favouring client is common but negotiable."},
        "Construction Contract": {"standard": "Mutual. Contractor indemnifies for workmanship; owner indemnifies for site conditions.", "note": "Construction Act may override contractual indemnity terms."},
    },
    "termination_notice": {
        "default": {"standard": "30 days written notice", "floor": "15 days", "ceiling": "90 days", "note": "Less than 15 days is aggressive. More than 90 days is unusual outside long-term agreements."},
        "Employment Contract": {"standard": "Per ESA minimums plus common law reasonable notice (Bardal factors)", "floor": "ESA minimum", "ceiling": "24 months (common law cap per Hudson Bay)", "note": "Cannot contract below ESA minimums. Common law notice ~1 month per year of service."},
        "SaaS / Technology": {"standard": "30 days for convenience; immediate for cause", "floor": "30 days", "ceiling": "60 days", "note": "Annual contracts typically require 30-60 days notice before renewal date."},
        "Commercial Lease": {"standard": "Per lease term. Typically 6-12 months before renewal.", "floor": "3 months", "ceiling": "12 months", "note": "Early termination clauses require careful review of penalty provisions."},
    },
    "payment_terms": {
        "default": {"standard": "Net 30 days from invoice", "floor": "Net 15", "ceiling": "Net 60", "note": "Net 60+ is unfavourable to the payee. Net 15 or less is aggressive for the payor."},
        "Construction Contract": {"standard": "Net 30, subject to Construction Act prompt payment provisions", "floor": "Net 28 (statutory)", "ceiling": "Net 45", "note": "Ontario Construction Act mandates prompt payment timelines."},
    },
    "late_fees": {
        "default": {"standard": "1.5% per month (18% per annum)", "floor": "1% per month", "ceiling": "2% per month", "note": "Criminal Code s.347.1 (as amended by Bill C-46, effective Jan 1 2025): interest exceeding 35% APR is criminal for commercial lending. The original 60% APR threshold under s.347 applies to other credit arrangements. Late fees must be reviewed against the 35% commercial ceiling. Anything above 2%/month (24% APR) should be flagged for review."},
    },
    "non_compete": {
        "default": {"standard": "6-12 months, limited geographic scope, specific activity restriction", "floor": "6 months", "ceiling": "12 months (18 months in exceptional cases)", "note": "Ontario Bill 27 bans non-competes for employees (except C-suite on sale of business). For contractors, courts require reasonableness in time, geography, and scope."},
        "Employment Contract": {"standard": "BANNED in Ontario for employees (Bill 27). Other provinces: 6-12 months, narrow scope.", "floor": "Banned (ON)", "ceiling": "12 months", "note": "Non-solicitation of clients is generally more enforceable than non-compete."},
        "Franchise Agreement": {"standard": "Duration of franchise plus 1-2 years, within franchised territory", "floor": "Franchise term", "ceiling": "Franchise term plus 2 years", "note": "Franchise non-competes receive more judicial deference."},
    },
    "ip_ownership": {
        "default": {"standard": "Foreground IP assigned to client; background/pre-existing IP retained by creator with licence to client", "note": "Canada has no work-for-hire doctrine (unlike US). IP must be explicitly assigned. Moral rights must be explicitly waived."},
        "SaaS / Technology": {"standard": "Provider retains platform IP. Customer owns customer data. Custom development assigned to customer with provider retaining licence for generalized learnings.", "note": "Ensure pre-existing IP carve-out is included."},
        "Independent Contractor": {"standard": "Deliverable IP assigned to client on payment. Pre-existing tools and methodologies retained by contractor with licence.", "note": "Without explicit assignment, contractor owns all IP under Canadian law."},
    },
    "governing_law": {
        "default": {"standard": "Province where the principal commercial relationship exists or where the client is headquartered", "note": "Foreign governing law (especially US) in a Canadian transaction is a material risk factor. Mandatory arbitration in foreign jurisdiction significantly disadvantages Canadian party."},
    },
    "force_majeure": {
        "default": {"standard": "Explicit clause listing specific events. Must include: natural disaster, pandemic, government action, war. Duration trigger: 30-90 days before termination right.", "note": "Absence of force majeure clause is a material omission. Overly broad force majeure favouring one party is a negotiation point."},
    },
    "confidentiality_term": {
        "default": {"standard": "2-5 years from disclosure or termination, whichever is later", "floor": "2 years", "ceiling": "Indefinite for trade secrets", "note": "Indefinite confidentiality for all information (not just trade secrets) is aggressive."},
    },
    "auto_renewal": {
        "default": {"standard": "Written notice 30-60 days before renewal date to opt out", "note": "Auto-renewal without adequate notice period or with escalating terms is commercially unfavourable."},
    },
    "dispute_resolution": {
        "default": {"standard": "Negotiation, then mediation, then litigation or arbitration in the governing jurisdiction", "note": "Mandatory binding arbitration in a foreign jurisdiction is a significant risk factor for the Canadian party."},
    },
    "insurance": {
        "default": {"standard": "Commercial general liability $2M, professional liability (E&O) $1-5M depending on engagement value", "note": "Absence of insurance requirements transfers risk to the client."},
        "Construction Contract": {"standard": "CGL $5M, builder's risk, workers' compensation, wrap-up (OCIP/CCIP) for large projects", "note": "Construction projects require specialized insurance coverage."},
    },
}


def get_benchmark(clause_category, contract_type):
    """Look up the market benchmark for a clause category and contract type."""
    cat_benchmarks = CLAUSE_BENCHMARKS.get(clause_category, {})
    # Try specific contract type first, then fall back to default
    benchmark = cat_benchmarks.get(contract_type, cat_benchmarks.get("default", {}))
    return benchmark


def format_benchmarks_for_prompt(contract_type):
    """Format all relevant benchmarks into a string for the system prompt."""
    lines = []
    for clause_key, type_dict in CLAUSE_BENCHMARKS.items():
        bench = type_dict.get(contract_type, type_dict.get("default", {}))
        if bench:
            label = clause_key.replace("_", " ").title()
            std = bench.get("standard", "N/A")
            note = bench.get("note", "")
            floor_val = bench.get("floor", "")
            ceiling_val = bench.get("ceiling", "")
            line = f"  {label}: Standard = {std}"
            if floor_val: line += f" | Floor = {floor_val}"
            if ceiling_val: line += f" | Ceiling = {ceiling_val}"
            if note: line += f" | Note: {note}"
            lines.append(line)
    return "\n".join(lines)
