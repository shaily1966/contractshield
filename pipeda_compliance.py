# ══════════════════════════════════════════════════════════════
# PIPEDA COMPLIANCE MODULE — ContractCheck Pro v12.5
#
# Three components addressing the gaps identified in the PIPEDA
# analysis:
#
#   1. PI Detection — scans contract text for personal information
#      patterns before the API call and warns the lawyer.
#   2. Retainer Clause Template — plain-English disclosure for
#      client retainer agreements.
#   3. Retention utilities — enforce matter store expiry.
#
# ══════════════════════════════════════════════════════════════
import re
from dataclasses import dataclass, field
from typing import List


# ── 1. PERSONAL INFORMATION DETECTION ────────────────────────

@dataclass
class PIFinding:
    category:    str
    pattern_key: str
    matches:     List[str]
    count:       int
    risk:        str   # "HIGH" | "MEDIUM" | "LOW"
    guidance:    str


# Regex patterns keyed by PI category.
# All patterns are case-insensitive and match common Canadian formats.
PI_PATTERNS = {
    "SIN (Social Insurance Number)": {
        # Require SIN-related context words to reduce false positives on invoice/serial numbers.
        # Matches: "SIN: 123 456 789", "social insurance number 123-456-789",
        #          "sin no. 123 456 789", "s.i.n. 123456789"
        # Does NOT match: bare 9-digit numbers, phone numbers, file references.
        "regex":    r'(?:\bSIN\b|social\s+insurance\s+(?:number|no\.?)|\bs\.?i\.?n\.?\s*(?:no\.?|number|#)?)\s*[:\-]?\s*\d{3}[-\s]?\d{3}[-\s]?\d{3}\b',
        "risk":     "HIGH",
        "guidance": (
            "Social Insurance Numbers are among the most sensitive PI under PIPEDA. "
            "Strongly consider redacting before upload. If retained, document the "
            "necessity and ensure the client retainer discloses AI processing."
        ),
    },
    "Date of birth": {
        "regex":    r'\b(?:born|d\.?o\.?b\.?|date of birth)[:\s]+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
        "risk":     "HIGH",
        "guidance": "Date of birth combined with name constitutes highly sensitive PI.",
    },
    "Canadian postal code": {
        "regex":    r'\b[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d\b',
        "risk":     "MEDIUM",
        "guidance": (
            "Postal codes alone are not PI, but combined with a name or address they "
            "identify an individual's location. Flag for context review."
        ),
    },
    "Phone number": {
        "regex":    (r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b'),
        "risk":     "MEDIUM",
        "guidance": "Phone numbers are PI when linked to an identifiable individual.",
    },
    "Email address": {
        "regex":    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
        "risk":     "MEDIUM",
        "guidance": "Email addresses are PI under PIPEDA when linked to a natural person.",
    },
    "Bank / financial account": {
        "regex":    r'\b(?:account\s*(?:no\.?|number|#)\s*[\d\-]{6,20}|transit\s*(?:no\.?|number)\s*\d{5})\b',
        "risk":     "HIGH",
        "guidance": "Financial account details are sensitive PI. Redact before upload.",
    },
    "Health / medical information": {
        "regex":    (
            r'\b(?:diagnosis|medical\s+condition|health\s+information|'
            r'prescription|disability|ohip|health\s+card)\b'
        ),
        "risk":     "HIGH",
        "guidance": (
            "Health information is among the most sensitive PI under PIPEDA and PHIPA "
            "(Ontario). Strong recommendation to redact before upload."
        ),
    },
    "Named individual (signature block)": {
        "regex":    (
            r'(?:signed|executed|agreed)\s+by[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ),
        "risk":     "LOW",
        "guidance": (
            "Named signatories are PI if they are natural persons. Corporate signing "
            "officers acting in their professional capacity carry lower PIPEDA risk, "
            "but document the processing purpose in the retainer."
        ),
    },
    "Home / residential address": {
        "regex":    (
            r'\b\d{1,6}\s+[A-Za-z][A-Za-z\s]{2,30}'
            r'(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Court|Ct|'
            r'Boulevard|Blvd|Lane|Ln|Place|Pl|Way|Crescent|Cres)\b'
        ),
        "risk":     "MEDIUM",
        "guidance": (
            "Residential addresses are PI. Commercial premises addresses are not. "
            "Review in context before upload."
        ),
    },
    "Salary / compensation (employment)": {
        "regex":    (
            r'\b(?:base\s+salary|annual\s+salary|total\s+compensation|'
            r'hourly\s+rate|wage)\s*(?:of\s*)?(?:\$|CAD)?\s*[\d,]+(?:\.\d{2})?\b'
        ),
        "risk":     "MEDIUM",
        "guidance": (
            "Individual compensation figures in employment contracts are PI. "
            "Consider whether the retainer disclosure covers AI-assisted review."
        ),
    },
}


def detect_personal_information(text: str) -> List[PIFinding]:
    """Scan contract text for personal information patterns.

    Returns a list of PIFinding objects, one per category where matches
    were found. Empty list = no PI patterns detected (but not a guarantee
    — unusual formatting may evade regex).

    Called before the API call so the lawyer can choose to redact or
    confirm consent before proceeding.
    """
    findings = []
    text_check = text[:200_000]  # scan first 200k chars — sufficient for PI detection

    for category, cfg in PI_PATTERNS.items():
        try:
            matches = re.findall(cfg["regex"], text_check, re.IGNORECASE)
            if matches:
                # Deduplicate and truncate for display
                unique = list(dict.fromkeys(
                    str(m[:60]) for m in matches if m
                ))[:5]
                findings.append(PIFinding(
                    category    = category,
                    pattern_key = category,
                    matches     = unique,
                    count       = len(matches),
                    risk        = cfg["risk"],
                    guidance    = cfg["guidance"],
                ))
        except re.error:
            pass

    # Sort: HIGH first, then MEDIUM, then LOW
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings.sort(key=lambda f: order.get(f.risk, 3))
    return findings


def pi_risk_summary(findings: List[PIFinding]) -> dict:
    """Summarise findings into an overall risk level and action recommendation."""
    if not findings:
        return {
            "level":      "NONE",
            "colour":     "#15803d",
            "summary":    "No personal information patterns detected.",
            "action":     "Standard processing. Document AI use in matter file.",
        }
    high   = [f for f in findings if f.risk == "HIGH"]
    medium = [f for f in findings if f.risk == "MEDIUM"]

    if high:
        return {
            "level":   "HIGH",
            "colour":  "#8B0000",
            "summary": (
                f"{len(high)} high-sensitivity PI category(s) detected "
                f"({', '.join(f.category for f in high[:3])})."
            ),
            "action": (
                "RECOMMENDED: Redact identified PI before upload, OR obtain explicit "
                "client consent covering AI processing and cross-border transfer to "
                "Anthropic's US infrastructure. Add AI disclosure to retainer agreement."
            ),
        }
    if medium:
        return {
            "level":   "MEDIUM",
            "colour":  "#B8860B",
            "summary": (
                f"{len(medium)} medium-sensitivity PI category(s) detected."
            ),
            "action": (
                "Review in context. Ensure client retainer agreement includes AI "
                "processing disclosure. Document the processing purpose."
            ),
        }
    return {
        "level":   "LOW",
        "colour":  "#2563EB",
        "summary": "Low-sensitivity patterns only (named signatories, addresses).",
        "action":  "Standard processing acceptable. Document AI use in matter file.",
    }


# ── 1b. AUTO-REDACTION ───────────────────────────────────────

def redact_personal_information(text: str, findings: List[PIFinding],
                                 placeholder: str = "[REDACTED]") -> tuple:
    """Replace detected PI patterns with redaction placeholders.

    Returns (redacted_text, count) where count is the number of
    substitutions made. The lawyer can download the redacted version
    and use that for the API call instead of the original.

    Only redacts HIGH and MEDIUM risk categories by default to avoid
    over-redacting (e.g. named signatories are LOW risk and may be
    needed for context).
    """
    redacted = text
    total_count = 0

    for finding in findings:
        if finding.risk not in ("HIGH", "MEDIUM"):
            continue
        cfg = PI_PATTERNS.get(finding.category, {})
        pattern = cfg.get("regex", "")
        if not pattern:
            continue
        label = finding.category.replace(" ", "_").replace("/", "_").upper()
        repl  = f"[REDACTED_{label}]"
        try:
            new_text, n = re.subn(pattern, repl, redacted, flags=re.IGNORECASE)
            redacted = new_text
            total_count += n
        except Exception:
            pass

    return redacted, total_count


# ── 2. RETAINER CLAUSE TEMPLATE ───────────────────────────────

def generate_retainer_disclosure(firm_name: str = "[FIRM NAME]",
                                  jurisdiction: str = "Ontario") -> str:
    """Generate a plain-English retainer disclosure clause.

    Designed for insertion into a standard client retainer agreement.
    Addresses PIPEDA consent, purpose limitation, cross-border transfer,
    and Anthropic's no-training commitment.
    """
    return f"""
USE OF TECHNOLOGY-ASSISTED REVIEW — CLIENT DISCLOSURE

{firm_name} (the "Firm") uses technology-assisted review tools, including
artificial intelligence ("AI") software, to assist with the review, analysis,
and drafting of legal documents as part of its professional services.

1. AI-Assisted Document Review. The Firm may use ContractCheck Pro, an
   AI-assisted contract review tool, to conduct first-pass analysis of
   contracts and legal documents you provide to the Firm. This tool uses
   large language model technology provided by Anthropic PBC ("Anthropic"),
   a U.S.-based artificial intelligence company.

2. How Your Information Is Processed. When a document is submitted for
   AI-assisted review: (a) the document text is transmitted to Anthropic's
   application programming interface (API) for processing; (b) the document
   text is processed in computer memory and is not retained by Anthropic
   beyond the duration of the processing request, in accordance with
   Anthropic's commercial API terms; (c) Anthropic does not use documents
   submitted via its commercial API to train its AI models; and (d) only
   anonymized analysis metadata (risk assessments, issue summaries) is
   stored locally on the Firm's systems — verbatim contract text is not
   retained locally.

3. Cross-Border Transfer. Anthropic's API infrastructure is located in the
   United States. By authorizing AI-assisted review, you acknowledge that
   your documents, which may contain personal information, will be
   transmitted to and processed in the United States. This transfer is
   subject to U.S. law, which may differ from Canadian privacy law. The
   Firm remains accountable for the protection of your personal information
   in accordance with the Personal Information Protection and Electronic
   Documents Act (Canada) ("PIPEDA") and, where applicable, {jurisdiction}
   privacy legislation.

4. Personal Information. If the documents you provide contain personal
   information about identifiable individuals (such as names, addresses,
   salary information, or other personal details), the Firm will use that
   information only for the purpose of providing the legal services
   described in this retainer agreement. You represent that you have
   authority to provide such personal information to the Firm for this
   purpose.

5. Consent. By signing this retainer agreement and providing documents to
   the Firm, you consent to the use of AI-assisted review tools as
   described above. You may withdraw this consent at any time by notifying
   the Firm in writing, in which case the Firm will use alternative
   (non-AI-assisted) review methods, which may affect the timing and cost
   of services.

6. Human Review. All AI-assisted analysis is reviewed by a qualified lawyer
   before any advice, recommendation, or work product is provided to you.
   The AI tool is a productivity aid only and does not replace the
   professional judgment of the Firm's lawyers.

7. Further Information. For questions about how the Firm handles personal
   information, please contact the Firm's Privacy Officer at
   [PRIVACY OFFICER EMAIL]. Anthropic's privacy practices are described at
   https://www.anthropic.com/policies/privacy.

This disclosure is provided in accordance with the Firm's obligations under
PIPEDA and the applicable Law Society rules of professional conduct.
""".strip()


# ── 3. MATTER STORE RETENTION UTILITIES ───────────────────────

def purge_expired_matters(retention_days: int) -> int:
    """Delete matters older than retention_days from the matter store.

    Returns the number of matters deleted.
    Called from the UI settings panel when the user configures retention.
    """
    # Import here to avoid circular imports
    from matter_store import _get_conn, init_db
    from datetime import datetime, timedelta
    init_db()
    cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
    with _get_conn() as c:
        result = c.execute(
            "DELETE FROM matters WHERE created_at < ?", (cutoff,))
        return result.rowcount


def purge_all_matters() -> int:
    """Delete ALL matters from the matter store. Irreversible."""
    from matter_store import _get_conn, init_db
    init_db()
    with _get_conn() as c:
        result = c.execute("DELETE FROM matters")
        return result.rowcount


def matters_older_than(days: int) -> int:
    """Count how many matters would be deleted by a given retention period."""
    from matter_store import _get_conn, init_db
    from datetime import datetime, timedelta
    init_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _get_conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM matters WHERE created_at < ?", (cutoff,)
        ).fetchone()[0]
