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
| HAL Assistant | AI chat with Ashlar Insurance context |
| Quote Engine | Upload PDFs, compare insurance plans |
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

*Confidential — Pantelis Kourbelas | Ashlar Insurance | v1.0 May 2026*
