"""
CHI Insurance Brokers — Ανίχνευση Ελληνικών vs Διεθνών Ασφαλιστικών

Χρησιμοποιείται για:
  - Να προσαρμόσει τα φίλτρα/καλύψεις ανάλογα με τη φύση των εταιρειών
  - Να αποκρύπτει πεδία που ΔΕΝ ισχύουν στην ελληνική αγορά
  - Να εμφανίζει σχετικές προειδοποιήσεις
"""

# ─── Γνωστές ελληνικές ασφαλιστικές (lowercase για σύγκριση) ─────────────────
_GREEK_INSURERS: set[str] = {
    "generali", "generali hellas",
    "εθνική", "ethniki", "εθνικη", "national",
    "groupama",
    "interamerican", "ιντεραμέρικαν", "ιντεραμερικαν",
    "ergo", "ergo ελλάδα", "ergo hellas",
    "allianz", "allianz hellas", "allianz ελλάδα",
    "eurolife", "eurolife ergo",
    "πειραιώς", "piraeos", "τράπεζα πειραιώς",
    "alphabank", "alpha bank", "alpha insurance",
    "eurobank", "eurobank life",
    "νη", "nη",   # ΝΗ ασφαλιστική
    "ιασω",
    "υγεία",
    "metlife", "met life",  # has Greek operations
    "aig ελλάδα", "aig hellas",
    "anytime",
    "minetta",
    "helvetia", "helvetia ελλάς",
}

# ─── Γνωστές ΔΙΕΘΝΕΙΣ ασφαλιστικές (expat / international health) ────────────
_INTERNATIONAL_INSURERS: set[str] = {
    "morgan price", "morgan-price",
    "now health", "nowhealth",
    "cigna", "cigna global",
    "axa", "axa international", "axa global",
    "bupa", "bupa global", "bupa international",
    "aetna", "aetna international",
    "april international", "april",
    "alc health", "alc",
    "img", "img global",
    "geo blue", "geoblue",
    "foyer global health", "foyer",
    "vumi", "william russell",
    "globalcare", "pacificcare",
    "integra global",
    "healix", "henner",
}


def is_greek_insurer(insurer_name: str | None) -> bool:
    """
    Επιστρέφει True αν το όνομα ταιριάζει με γνωστή ελληνική ασφαλιστική.
    Fallback: αν δεν βρεθεί πουθενά → θεωρείται ελληνική (conservative default).
    """
    if not insurer_name:
        return True   # άγνωστη → θεωρούμε ελληνική για ασφάλεια
    name = insurer_name.lower().strip()
    # Ρητά διεθνείς
    for intl in _INTERNATIONAL_INSURERS:
        if intl in name or name in intl:
            return False
    # Ρητά ελληνικές
    for gr in _GREEK_INSURERS:
        if gr in name or name in gr:
            return True
    # Αν η εταιρεία έχει ελληνικό χαρακτήρα στο όνομά της → ελληνική
    if any(ord(c) > 880 for c in insurer_name):   # unicode Greek range
        return True
    # Default: θεωρούμε ελληνική (οι περισσότεροι πελάτες του CHI είναι ελληνική αγορά)
    return True


def detect_comparison_mode(proposals: list[dict]) -> str:
    """
    Ανιχνεύει τη λειτουργία σύγκρισης βάσει των εταιρειών.

    Επιστρέφει:
      "greek_only"         — όλες ελληνικές
      "international_only" — όλες διεθνείς
      "mixed"              — μεικτός πληθυσμός
    """
    if not proposals:
        return "greek_only"

    greek_count = sum(
        1 for p in proposals if is_greek_insurer(p.get("insurer"))
    )
    intl_count = len(proposals) - greek_count

    if greek_count == 0:
        return "international_only"
    if intl_count == 0:
        return "greek_only"
    return "mixed"


# ─── Καλύψεις που ΔΕΝ παρέχονται στην ελληνική αγορά ────────────────────────
NOT_AVAILABLE_IN_GREEK = [
    {
        "field": "outpatient_type_general",
        "label": "Εξωνοσοκομειακή σε ελεύθερο δίκτυο ιατρών",
        "reason": (
            "Καμία ελληνική ασφαλιστική δεν καλύπτει γενικές επισκέψεις/εξετάσεις "
            "εκτός νοσοκομείου. Το 'εξωνοσοκομειακό' των ελληνικών εταιρειών "
            "αφορά ΜΟΝΟ ειδικές διαγνωστικές/επεμβατικές πράξεις σε συμβεβλημένα νοσοκομεία."
        ),
    },
    {
        "field": "dental_full",
        "label": "Πλήρης οδοντιατρική (σφραγίσματα, εξαγωγές, ορθοδοντική)",
        "reason": (
            "Καμία ελληνική ασφαλιστική δεν καλύπτει οδοντιατρικές θεραπείες. "
            "Κάποιες παρέχουν εκπτώσεις σε συνεργαζόμενο δίκτυο ή "
            "κάλυψη αποκλειστικά μετά από τροχαίο ατύχημα."
        ),
    },
    {
        "field": "psychiatric_outpatient",
        "label": "Ψυχολογική/ψυχιατρική υποστήριξη χωρίς νοσηλεία",
        "reason": (
            "Δεν καλύπτεται αυτόνομα σε καμία ελληνική εταιρεία. "
            "Η Generali καλύπτει 10 συνεδρίες ΜΕΤΑνοσηλεία, "
            "η Groupama καλύπτει ψυχιατρική νοσηλεία (εντός νοσοκομείου, έως €10.000)."
        ),
    },
    {
        "field": "mri_ct_pet_outpatient",
        "label": "MRI / CT / PET scan εκτός νοσηλείας",
        "reason": (
            "Τα MRI/CT/PET καλύπτονται μόνο στο πλαίσιο νοσηλείας. "
            "Δεν υπάρχει ελληνική ασφαλιστική που να τα καλύπτει ως αυτόνομο εξωνοσοκομειακό."
        ),
    },
    {
        "field": "cancer_outpatient",
        "label": "Θεραπεία καρκίνου (χημειο/ακτινο) εκτός νοσηλείας",
        "reason": (
            "Χημειοθεραπεία και ακτινοθεραπεία καλύπτονται μόνο εντός νοσοκομείου "
            "ή άμεσα συνδεδεμένα με νοσηλεία. Δεν υπάρχει standalone εξωνοσοκομειακή "
            "ογκολογική κάλυψη στην ελληνική αγορά."
        ),
    },
]


# ─── Ελληνικές καλύψεις που αξίζει να εμφανίζονται ─────────────────────────
GREEK_SPECIFIC_FIELDS = [
    # (field_key, label, help_text)
    ("deductible_ods",           "Εκπιπτόμενο ODS (ημερήσια χειρ.)",
     "Μειωμένο εκπιπτόμενο για χειρουργεία χωρίς διανυκτέρευση"),
    ("deductible_public",        "Εκπιπτόμενο σε δημόσιο νοσ.",
     "Συνήθως €0 στα ελληνικά προγράμματα"),
    ("emergency_er_limit",       "Επείγοντα εξωτερικά ιατρεία — Όριο/περιστατικό",
     "Κάλυψη ΤΕΠ/εξωτερικών ιατρείων σε συμβεβλημένα νοσοκομεία"),
    ("emergency_er_copay",       "Επείγοντα — Συμμετοχή (%)",
     "Ποσοστό συμμετοχής ασφαλισμένου στο επείγον περιστατικό"),
    ("emergency_er_incidents",   "Επείγοντα — Μέγιστα περιστατικά/έτος",
     ""),
    ("specific_diagnostics_limit","Ειδικές διαγνωστικές χωρίς νοσ. — Όριο",
     "Γαστροσκόπηση, κολονοσκόπηση, κυστεοσκόπηση, βιοψία κλπ."),
    ("specific_diagnostics_copay","Ειδικές διαγνωστικές — Συμμετοχή (%)",
     "0% με χρήση κοινωνικής ασφάλισης σε ορισμένες εταιρείες"),
    ("second_opinion",           "Δεύτερη Ιατρική Γνώμη",
     "Αριθμός ασθενειών που καλύπτονται και συχνότητα"),
    ("zero_deductible_serious",  "Μηδενισμός εκπιπτόμενου — Σοβαρές ασθένειες",
     "Καρκίνος, καρδιοπάθεια, ΑΕΕ κ.λπ."),
    ("rehabilitation_limit",     "Αποκατάσταση / Κέντρα αποθεραπείας — Όριο",
     ""),
    ("home_nursing",             "Νοσηλεία στο σπίτι — Όριο/έτος",
     ""),
    ("maternity_allowance",      "Επίδομα Τοκετού",
     "Ποσό επιδόματος — ισχύει από ποιο έτος ασφάλισης"),
    ("annual_checkup_count",     "Ετήσιες Προληπτικές Εξετάσεις (αριθμός)",
     "Αριθμός εξετάσεων που περιλαμβάνει το ετήσιο πακέτο"),
    ("telemedicine",             "Τηλεϊατρική",
     "Δωρεάν ή με χρέωση — ειδικότητες και διαθεσιμότητα"),
    ("accident_outpatient_limit","Ατύχημα εκτός νοσοκομείου — Όριο",
     "Ιατροφαρμακευτικά έξοδα από ατύχημα εκτός νοσηλείας"),
    ("accident_outpatient_copay","Ατύχημα εκτός νοσ. — Συμμετοχή (%)",
     ""),
    ("dental_network_discount",  "Οδοντιατρικές Εκπτώσεις Δικτύου",
     "ΟΧΙ πλήρης κάλυψη — μόνο ανώτατη τιμή σε συνεργαζόμενους"),
    ("psychiatric_inpatient",    "Ψυχιατρική Νοσηλεία (εντός νοσ.)",
     "Μόνο Groupama στην ελληνική αγορά (έως €10.000)"),
    ("psychiatric_post_hosp",    "Ψυχολ. Υποστήριξη μετά νοσηλεία",
     "Μόνο Generali — 10 συνεδρίες μόνο μετά νοσηλεία"),
]


# ─── Μεταφράσεις όρων (EN → EL) ─────────────────────────────────────────────

# Ακριβείς αντιστοιχίσεις (case-insensitive trim)
_EXACT_TRANSLATIONS: dict[str, str] = {
    "not covered":      "Δεν Καλύπτεται",
    "not covered.":     "Δεν Καλύπτεται",
    "full refund":      "Πλήρης Κάλυψη",
    "covered":          "Καλύπτεται",
    "unlimited":        "Απεριόριστη",
    "immediate":        "Άμεση",
    "null":             "",
    "none":             "",
}

# Μερικές αντικαταστάσεις μέσα σε συνθετότερες τιμές
_PARTIAL_TRANSLATIONS: list[tuple[str, str]] = [
    ("Not Covered",  "Δεν Καλύπτεται"),
    ("Full Refund",  "Πλήρης Κάλυψη"),
    ("Unlimited",    "Απεριόριστη"),
    ("Immediate",    "Άμεση"),
]


def _translate_value(v: str) -> str:
    """Μεταφράζει μία τιμή αγγλικού ασφαλιστικού όρου σε ελληνικά."""
    stripped = v.strip()
    lower    = stripped.lower()

    # Ακριβής αντιστοίχιση
    if lower in _EXACT_TRANSLATIONS:
        return _EXACT_TRANSLATIONS[lower]

    # Μερική αντικατάσταση
    result = stripped
    for eng, gr in _PARTIAL_TRANSLATIONS:
        result = result.replace(eng, gr)
    return result


def localize_insurance_data(prop: dict) -> None:
    """
    Μεταφράζει τιμές αγγλικών ασφαλιστικών όρων σε ελληνικά μέσα στο dict.
    Ενεργοποιείται ΜΟΝΟ για ελληνικές εταιρείες, αμέσως μετά την εξαγωγή.
    Δεν αγγίζει αριθμητικά πεδία ή λίστες.
    Τροποποιεί το dict in-place.
    """
    # Πεδία που δεν πρέπει να μεταφραστούν (αριθμοί, IDs, τεχνικά)
    _skip = {
        "annual_premium", "deductible", "max_coverage", "outpatient_limit",
        "outpatient_pct", "outpatient_type", "company_type", "currency",
        "payment_frequency", "insured_members", "key_notes",
        "deductible_public", "deductible_ods",
        "emergency_er_limit", "emergency_er_copay", "emergency_er_incidents",
        "specific_diagnostics_limit", "specific_diagnostics_copay",
        "rehabilitation_limit", "maternity_allowance", "annual_checkup_count",
        "accident_outpatient_limit", "accident_outpatient_copay",
    }

    for key, value in prop.items():
        if key in _skip:
            continue
        if isinstance(value, str) and value.strip():
            translated = _translate_value(value)
            if translated != value:
                prop[key] = translated
