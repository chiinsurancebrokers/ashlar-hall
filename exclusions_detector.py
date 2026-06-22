"""
CHI Insurance Brokers — Critical Exclusions & Risk Flag Detector
================================================================
Adapted from PythonProject5/simple_working_analyzer.py and
PythonProject5/analysis_plugins.py

Scans extracted PDF text for dangerous hidden clauses:
  - Life support / ventilator time limits
  - Dialysis session limits
  - Terminal / palliative care caps
  - Artificial feeding limits
  - Mental health session caps
  - Pre-existing condition exclusion windows
  - Ambiguous wording ("at our discretion", "reasonable", etc.)

Multi-dimensional scoring (from analysis_plugins.py PolicyScoringPlugin):
  coverage_breadth, financial_protection, preventive_care, accessibility
"""

import re
from typing import Dict, List


# ─── EXCLUSION PATTERNS (from PythonProject5/simple_working_analyzer.py) ──────

EXCLUSION_PATTERNS = {
    "artificial_life_support": {
        "severity": "CRITICAL",
        "label_el": "Τεχνητή Υποστήριξη Ζωής",
        "patterns": [
            r"artificial.*?(?:life|mechanical).*?support.*?(?:more than|beyond|limited to|maximum of)\s*(\d+)\s*(?:consecutive\s+)?days",
            r"mechanical.*?(?:life|artificial).*?support.*?(?:more than|limited to|maximum of)\s*(\d+)\s*days",
            r"ventilator.*?support.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:consecutive\s+)?days",
            r"life.*?support.*?(?:limited to|maximum of|not more than)\s*(\d+)\s*days",
        ],
    },
    "dialysis_limits": {
        "severity": "CRITICAL",
        "label_el": "Περιορισμός Αιμοκάθαρσης",
        "patterns": [
            r"dialysis.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:sessions|days|treatments)",
            r"kidney.*?support.*?(?:limited to|maximum of)\s*(\d+)\s*(?:sessions|days|treatments)",
            r"renal.*?(?:dialysis|treatment).*?(?:limited to|maximum of)\s*(\d+)",
        ],
    },
    "terminal_care": {
        "severity": "CRITICAL",
        "label_el": "Παρηγορητική / Τερματική Φροντίδα",
        "patterns": [
            r"terminal.*?illness.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:days|months|weeks)",
            r"palliative.*?care.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:days|months|weeks)",
            r"hospice.*?care.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:days|months|weeks)",
        ],
    },
    "feeding_support": {
        "severity": "CRITICAL",
        "label_el": "Τεχνητή Σίτιση",
        "patterns": [
            r"(?:artificial|tube).*?feeding.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:days|weeks|months)",
            r"PEG.*?(?:more than|limited to|maximum of)\s*(\d+)\s*(?:days|weeks|months)",
            r"nutritional.*?support.*?(?:limited to|maximum of)\s*(\d+)\s*(?:days|weeks|months)",
        ],
    },
    "mental_health_limits": {
        "severity": "HIGH",
        "label_el": "Περιορισμός Ψυχικής Υγείας",
        "patterns": [
            r"mental.*?health.*?(?:limited to|maximum of|not more than)\s*(\d+)\s*(?:sessions|visits|days)",
            r"therapy.*?(?:limited to|maximum of|not more than)\s*(\d+)\s*(?:sessions|visits|days)",
            r"psychological.*?(?:limited to|maximum of|not more than)\s*(\d+)\s*(?:sessions|visits|days)",
            r"psychiatric.*?(?:limited to|maximum of|not more than)\s*(\d+)\s*(?:sessions|visits|days)",
        ],
    },
    "pre_existing_exclusion": {
        "severity": "HIGH",
        "label_el": "Αποκλεισμός Προϋπαρχουσών Παθήσεων",
        "patterns": [
            r"pre.existing.*?condition.*?(?:excluded|not covered).*?(?:for|during)\s*(\d+)\s*(?:months|years)",
            r"existing.*?condition.*?(?:excluded|not covered).*?(?:for|during)\s*(\d+)\s*(?:months|years)",
        ],
    },
    "evacuation_cap": {
        "severity": "HIGH",
        "label_el": "Ανώτατο Όριο Εκκένωσης",
        "patterns": [
            r"medical.*?evacuation.*?(?:limited to|maximum of)\s*[\$£€¥]\s*([\d,]+)",
            r"emergency.*?evacuation.*?(?:limited to|maximum of)\s*[\$£€¥]\s*([\d,]+)",
        ],
    },
}

# Ambiguous wording (from PythonProject5/wording_analyzer.py)
AMBIGUOUS_TERMS = [
    "at our discretion",
    "at the company's discretion",
    "reasonable and customary",
    "medically necessary",
    "as we determine",
    "subject to approval",
    "may be covered",
    "we may refuse",
]


# ─── SEVERITY EMOJI MAP ─────────────────────────────────────────────

SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
}


# ─── MAIN DETECTOR ──────────────────────────────────────────────────

def detect_exclusions(policy_text: str, insurer: str = "") -> Dict:
    """
    Scan raw policy text for dangerous exclusions and risk flags.

    Returns:
        {
          "findings":        list of individual matches with context
          "critical_count":  int
          "high_count":      int
          "severity_score":  int   (higher = more dangerous)
          "safety_rating":   float (0–10, 10 = safest)
          "risk_flags":      list of short flag strings
          "ambiguous_terms_found": list
        }
    """
    if not policy_text or len(policy_text.strip()) < 50:
        return _empty_result()

    text_lower = policy_text.lower()
    findings = []
    critical_count = 0
    high_count = 0
    severity_score = 0

    for category, meta in EXCLUSION_PATTERNS.items():
        sev = meta["severity"]
        label = meta["label_el"]
        for pattern in meta["patterns"]:
            try:
                for match in re.finditer(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                    # Context window: 120 chars around the match
                    start = max(0, match.start() - 120)
                    end   = min(len(policy_text), match.end() + 120)
                    context = policy_text[start:end].strip()

                    numbers = [g for g in match.groups() if g]

                    finding = {
                        "category":    category,
                        "label_el":    label,
                        "severity":    sev,
                        "emoji":       SEVERITY_EMOJI.get(sev, "⚪"),
                        "matched":     match.group(),
                        "numbers":     numbers,
                        "context":     context,
                    }
                    findings.append(finding)

                    if sev == "CRITICAL":
                        critical_count += 1
                        severity_score += 25
                        # Extra penalty for very short time limits
                        for n in numbers:
                            try:
                                if int(n.replace(",", "")) <= 60:
                                    severity_score += 15
                            except ValueError:
                                pass
                    elif sev == "HIGH":
                        high_count += 1
                        severity_score += 10

            except re.error:
                pass  # Ignore bad patterns silently

    # Deduplicate by (category + first number)
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f["category"], f["numbers"][0] if f["numbers"] else f["matched"][:30])
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # Ambiguous wording check
    ambiguous_found = [
        term for term in AMBIGUOUS_TERMS if term in text_lower
    ]

    # Safety rating (from PythonProject5/simple_working_analyzer.py)
    if critical_count == 0 and high_count == 0:
        safety_rating = 9.0
    elif critical_count >= 3 or severity_score >= 80:
        safety_rating = 1.0
    elif critical_count >= 2 or severity_score >= 55:
        safety_rating = 3.0
    elif critical_count >= 1 or severity_score >= 30:
        safety_rating = 5.5
    elif high_count >= 2:
        safety_rating = 6.5
    elif high_count >= 1:
        safety_rating = 7.5
    else:
        safety_rating = 8.5

    # Risk flag strings
    risk_flags = _build_risk_flags(unique_findings, ambiguous_found)

    return {
        "findings":             unique_findings,
        "critical_count":       critical_count,
        "high_count":           high_count,
        "severity_score":       severity_score,
        "safety_rating":        safety_rating,
        "risk_flags":           risk_flags,
        "ambiguous_terms_found": ambiguous_found,
    }


def _build_risk_flags(findings: List[Dict], ambiguous: List[str]) -> List[str]:
    """Build short, human-readable risk flag strings."""
    flags = []
    categories_seen = set()

    for f in findings:
        cat = f["category"]
        if cat in categories_seen:
            continue
        categories_seen.add(cat)

        emoji = f["emoji"]
        label = f["label_el"]
        nums  = f["numbers"]

        if nums:
            flags.append(f"{emoji} {label}: περιορισμός {nums[0]}")
        else:
            flags.append(f"{emoji} {label}: ρήτρα αποκλεισμού")

    if ambiguous:
        flags.append(f"⚠️ Αμφίσημοι όροι: {len(ambiguous)} ({', '.join(ambiguous[:2])}...)")

    return flags


def _empty_result() -> Dict:
    return {
        "findings":             [],
        "critical_count":       0,
        "high_count":           0,
        "severity_score":       0,
        "safety_rating":        9.0,
        "risk_flags":           [],
        "ambiguous_terms_found": [],
    }


# ─── MULTI-DIMENSIONAL SCORING ──────────────────────────────────────
# Adapted from PythonProject5/analysis_plugins.py PolicyScoringPlugin

def compute_multidim_score(prop: dict) -> dict:
    """
    Returns a breakdown dict:
      {
        "overall":              float  0–10
        "coverage_breadth":     float  0–10
        "financial_protection": float  0–10
        "preventive_care":      float  0–10
        "accessibility":        float  0–10
        "labels": { dim: "Άριστο"|"Καλό"|"Μέτριο"|"Χαμηλό" }
      }
    """

    def _not_covered(v):
        if v is None:
            return True
        s = str(v).strip()
        return s in ("", "null", "None", "—") or "Not Covered" in s

    # ── Coverage breadth (0-10) ──
    breadth_fields = [
        "inpatient", "cancer", "mri_ct_pet", "chronic_conditions",
        "evacuation_repatriation", "physiotherapy", "psychiatric_outpatient",
        "dental_emergency", "wellness_screening", "cancer_screening",
        "organ_transplant", "hospice_care", "home_nursing",
    ]
    covered = sum(1 for f in breadth_fields if not _not_covered(prop.get(f)))
    coverage_breadth = round((covered / len(breadth_fields)) * 10, 1)

    # ── Financial protection (0-10) ──
    fp = 0.0
    mc = prop.get("max_coverage")
    if mc:
        try:
            v = int(str(mc).replace(",", ""))
            if   v >= 1_000_000: fp += 4.0
            elif v >=   500_000: fp += 3.0
            elif v >=   250_000: fp += 2.0
            elif v >=   100_000: fp += 1.0
        except (ValueError, TypeError):
            pass

    ded = prop.get("deductible")
    if ded:
        try:
            d = int(re.sub(r"[^\d]", "", str(ded)) or "0")
            if   d == 0:        fp += 3.0
            elif d <= 500:      fp += 2.5
            elif d <= 1000:     fp += 2.0
            elif d <= 2000:     fp += 1.0
        except (ValueError, TypeError):
            fp += 1.0

    ol = prop.get("outpatient_limit")
    if ol and not _not_covered(ol):
        try:
            v = int(str(ol).replace(",", ""))
            if   v >= 10_000: fp += 3.0
            elif v >= 5_000:  fp += 2.0
            elif v >= 2_000:  fp += 1.0
        except (ValueError, TypeError):
            fp += 1.0

    financial_protection = round(min(10.0, fp), 1)

    # ── Preventive care (0-10) ──
    prev_fields = ["wellness_screening", "cancer_screening"]
    prev_score  = 0.0
    for f in prev_fields:
        v = prop.get(f)
        if not _not_covered(v):
            try:
                amt = int(str(v).replace(",", ""))
                if   amt >= 1000: prev_score += 5.0
                elif amt >= 300:  prev_score += 3.0
                else:             prev_score += 1.5
            except (ValueError, TypeError):
                prev_score += 2.0
    preventive_care = round(min(10.0, prev_score), 1)

    # ── Accessibility (0-10) ──
    acc = 0.0
    geo = str(prop.get("geography") or "").lower()
    if any(w in geo for w in ["παγκόσμ", "worldwide", "global"]):
        acc += 5.0
    elif any(w in geo for w in ["ευρώπη", "europe", "διεθν"]):
        acc += 3.0
    elif geo:
        acc += 1.5

    if not _not_covered(prop.get("evacuation_repatriation")):
        acc += 2.5
    if not _not_covered(prop.get("home_nursing")):
        acc += 1.5
    if not _not_covered(prop.get("dental_emergency")):
        acc += 1.0
    accessibility = round(min(10.0, acc), 1)

    # ── Overall (weighted) ──
    overall = round(
        coverage_breadth     * 0.35 +
        financial_protection * 0.35 +
        preventive_care      * 0.15 +
        accessibility        * 0.15,
        1,
    )

    def _label(v: float) -> str:
        if v >= 8:   return "Άριστο"
        if v >= 6:   return "Καλό"
        if v >= 4:   return "Μέτριο"
        return "Χαμηλό"

    return {
        "overall":              overall,
        "coverage_breadth":     coverage_breadth,
        "financial_protection": financial_protection,
        "preventive_care":      preventive_care,
        "accessibility":        accessibility,
        "labels": {
            "overall":              _label(overall),
            "coverage_breadth":     _label(coverage_breadth),
            "financial_protection": _label(financial_protection),
            "preventive_care":      _label(preventive_care),
            "accessibility":        _label(accessibility),
        },
    }
