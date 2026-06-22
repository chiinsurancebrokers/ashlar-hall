"""
CHI Insurance Brokers — Language Profiles
==========================================
Bilingual support: Greek (el) and English (en).

Usage:
    from language_profiles import get_profile, detect_pdf_language

    lang = detect_pdf_language(pdf_text)   # "el" or "en"
    L    = get_profile(lang)               # LangProfile object
    print(L.labels["annual_premium"])      # "Ετήσιο Ασφάλιστρο" or "Annual Premium"
"""

import re
from dataclasses import dataclass, field
from typing import Dict


# ─── DETECTION ───────────────────────────────────────────────────────

def detect_pdf_language(text: str) -> str:
    """
    Detect whether a PDF's text is primarily Greek or English.
    Returns "el" (Greek) or "en" (English).

    Strategy: count Greek Unicode characters vs Latin characters.
    If > 20 % of alpha chars are Greek → "el".
    """
    if not text:
        return "en"

    # Greek Unicode range: 0370–03FF (basic) + 1F00–1FFF (extended)
    greek_chars = len(re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    total       = greek_chars + latin_chars

    if total == 0:
        return "en"

    return "el" if (greek_chars / total) > 0.20 else "en"


def detect_client_language(client_name: str, nationality: str = "") -> str:
    """
    Determine output language from client name or explicit nationality.
    Heuristic: if name contains Greek chars → "el", else "en".
    """
    if nationality.lower() in ("greek", "greece", "ελληνική", "ελλάδα", "gr"):
        return "el"
    if nationality.lower() in ("english", "uk", "us", "american", "british"):
        return "en"
    # Fallback: check if name has Greek chars
    greek = len(re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]", client_name))
    return "el" if greek > 0 else "en"


# ─── LANG PROFILE ────────────────────────────────────────────────────

@dataclass
class LangProfile:
    code:   str          # "el" or "en"
    name:   str          # "Ελληνικά" or "English"
    labels: Dict[str, str] = field(default_factory=dict)
    pptx:   Dict[str, str] = field(default_factory=dict)
    analysis_instruction: str = ""


# ── GREEK PROFILE ────────────────────────────────────────────────────

EL = LangProfile(
    code="el",
    name="Ελληνικά",
    analysis_instruction=(
        "Απάντησε ΑΠΟΚΛΕΙΣΤΙΚΑ στα ελληνικά. "
        "Χρησιμοποίησε επαγγελματικό αλλά ανθρώπινο ύφος, β' ενικό."
    ),
    labels={
        # Core fields
        "insurer":              "Ασφαλιστική",
        "plan_name":            "Πλάνο",
        "annual_premium":       "Ετήσιο Ασφάλιστρο",
        "currency":             "Νόμισμα",
        "deductible":           "Απαλλαγή",
        "max_coverage":         "Μέγιστο Κεφάλαιο",
        "geography":            "Γεωγραφία",
        "hospital_class":       "Θέση Νοσηλείας",
        "inpatient":            "Νοσοκομειακή",
        "outpatient_limit":     "Εξωνοσ. Όριο",
        "outpatient_pct":       "Εξωνοσ. %",
        "mri_ct_pet":           "MRI / CT / PET",
        "cancer":               "Καρκίνος",
        "physiotherapy":        "Φυσιοθεραπεία",
        "chronic_conditions":   "Χρόνιες Παθήσεις",
        "evacuation_repatriation": "Εκκένωση / Επαναπατρισμός",
        "dental_emergency":     "Οδοντ. Έκτακτη",
        "wellness_screening":   "Προληπτικός Έλεγχος",
        "cancer_screening":     "Έλεγχος Καρκίνου",
        "organ_transplant":     "Μεταμόσχευση Οργάνου",
        "hospice_care":         "Ανακουφιστική Φροντίδα",
        "psychiatric_inpatient":"Ψυχ. Νοσηλεία",
        "psychiatric_outpatient":"Ψυχ. Εξωτερικά",
        "home_nursing":         "Νοσηλεία Κατ' Οίκον",
        "waiting_period":       "Αναμονή",
        "preexisting":          "Προϋπ. Παθήσεις",
        "payment_frequency":    "Συχνότητα Πληρωμής",
        # Score dims
        "coverage_breadth":     "Εύρος Κάλυψης",
        "financial_protection": "Οικονομική Προστασία",
        "preventive_care":      "Πρόληψη",
        "accessibility":        "Προσβασιμότητα",
        "safety_rating":        "Ασφάλεια Πλάνου",
        # UI
        "recommended":          "ΠΡΟΤΕΙΝΟΜΕΝΟ",
        "not_covered":          "Δεν Καλύπτεται",
        "full_refund":          "Πλήρης Αποζημίωση",
    },
    pptx={
        "cover_subtitle":       "Ανάλυση & Σύγκριση Ασφαλιστικών Προσφορών",
        "overview_title":       "Σύνοψη Προσφορών",
        "comparison_title":     "Πίνακας Σύγκρισης",
        "analysis_title":       "Γιατί Προτείνουμε Αυτό το Πλάνο",
        "exclusions_title":     "Κρίσιμες Εξαιρέσεις & Ρήτρες",
        "closing_title":        "Η Πρότασή μας",
        "step1_tag":            "ΒΗΜΑ 1",
        "step1_title":          "Εντός 48ωρών",
        "step1_body":           "Έγκριση πρότασης & αποστολή ιατρικού ιστορικού",
        "step2_tag":            "ΒΗΜΑ 2",
        "step2_title":          "Underwriting",
        "step2_body":           "Υπογραφή αίτησης — σαφής γνώση τι καλύπτεται",
        "step3_tag":            "ΒΗΜΑ 3",
        "step3_title":          "Ενεργοποίηση",
        "step3_body":           "Άμεση κάλυψη χωρίς αναμονές",
        "key_advantages":       "ΚΥΡΙΑ ΠΛΕΟΝΕΚΤΗΜΑΤΑ",
        "risk_flags_title":     "ΚΡΙΣΙΜΕΣ ΡΗΤΡΕΣ (από Policy Wording)",
        "quote_text":           (
            "Η ασφάλεια υγείας δεν είναι κόστος — "
            "είναι επένδυση στην ηρεμία σας και στην οικογένειά σας."
        ),
        "prepared_for":         "Προετοιμάστηκε για:",
        "members_label":        "Μέλη:",
        "score_label":          "Βαθμολογία",
        "safety_label":         "Safety",
        "annual_label":         "Ετήσιο",
        "monthly_label":        "Μηνιαίο",
        "per_year":             "/ έτος",
    },
)


# ── ENGLISH PROFILE ──────────────────────────────────────────────────

EN = LangProfile(
    code="en",
    name="English",
    analysis_instruction=(
        "Respond EXCLUSIVELY in English. "
        "Use a professional yet approachable tone, second person (you/your)."
    ),
    labels={
        "insurer":              "Insurer",
        "plan_name":            "Plan",
        "annual_premium":       "Annual Premium",
        "currency":             "Currency",
        "deductible":           "Deductible",
        "max_coverage":         "Maximum Coverage",
        "geography":            "Geography",
        "hospital_class":       "Hospital Class",
        "inpatient":            "Inpatient",
        "outpatient_limit":     "Outpatient Limit",
        "outpatient_pct":       "Outpatient %",
        "mri_ct_pet":           "MRI / CT / PET",
        "cancer":               "Cancer",
        "physiotherapy":        "Physiotherapy",
        "chronic_conditions":   "Chronic Conditions",
        "evacuation_repatriation": "Evacuation / Repatriation",
        "dental_emergency":     "Emergency Dental",
        "wellness_screening":   "Preventive Screening",
        "cancer_screening":     "Cancer Screening",
        "organ_transplant":     "Organ Transplant",
        "hospice_care":         "Hospice Care",
        "psychiatric_inpatient":"Psychiatric Inpatient",
        "psychiatric_outpatient":"Psychiatric Outpatient",
        "home_nursing":         "Home Nursing",
        "waiting_period":       "Waiting Period",
        "preexisting":          "Pre-existing Conditions",
        "payment_frequency":    "Payment Frequency",
        "coverage_breadth":     "Coverage Breadth",
        "financial_protection": "Financial Protection",
        "preventive_care":      "Preventive Care",
        "accessibility":        "Accessibility",
        "safety_rating":        "Plan Safety",
        "recommended":          "RECOMMENDED",
        "not_covered":          "Not Covered",
        "full_refund":          "Full Refund",
    },
    pptx={
        "cover_subtitle":       "Insurance Quote Analysis & Comparison",
        "overview_title":       "Quotes Overview",
        "comparison_title":     "Comparison Table",
        "analysis_title":       "Why We Recommend This Plan",
        "exclusions_title":     "Critical Exclusions & Policy Terms",
        "closing_title":        "Our Recommendation",
        "step1_tag":            "STEP 1",
        "step1_title":          "Within 48 hours",
        "step1_body":           "Approve proposal & submit medical history",
        "step2_tag":            "STEP 2",
        "step2_title":          "Underwriting",
        "step2_body":           "Sign application — full clarity on coverage",
        "step3_tag":            "STEP 3",
        "step3_title":          "Activation",
        "step3_body":           "Immediate coverage, no waiting periods",
        "key_advantages":       "KEY ADVANTAGES",
        "risk_flags_title":     "CRITICAL CLAUSES (from Policy Wording)",
        "quote_text":           (
            "Health insurance is not a cost — "
            "it is an investment in your peace of mind and your family's future."
        ),
        "prepared_for":         "Prepared for:",
        "members_label":        "Members:",
        "score_label":          "Score",
        "safety_label":         "Safety",
        "annual_label":         "Annual",
        "monthly_label":        "Monthly",
        "per_year":             "/ year",
    },
)


# ─── ACCESSOR ────────────────────────────────────────────────────────

_PROFILES = {"el": EL, "en": EN}

def get_profile(lang_code: str) -> LangProfile:
    """Return the LangProfile for 'el' or 'en'. Defaults to 'el'."""
    return _PROFILES.get(lang_code, EL)
