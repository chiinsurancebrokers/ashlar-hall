"""
CHI Insurance Brokers — Policy Terms / Wording Analyzer
========================================================
Solves the token problem: instead of feeding a 200-page Terms PDF to Claude,
this module:
  1. Detects which pages contain exclusion-relevant language
  2. Splits them into 3 500-char chunks
  3. Sends each chunk to Claude with a FOCUSED exclusion-hunter prompt
  4. Merges and deduplicates all findings

Designed to be called ONCE per Terms PDF, separately from the main
quote extraction. Results are stored in prop["_terms_exclusions"].

Token cost per insurer: ~1-3 Claude calls (vs 1 massive call that
would exceed context for most policy documents).
"""

import re
import time
import json

import anthropic
import streamlit as st

try:
    import fitz
    _PYMUPDF_OK = True
except ImportError:
    _PYMUPDF_OK = False

from config import MODEL, MAX_RETRIES, RETRY_WAIT_BASE


# ─── PAGE SCORING: exclusion-focused keywords ────────────────────────
# Different from extraction.py's _HIGH_VALUE — these target TERMS pages

_EXCLUSION_KEYWORDS = [
    # English
    "exclusion", "excluded", "not covered", "does not cover", "shall not cover",
    "limitation", "limit of liability", "waiting period", "pre-existing",
    "pre existing", "general exclusions", "specific exclusions",
    "what is not covered", "conditions not covered",
    "dialysis", "life support", "ventilator", "palliative", "hospice",
    "terminal illness", "artificial feeding", "tube feeding",
    "maximum benefit", "benefit limit", "annual limit", "sub-limit",
    "coinsurance", "deductible", "co-payment", "copayment",
    "experimental", "investigational", "cosmetic", "elective",
    "mental health limit", "psychiatric limit",
    # Greek
    "εξαίρεση", "εξαιρέσεις", "εξαιρούνται", "δεν καλύπτεται",
    "δεν καλύπτονται", "αποκλείεται", "αποκλεισμός",
    "προϋπάρχουσα", "προϋπάρχον", "αναμονή", "περίοδος αναμονής",
    "ανώτατο όριο", "ανώτατο κεφάλαιο", "υποόριο",
    "αιμοκάθαρση", "διαπίστωση", "νεφρική", "τεχνητή αναπνοή",
    "παρηγορητική", "ανακουφιστική", "τεχνητή σίτιση",
    "ψυχιατρική", "ψυχική υγεία", "όρια ψυχικής",
    "γενικές εξαιρέσεις", "ειδικές εξαιρέσεις",
    "τι δεν καλύπτεται", "παθήσεις που εξαιρούνται",
]

_CHUNK_MAX_CHARS  = 3_500   # Max chars per Claude call
_MAX_CHUNKS       = 6       # Safety cap: max 6 chunks per Terms PDF
_MIN_PAGE_SCORE   = 3       # Page must have ≥ 3 keyword hits to be included


# ─── EXCLUSION HUNTER PROMPT ─────────────────────────────────────────

def _build_hunter_prompt(chunk_text: str, insurer: str, lang: str) -> str:
    """Prompt sent to Claude for each terms chunk."""
    lang_instruction = (
        "Respond in GREEK (ελληνικά)." if lang == "el"
        else "Respond in ENGLISH."
    )

    return f"""You are an expert insurance policy analyst for CHI Insurance Brokers.
Analyze this extract from the policy terms/wording of {insurer} and identify ALL exclusions,
limitations, time caps, and hidden restrictions.

{lang_instruction}

TEXT:
\"\"\"
{chunk_text}
\"\"\"

Return ONLY valid JSON, no markdown, no preamble:
{{
  "exclusions": [
    {{
      "category": "one of: life_support|dialysis|terminal_care|mental_health|pre_existing|waiting_period|benefit_cap|general_exclusion|other",
      "severity": "CRITICAL|HIGH|MEDIUM",
      "description": "plain language description of what is restricted/excluded",
      "exact_wording": "the relevant phrase from the text (max 80 chars)",
      "limit_value": "specific number/amount/duration if mentioned, else null"
    }}
  ],
  "ambiguous_clauses": [
    "short description of any vague clause like 'at our discretion' or 'reasonable'"
  ]
}}

Rules:
- Only include findings that are genuine exclusions or restrictions (not general coverage descriptions).
- severity CRITICAL = life-threatening impact (dialysis, life support, terminal illness caps).
- severity HIGH = significant financial impact or major benefit restriction.
- severity MEDIUM = minor limitation worth noting.
- If no exclusions found in this chunk, return {{"exclusions": [], "ambiguous_clauses": []}}.
- Exact wording must be a direct quote from the text, max 80 characters.
"""


# ─── PAGE SCORER ─────────────────────────────────────────────────────

def _score_exclusion_page(page_text: str) -> int:
    """Count how many exclusion keywords appear on this page."""
    t = page_text.lower()
    return sum(1 for kw in _EXCLUSION_KEYWORDS if kw.lower() in t)


# ─── CHUNK BUILDER ───────────────────────────────────────────────────

def _build_chunks(pages: list[tuple[int, str]]) -> list[str]:
    """
    Takes list of (page_num, text) tuples and groups them into
    chunks of max _CHUNK_MAX_CHARS characters.
    """
    chunks   = []
    current  = ""

    for page_num, text in pages:
        header = f"\n\n[PAGE {page_num}]\n"
        block  = header + text.strip()

        if len(current) + len(block) > _CHUNK_MAX_CHARS:
            if current.strip():
                chunks.append(current.strip())
            current = block
        else:
            current += block

    if current.strip():
        chunks.append(current.strip())

    return chunks[:_MAX_CHUNKS]


# ─── MAIN ENTRY POINT ────────────────────────────────────────────────

def analyze_terms_pdf(
    pdf_bytes: bytes,
    insurer: str,
    api_key: str,
    lang: str = "el",
    filename: str = "",
) -> dict:
    """
    Analyze a policy Terms/Wording PDF for exclusions.

    Strategy:
      - Extract text from pages that score high on exclusion keywords
      - Split into chunks ≤ 3 500 chars
      - Run a focused Claude "exclusion hunter" call per chunk
      - Merge + deduplicate all findings

    Returns:
      {
        "insurer":          str
        "pages_scanned":    int
        "pages_selected":   int
        "chunks_analyzed":  int
        "exclusions":       list   ← all findings merged
        "ambiguous_clauses": list
        "critical_count":   int
        "high_count":       int
        "summary_flags":    list   ← short human-readable flags
      }
    """
    if not _PYMUPDF_OK:
        return _empty_terms_result(insurer, "PyMuPDF not installed — install fitz")

    client_obj = anthropic.Anthropic(api_key=api_key)

    # ── 1. Extract and score pages ──
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        scored_pages = []

        for i, page in enumerate(doc):
            text  = page.get_text().strip()
            score = _score_exclusion_page(text)
            if score >= _MIN_PAGE_SCORE:
                scored_pages.append((i + 1, score, text))

        doc.close()

    except Exception as e:
        return _empty_terms_result(insurer, f"PDF read error: {e}")

    if not scored_pages:
        return _empty_terms_result(
            insurer,
            f"No exclusion-relevant pages found in {filename or 'PDF'}"
        )

    # Sort by score descending, keep top pages that fit budget
    scored_pages.sort(key=lambda x: -x[1])
    selected = [(pg, tx) for pg, _, tx in scored_pages]

    # ── 2. Build chunks ──
    chunks = _build_chunks(selected)

    # ── 3. Run Claude on each chunk ──
    all_exclusions     = []
    all_ambiguous      = []
    chunks_analyzed    = 0

    for ci, chunk in enumerate(chunks):
        prompt = _build_hunter_prompt(chunk, insurer, lang)
        st.info(
            f"🔍 {insurer} — Terms chunk {ci + 1}/{len(chunks)} "
            f"({len(chunk):,} chars)…",
            icon="📄"
        )

        for attempt in range(MAX_RETRIES):
            try:
                resp = client_obj.messages.create(
                    model=MODEL,
                    max_tokens=1200,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text.strip()
                raw = re.sub(r"```json|```", "", raw).strip()
                parsed = json.loads(raw)

                excl = parsed.get("exclusions", [])
                amb  = parsed.get("ambiguous_clauses", [])
                all_exclusions.extend(excl)
                all_ambiguous.extend(amb)
                chunks_analyzed += 1
                break

            except anthropic.RateLimitError:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_WAIT_BASE * (2 ** attempt)
                    st.warning(f"⏳ Rate limit — waiting {wait}s…")
                    time.sleep(wait)
                else:
                    st.error(f"Rate limit after {MAX_RETRIES} retries for chunk {ci+1}")
                    break

            except (json.JSONDecodeError, anthropic.APIStatusError) as e:
                st.warning(f"⚠️ Chunk {ci+1} parse error: {e}")
                break

        # Small delay between chunks to avoid rate limit
        if ci < len(chunks) - 1:
            time.sleep(3)

    # ── 4. Deduplicate by (category + exact_wording[:40]) ──
    seen = set()
    unique_exclusions = []
    for exc in all_exclusions:
        key = (exc.get("category", ""), exc.get("exact_wording", "")[:40].lower())
        if key not in seen:
            seen.add(key)
            unique_exclusions.append(exc)

    # Deduplicate ambiguous clauses
    unique_ambiguous = list(dict.fromkeys(a.strip() for a in all_ambiguous if a.strip()))

    # ── 5. Build summary flags ──
    critical_count = sum(1 for e in unique_exclusions if e.get("severity") == "CRITICAL")
    high_count     = sum(1 for e in unique_exclusions if e.get("severity") == "HIGH")
    summary_flags  = _build_summary_flags(unique_exclusions, unique_ambiguous)

    return {
        "insurer":           insurer,
        "pages_scanned":     total_pages,
        "pages_selected":    len(selected),
        "chunks_analyzed":   chunks_analyzed,
        "exclusions":        unique_exclusions,
        "ambiguous_clauses": unique_ambiguous,
        "critical_count":    critical_count,
        "high_count":        high_count,
        "summary_flags":     summary_flags,
    }


def _build_summary_flags(exclusions: list, ambiguous: list) -> list:
    """Build short human-readable risk flags from found exclusions."""
    flags = []
    sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}

    categories_seen = {}
    for exc in exclusions:
        cat = exc.get("category", "other")
        sev = exc.get("severity", "MEDIUM")
        if cat not in categories_seen or (
            ["MEDIUM","HIGH","CRITICAL"].index(sev) >
            ["MEDIUM","HIGH","CRITICAL"].index(categories_seen[cat])
        ):
            categories_seen[cat] = sev

    for cat, sev in categories_seen.items():
        emoji = sev_emoji.get(sev, "⚪")
        label = {
            "life_support":    "Τεχνητή υποστήριξη ζωής",
            "dialysis":        "Αιμοκάθαρση",
            "terminal_care":   "Παρηγορητική φροντίδα",
            "mental_health":   "Ψυχική υγεία",
            "pre_existing":    "Προϋπάρχουσες παθήσεις",
            "waiting_period":  "Περίοδος αναμονής",
            "benefit_cap":     "Ανώτατο κεφάλαιο παροχής",
            "general_exclusion": "Γενική εξαίρεση",
            "other":           "Εξαίρεση",
        }.get(cat, cat.replace("_", " ").title())

        # Add limit value if available
        limits = [
            e.get("limit_value") for e in exclusions
            if e.get("category") == cat and e.get("limit_value")
        ]
        if limits:
            flags.append(f"{emoji} {label}: {limits[0]}")
        else:
            flags.append(f"{emoji} {label}")

    if ambiguous:
        flags.append(f"⚠️ Αμφίσημοι όροι ({len(ambiguous)})")

    return flags


def _empty_terms_result(insurer: str, reason: str = "") -> dict:
    return {
        "insurer":           insurer,
        "pages_scanned":     0,
        "pages_selected":    0,
        "chunks_analyzed":   0,
        "exclusions":        [],
        "ambiguous_clauses": [],
        "critical_count":    0,
        "high_count":        0,
        "summary_flags":     [],
        "_reason":           reason,
    }
