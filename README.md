# HAL Dashboard — Ashlar Insurance

> **HAL** — Heuristically Programmed Algorithmic Layer  
> Personal AI operating system for Pantelis Kourbelas · Ashlar Insurance

---

## Quick Deploy to Streamlit Cloud

1. Push this folder to a GitHub repo (e.g. `ashlar-hal`)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select repo
3. Main file: `app.py`
4. Add secrets (Settings → Secrets):

```toml
Claude_API_Key = "sk-ant-api03-..."
HAL_PIN = "your-sha256-pin-hash"
```

### Generate your PIN hash
```bash
python3 -c "import hashlib; print(hashlib.sha256('YOUR-PIN'.encode()).hexdigest())"
```
Paste the output as the `HAL_PIN` secret value.

---

## Modules

### 🏛 Business (Ashlar Insurance) — public layer
| Module | Description |
|--------|-------------|
| HAL Assistant | AI chat with Ashlar Insurance context · code execution (Claude can generate real PDFs/files, not just describe them) |
| Quote Engine | Upload PDFs, compare insurance plans, terms/exclusions analysis, themed PPTX export |
| Document Filler | Auto-fill forms from source documents |
| Communications | Emails, appeals, renewals, letters |
| Commissions | Upload statements, track P&L |
| Market Intel | Niche analysis, expansion strategy |
| Clients | Active cases, policy tracker |
| App Builder | Generate Python/Streamlit/Netlify code |
| PetsHealth | Pet insurance tools & marketing |

### 🔒 Private — PIN protected
| Module | Description |
|--------|-------------|
| Lodge Secretary | Masonic correspondence (Στ∴ ΑΚΡΟΠΟΛΙΣ 84) |
| Minutes & Docs | Official Masonic minutes generator |
| Attendance | Member presence tracker |
| Events & Gala | Φιλανθρωπική εκδήλωση manager |
| Financial Planner | Retirement model, savings tracker |
| Health & Gym | Workout plans, health coach |

---

## Local Development

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Edit secrets.toml with your keys
streamlit run app.py
```

---

## Tech Stack
- **Frontend**: Streamlit
- **AI**: Anthropic Claude (claude-sonnet-4-6)
- **PDF**: ReportLab, pypdf2
- **PPT**: python-pptx
- **Data**: pandas, Google Sheets via gspread
- **Deploy**: Streamlit Cloud

---

## Changelog — Bug-fix pass

This package is a cleaned-up version of the original upload. Changes made:

**Fixed**
- `render_quotes()`: three `return` statements inside `with tab_live:` / `with tab_pdf:` were exiting the whole function early, which silently broke the "PDF → AI Extraction" and "Saved Results" tabs under several conditions. Restructured as `if/else` so each tab only skips its own content.
- Standardized every hardcoded model string on `claude-sonnet-4-6` (previously split between that and the older dated snapshot `claude-sonnet-4-20250514` across 9 call sites in `app.py`). `config.py`'s shared `MODEL` constant updated too.
- Added `try/except` around Anthropic API calls in `render_finance`, `render_health`, `render_apps`, and `render_pets` — these had none, so an invalid API key, rate limit, or network error would crash the entire page with a raw traceback instead of showing an error in that module.
- Added missing/empty-input feedback (`st.error` / `st.warning`) to the "Generate" buttons in `render_finance`, `render_health`, `render_apps`, `render_pets`, `render_kira_nurse`, and `render_kira_pet_hal` — previously clicking these with no API key or empty required field did nothing visible.
- Removed two dead `sym = _sym(...)` variables in `pptx_builder.py` (computed but never used).
- Updated the model reference in this README to match.

**Removed**
- `brochures/april  .pdf` — exact duplicate of `brochures/april.pdf` (same MD5 hash, just a typo'd filename with trailing spaces).
- `Renewals module` (the loose top-level file) — an earlier standalone draft of the renewals logic that's already fully merged into `app.py`'s `render_renewals()`. Kept only the version that's actually wired into the router.

**Verified, left as-is**
- `render_documents()` is an intentional placeholder/stub per the original README — not touched, since completing it is a feature request rather than a bug fix.
- `extraction.py` / `analysis.py` were reviewed in depth: retry/backoff logic, JSON parsing, and `compute_score()`'s weighting all check out correctly.
- All 21 module/mode combinations (16 business + 5 private) verified to render without exceptions via Streamlit's `AppTest` harness, including with a deliberately invalid API key to confirm graceful error handling.

---

## Changelog — Feature pass (ported from chi-quote-demo-app)

Five modules were reviewed from `chiinsurancebrokers/chi-quote-demo-app` and selectively ported in. `email_gate.py`, `lock_screen.py`, and `trial_lock.py` (the demo's 7-quote paywall) were intentionally **not** ported — they're a sales-funnel mechanism for an unknown public, not something HAL (your own internal tool) needs.

**Added**
- `exclusions_detector.py` + `terms_analyzer.py` — every PDF extraction now also runs a best-effort exclusions/safety scan (`_safety_rating`, `_risk_flags` on the proposal dict, surfaced as an expander next to each coverage score). New **"🔍 Terms Analyzer"** tab in Quote Engine for scanning a full Terms & Conditions PDF on its own — chunks the document, hunts for exclusions/caps/ambiguous clauses with Claude, summarizes findings by severity.
- `greek_insurers.py` — auto-detects Greek vs. international insurers in a comparison, localizes coverage values to Greek for Greek companies, and warns when a comparison mixes the two (since several coverage categories simply don't exist in the Greek market and a 1:1 comparison would be misleading).
- `language_profiles.py` — Greek/English detection by Unicode ratio; used to auto-select the Terms Analyzer's working language from the uploaded PDF.
- `themes.py` — 10 PPTX color themes ported in; `pptx_builder.generate_pptx()` gained an optional `theme=` parameter (defaults to `"ocean"`, matching the prior look exactly — fully backward compatible with existing callers). A theme picker was added to the Quote Engine's PPTX export step.
- **Code execution for HAL Assistant** — the chat now includes Anthropic's `code_execution_20250825` server tool, so HAL can actually run Python/Bash and generate real files (PDFs, etc.) instead of only describing how to. Generated files are detected via a `===FILE:name===`/base64/`===ENDFILE===` marker convention the system prompt asks Claude to emit, decoded, and offered as Streamlit download buttons.

**Reviewed but not ported as-is**
- `chi-quote-demo-app/pptx_builder.py` was compared line-by-line against HAL's own — it's actually a **less clean** intermediate version (still has the two dead `sym = _sym(...)` variables HAL had already removed, plus `lang` and `terms_results` parameters that are declared but never used in the function body). Only its working part — `themes.py` — was carried over; HAL's own `pptx_builder.py` was kept as the base.

**Fixed in passing**
- `terms_analyzer.py` had an unused `base64` import and a `last_error` variable that was assigned but never read (the rate-limit branch logs a warning but doesn't re-raise, unlike `extraction.py`'s equivalent loop) — cleaned up during the port.

---

*Confidential — Pantelis Kourbelas | Ashlar Insurance | v1.0 May 2026*
