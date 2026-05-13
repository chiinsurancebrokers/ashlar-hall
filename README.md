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
- **AI**: Anthropic Claude (claude-sonnet-4-20250514)
- **PDF**: ReportLab, pypdf2
- **PPT**: python-pptx
- **Data**: pandas, Google Sheets via gspread
- **Deploy**: Streamlit Cloud

---

*Confidential — Pantelis Kourbelas | Ashlar Insurance | v1.0 May 2026*
