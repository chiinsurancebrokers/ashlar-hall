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

## Changelog — Multi-file attachments in HAL Assistant

The HAL Assistant chat (the top-level "Chat with HAL" view, not the Quote Engine module) now accepts file attachments directly. Drop one or more PDFs, images, CSV/TXT/JSON/MD files into the panel above the chat input, then ask HAL anything — `"compare these two quotes"`, `"summarise this T&C in Greek"`, `"which of these screenshots has the lower deductible?"`. Files stay in conversation history so follow-up questions work without re-uploading.

**Added**
- `_hal_build_api_messages()` helper in `app.py` — translates `chat_history` entries into Anthropic API content blocks. PDFs go through `extraction.smart_pdf_to_text()` first when they're large (saves tokens, identical strategy to Quote Engine), otherwise sent as base64 `document` blocks. Images become base64 `image` blocks. Text-ish files (txt/csv/json/md) are inlined as labelled text blocks. Plain text messages stay strings, so token cost only grows when files are actually attached.
- `_hal_mime_for()` helper — pins MIME from file extension because `UploadedFile.type` is sometimes empty or generic, which would mis-route a PDF to the text branch.
- Always-visible attachment panel above the chat input: a `st.file_uploader(accept_multiple_files=True)` on the left, a live "staged files" list with size summary and a "Clear staged files" button on the right.
- Chat history renderer shows a small `📎 filename.pdf` chip line above each user turn that had attachments, so the conversation visibly remembers what was sent.
- System prompt for the business mode picked up a `FILE ATTACHMENTS` section telling HAL to do the task directly (produce the comparison table / summary / recommendation) instead of redirecting the user to the Quote Engine module.
- Voice tab (Groq/Whisper + ElevenLabs path) also routes through `_hal_build_api_messages()`, so a voice follow-up after a file upload still sees the attached files in context.
- The "🗑 Clear conversation" button now also clears any staged-but-unsent files and remounts the uploader, so the next session starts clean.

**Design choices**
- Files are attached to the **next** user message, not held in a global "context" — this makes intent explicit (you see exactly which turn carries which files) and keeps token cost predictable.
- Uploader is rebuilt with a `key=f"hal_file_uploader_{nonce}"` and the nonce is bumped after each send. Streamlit's `file_uploader` has no public clear-API; bumping the key is the standard idiom for forcing a fresh widget instance.
- No upload size cap is enforced in the app — Streamlit's own `server.maxUploadSize` (default 200 MB) and Claude's API limits handle that. Per the spec decision in the design conversation: "let Claude/Streamlit decide".
- Google Sheets memory log records `[attached: a.pdf, b.pdf]` after the user's text so the rolling memory window remembers context even though it can't store the binaries themselves.

**Verified**
- Helper unit tests pass for: plain text passthrough, PDF+image+text ordering, CSV inlining, MIME extension fallback, empty-prompt placeholder, non-UTF8 byte tolerance, mixed history (only flagged turns expand), and base64 roundtrip.
- `python -m py_compile app.py` clean.

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
