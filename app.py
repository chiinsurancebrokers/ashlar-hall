"""
HAL — Heuristically Programmed Algorithmic Layer
Pantelis Kourbelas | Ashlar Insurance
Main Dashboard Entry Point
"""

import streamlit as st
import hashlib
import os
import json
from datetime import datetime

# Rate tables (rate_tables.py in same repo)
try:
    from rate_tables import (
        MORGAN_PRICE_2025, APRIL_2025, IMG_EUROPE_2025,
        RATE_PLANS, CARRIER_BROCHURES,
        lookup_premium, get_brochure_info, _mp_band, _apr_band
    )
    RATES_LOADED = True
except ImportError:
    RATES_LOADED = False

# Google Sheets (tickets persistence)
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HAL · Ashlar Insurance",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── STYLING ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global */
[data-testid="stAppViewContainer"] { background: #F8F6F2; }
[data-testid="stSidebar"] { background: #1C1410; }
[data-testid="stSidebar"] * { color: #E8DDD0 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #A89880 !important; font-size: 12px !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #A89880 !important; font-size: 12px !important; }

/* Sidebar HAL logo area */
.hal-logo { 
    text-align: center; padding: 24px 0 16px; 
    border-bottom: 1px solid #3A2E24; margin-bottom: 16px;
}
.hal-logo .hal-title { 
    font-size: 32px; font-weight: 800; 
    color: #C9A96E !important; letter-spacing: 4px;
}
.hal-logo .hal-sub { 
    font-size: 11px; color: #7A6A5A !important; 
    letter-spacing: 2px; text-transform: uppercase; margin-top: 2px;
}

/* Mode selector tabs */
.mode-btn {
    display: block; width: 100%; padding: 10px 16px; margin: 4px 0;
    border-radius: 8px; border: none; text-align: left;
    cursor: pointer; font-size: 13px; font-weight: 500;
    transition: all 0.2s;
}
.mode-btn-business { background: #C9A96E22; color: #C9A96E !important; }
.mode-btn-business:hover { background: #C9A96E44; }
.mode-btn-private { background: #4A3728 22; color: #A89880 !important; }

/* Cards */
.hal-card {
    background: white; border-radius: 12px; padding: 20px 24px;
    border: 1px solid #E8E0D5; margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.hal-card-dark {
    background: #1C1410; border-radius: 12px; padding: 20px 24px;
    border: 1px solid #3A2E24; margin-bottom: 16px;
}

/* Module tiles */
.module-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 8px; }
.module-tile {
    background: white; border: 1px solid #E8E0D5; border-radius: 10px;
    padding: 18px; cursor: pointer; transition: all 0.15s;
    text-decoration: none;
}
.module-tile:hover { border-color: #C9A96E; box-shadow: 0 2px 8px rgba(201,169,110,0.15); }
.module-tile .tile-icon { font-size: 28px; margin-bottom: 8px; }
.module-tile .tile-name { font-size: 14px; font-weight: 600; color: #2C1810; }
.module-tile .tile-desc { font-size: 12px; color: #7A6A5A; margin-top: 4px; }

/* Status badge */
.badge { 
    display: inline-block; padding: 2px 8px; border-radius: 20px; 
    font-size: 11px; font-weight: 600;
}
.badge-live { background: #EAF3DE; color: #27500A; }
.badge-dev  { background: #FAEEDA; color: #633806; }
.badge-private { background: #FCEBEB; color: #A32D2D; }

/* Section header */
.section-header {
    font-size: 11px; font-weight: 600; letter-spacing: 2px; 
    text-transform: uppercase; color: #7A6A5A; 
    border-bottom: 1px solid #E8E0D5; padding-bottom: 8px; margin-bottom: 16px;
}

/* Chat area */
.hal-chat-input { border-radius: 10px !important; }
.hal-response {
    background: white; border-left: 3px solid #C9A96E; 
    padding: 16px 20px; border-radius: 0 10px 10px 0; margin-top: 8px;
}

/* PIN input */
.pin-container { max-width: 320px; margin: 60px auto; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state.mode = "business"      # "business" | "private"
if "private_unlocked" not in st.session_state:
    st.session_state.private_unlocked = False
if "active_module" not in st.session_state:
    st.session_state.active_module = "home"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── HELPERS ───────────────────────────────────────────────────────────────────
def check_pin(pin_input):
    """Check PIN against stored hash in secrets."""
    stored = st.secrets.get("HAL_PIN", "")
    if not stored:
        return False
    return hashlib.sha256(pin_input.encode()).hexdigest() == stored

def get_gsheet():
    """Connect to HAL Google Sheet. Returns (tickets_ws, log_ws) or (None, None)."""
    if not GSHEETS_AVAILABLE:
        return None, None
    try:
        creds_dict = dict(st.secrets.get("gcp_service_account", {}))
        if not creds_dict:
            return None, None
        # Fix newlines in private key
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = st.secrets.get("HAL_SHEET_ID", "")
        if not sheet_id:
            return None, None
        wb = client.open_by_key(sheet_id)
        try:
            tickets_ws = wb.worksheet("Tickets")
        except Exception:
            tickets_ws = wb.add_worksheet("Tickets", rows=500, cols=10)
            tickets_ws.append_row(["ID","Client","Subject","Status","Priority","Created","Updated"])
        try:
            log_ws = wb.worksheet("Log")
        except Exception:
            log_ws = wb.add_worksheet("Log", rows=1000, cols=6)
            log_ws.append_row(["Timestamp","TicketID","Client","Action","OldStatus","NewStatus"])
        return tickets_ws, log_ws
    except Exception as e:
        return None, None


def load_tickets_from_sheet(ws):
    """Load all tickets from Google Sheet into list of dicts."""
    if ws is None:
        return None
    try:
        rows = ws.get_all_records()
        return [
            {
                "id":       r.get("ID", ""),
                "client":   r.get("Client", ""),
                "subject":  r.get("Subject", ""),
                "status":   r.get("Status", "Open"),
                "priority": r.get("Priority", "🟡 Medium"),
                "created":  r.get("Created", ""),
                "updated":  r.get("Updated", ""),
            }
            for r in rows if r.get("ID")
        ]
    except Exception:
        return None


def save_ticket_to_sheet(ws, ticket):
    """Append a new ticket row to Google Sheet."""
    if ws is None:
        return False
    try:
        ws.append_row([
            ticket["id"], ticket["client"], ticket["subject"],
            ticket["status"], ticket["priority"],
            ticket.get("created", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ticket.get("updated", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ])
        return True
    except Exception:
        return False


def update_ticket_in_sheet(ws, log_ws, ticket_id, new_status, old_status, client):
    """Update a ticket status in Google Sheet."""
    if ws is None:
        return False
    try:
        cell = ws.find(ticket_id)
        if cell:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            # Status is column 4, Updated is column 7
            ws.update_cell(cell.row, 4, new_status)
            ws.update_cell(cell.row, 7, now)
            if log_ws:
                log_ws.append_row([now, ticket_id, client, "Status change", old_status, new_status])
        return True
    except Exception:
        return False


def delete_ticket_from_sheet(ws, ticket_id):
    """Delete a ticket row from Google Sheet."""
    if ws is None:
        return False
    try:
        cell = ws.find(ticket_id)
        if cell:
            ws.delete_rows(cell.row)
        return True
    except Exception:
        return False


def get_api_key():
    return (
        st.secrets.get("Claude_API_Key") or
        st.secrets.get("ANTHROPIC_API_KEY") or
        st.secrets.get("claude_api_key") or ""
    )

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="hal-logo">
        <div class="hal-title">HAL</div>
        <div class="hal-sub">Ashlar Intelligence Layer</div>
    </div>
    """, unsafe_allow_html=True)

    # Mode switcher
    st.markdown("**Mode**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "🏛 Business",
            use_container_width=True,
            type="primary" if st.session_state.mode == "business" else "secondary"
        ):
            st.session_state.mode = "business"
            st.session_state.active_module = "home"
            st.rerun()
    with col2:
        if st.button(
            "🔒 Private",
            use_container_width=True,
            type="primary" if st.session_state.mode == "private" else "secondary"
        ):
            st.session_state.mode = "private"
            st.session_state.active_module = "home"
            st.rerun()

    st.divider()

    # Module navigation — changes based on mode
    if st.session_state.mode == "business":
        st.markdown('<div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#7A6A5A;margin-bottom:8px">Ashlar Insurance</div>', unsafe_allow_html=True)

        modules_business = [
            ("🏠", "home", "Dashboard"),
            ("💬", "hal_chat", "HAL Assistant"),
            ("📊", "quotes", "Quote Engine"),
            ("📄", "documents", "Document Filler"),
            ("✉️", "comms", "Communications"),
            ("📈", "commissions", "Commissions"),
            ("🔍", "market", "Market Intel"),
            ("🤝", "clients", "Clients"),
            ("🏗️", "apps", "App Builder"),
            ("🐾", "pets", "PetsHealth"),
            ("🩺", "kira_nurse", "Kira AI Nurse"),
            ("🧠", "chi_analyzer", "Insurance Analyzer"),
            ("🌐", "chi_portal", "Client Portals"),
            ("🐱", "kira_pet", "Kira Pet"),
        ]
        for icon, key, label in modules_business:
            active = st.session_state.active_module == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary"
            ):
                st.session_state.active_module = key
                st.rerun()

    else:
        if st.session_state.private_unlocked:
            st.markdown('<div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#7A6A5A;margin-bottom:8px">Private Modules</div>', unsafe_allow_html=True)

            modules_private = [
                ("🏠", "home", "Dashboard"),
                ("💬", "hal_chat", "HAL Assistant"),
                ("🏛️", "lodge", "Lodge Secretary"),
                ("📋", "minutes", "Minutes & Docs"),
                ("👥", "attendance", "Attendance"),
                ("📅", "events", "Events & Gala"),
                ("💰", "finance", "Financial Planner"),
                ("💪", "health", "Health & Gym"),
                ("🔑", "settings_private", "Settings"),
            ]
            for icon, key, label in modules_private:
                active = st.session_state.active_module == key
                if st.button(
                    f"{icon}  {label}",
                    key=f"nav_p_{key}",
                    use_container_width=True,
                    type="primary" if active else "secondary"
                ):
                    st.session_state.active_module = key
                    st.rerun()

            st.divider()
            if st.button("🔓 Lock Private Mode", use_container_width=True):
                st.session_state.private_unlocked = False
                st.session_state.mode = "business"
                st.session_state.active_module = "home"
                st.rerun()

    st.divider()

    # API key status
    api_key = get_api_key()
    if api_key:
        st.success("🔑 API key loaded", icon="✅")
    else:
        api_key = st.text_input("Claude API Key", type="password", key="api_key_input")

    st.markdown('<div style="font-size:11px;color:#4A3728;margin-top:8px;text-align:center">HAL v1.0 · May 2026</div>', unsafe_allow_html=True)


# ── PRIVATE LOCK SCREEN ───────────────────────────────────────────────────────
def render_pin_screen():
    st.markdown('<div class="pin-container">', unsafe_allow_html=True)
    st.markdown("## 🔒 Private Mode")
    st.markdown("Enter your PIN to unlock personal and lodge modules.")
    pin = st.text_input("PIN", type="password", max_chars=8, label_visibility="collapsed", placeholder="Enter PIN")
    if st.button("Unlock", type="primary", use_container_width=True):
        if check_pin(pin):
            st.session_state.private_unlocked = True
            st.session_state.active_module = "home"
            st.rerun()
        else:
            st.error("Incorrect PIN.")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

def render_business_home():
    st.markdown("## 🏛 Ashlar Insurance — HAL Dashboard")
    st.caption("Pantelis Kourbelas · Your AI business operating system")

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Clients", "—", help="Pull from commission statements")
    with col2:
        st.metric("Quotes This Month", "—", help="From Quote Engine logs")
    with col3:
        st.metric("Pending Renewals", "—", help="Track renewal dates")
    with col4:
        st.metric("Commission MTD", "—", help="Upload statement to track")

    st.divider()

    # Module grid
    st.markdown('<div class="section-header">Business Modules</div>', unsafe_allow_html=True)

    tiles = [
        ("💬", "HAL Assistant", "Ask anything — quotes, emails, analysis", "hal_chat", "live"),
        ("📊", "Quote Engine", "Compare insurance proposals via PDF upload", "quotes", "live"),
        ("📄", "Document Filler", "Auto-fill forms from contracts", "documents", "live"),
        ("✉️", "Communications", "Emails, appeal letters, renewal notices", "comms", "live"),
        ("📈", "Commissions", "Upload & analyse commission statements", "commissions", "dev"),
        ("🔍", "Market Intel", "Niche analysis & expansion strategy", "market", "live"),
        ("🤝", "Clients", "Client cases & policy tracker", "clients", "dev"),
        ("🏗️", "App Builder", "Generate Python/Streamlit/Netlify apps", "apps", "live"),
        ("🐾", "PetsHealth", "Pet insurance tools & petshealth.gr", "pets", "dev"),
    ]

    for i in range(0, len(tiles), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j < len(tiles):
                icon, name, desc, key, status = tiles[i + j]
                badge_class = "badge-live" if status == "live" else "badge-dev"
                badge_label = "Live" if status == "live" else "In Dev"
                with col:
                    st.markdown(f"""
                    <div class="module-tile">
                        <div class="tile-icon">{icon}</div>
                        <div class="tile-name">{name} <span class="badge {badge_class}">{badge_label}</span></div>
                        <div class="tile-desc">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Open {name}", key=f"open_{key}", use_container_width=True):
                        st.session_state.active_module = key
                        st.rerun()

    st.divider()
    st.markdown('<div class="section-header">Recent Projects</div>', unsafe_allow_html=True)

    projects = [
        ("Ashlar Quote Engine", "Streamlit · Claude API", "github.com/chiinsurancebrokers/chi_quote_engine", "Live"),
        ("Ashlar Client Portal", "Netlify · HTML/JS", "panteliskourbelas-chiinsurancebrokers.netlify.app", "Live"),
        ("Document Filler", "Streamlit · ReportLab · Claude API", "Internal", "Live"),
        ("PPT Quote Generator", "python-pptx · Claude API", "Internal", "Live"),
        ("Ashlar Assurance Site", "WordPress · Breakdance", "ashlar-assurance.com", "In Build"),
        ("petshealth.gr", "HTML · Claude API", "petshealth.gr", "Live"),
    ]

    for name, stack, url, status in projects:
        badge_cls = "badge-live" if status == "Live" else "badge-dev"
        col_a, col_b, col_c, col_d = st.columns([3, 3, 3, 1])
        col_a.markdown(f"**{name}**")
        col_b.caption(stack)
        col_c.caption(url)
        col_d.markdown(f'<span class="badge {badge_cls}">{status}</span>', unsafe_allow_html=True)


def render_private_home():
    st.markdown("## 🔒 Private — Personal Dashboard")
    st.caption("Eyes only · Lodge & Personal modules")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Next Lodge Meeting", "—")
    with col2:
        st.metric("Pending Masonic Tasks", "—")
    with col3:
        st.metric("Savings Rate", "—")

    st.divider()

    tiles = [
        ("🏛️", "Lodge Secretary", "Correspondence, circulars, notices", "lodge"),
        ("📋", "Minutes & Docs", "Generate official Masonic minutes", "minutes"),
        ("👥", "Attendance", "Track member presence per session", "attendance"),
        ("📅", "Events & Gala", "Gala registrations, payments, lists", "events"),
        ("💰", "Financial Planner", "Savings, retirement modelling", "finance"),
        ("💪", "Health & Gym", "Workout plans, health monitor", "health"),
    ]

    for i in range(0, len(tiles), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j < len(tiles):
                icon, name, desc, key = tiles[i + j]
                with col:
                    st.markdown(f"""
                    <div class="module-tile">
                        <div class="tile-icon">{icon}</div>
                        <div class="tile-name">{name}</div>
                        <div class="tile-desc">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Open {name}", key=f"open_p_{key}", use_container_width=True):
                        st.session_state.active_module = key
                        st.rerun()


def render_hal_chat():
    import anthropic

    is_private = st.session_state.mode == "private"
    mode_label = "Private · Lodge & Personal" if is_private else "Business · Ashlar Insurance"
    st.markdown(f"## 💬 HAL Assistant — {mode_label}")

    system_prompt_business = """You are HAL — the AI operating system for Pantelis Kourbelas, founder of Ashlar Insurance (formerly CHI Insurance Brokers), Athens, Greece. 

You specialise in international health insurance brokerage. Key knowledge:
- Carriers: Groupama, Generali, Ethniki, Morgan Price, NOW Health, Bupa Global, Safe Pet System
- Greek domestic plans: no free-network outpatient, no dental treatment, no psychiatric outpatient, no MRI/PET/CT outside hospitalisation. Greek deductibles: per-hospitalisation OR annual (important difference).
- International plans: full outpatient, diagnostics, physio, dental, psychiatric depending on plan.
- Bupa Global claim expertise: formal complaint procedure, FSPO (Dublin), 7-day escalation protocol.
- Tech stack: Python, Streamlit, Netlify, Claude API, ReportLab, python-pptx, Firebase, Google Sheets.
- Brand: Ashlar Insurance (ashlar-assurance.com). Pet brand: petshealth.gr.

Respond in the language of the message. Be direct — produce outputs, not advice about producing them. For emails and letters, write them fully ready to send.

LIVE 2025 RATE TABLES (EUR, annual, Area 1 = Europe excl USA):

MORGAN PRICE (area1):
- Standard (HOSPITAL ONLY — NO outpatient): 30y=1,061 | 40y=1,380 | 45y=1,698 | 50y=2,041 | 55y=2,810 | 60y=3,548 | 65y=4,719
- Standard Plus (hospital + outpatient 80% + MRI/CT/PET): 30y=1,322 | 40y=1,719 | 45y=2,136 | 50y=2,495 | 55y=3,436 | 60y=4,338 | 65y=5,810
- Comprehensive (full: hospital + outpatient + dental + optical + mental health): 30y=2,247 | 40y=2,921 | 45y=3,690 | 50y=4,104 | 55y=5,656 | 60y=7,849 | 65y=10,647

CRITICAL: Morgan Price Standard covers INPATIENT ONLY. For outpatient coverage, recommend Standard Plus minimum.

APRIL (area1):
- International (hospital + some outpatient): 30y=1,940 | 40y=2,501 | 45y=2,869 | 50y=3,700 | 55y=4,913 | 60y=6,670 | 65y=10,011
- Executive (full outpatient + maternity option): 30y=4,459 | 40y=5,743 | 45y=6,596 | 50y=8,640 | 55y=10,678 | 60y=13,675 | 65y=20,142

IMG (area1, EUR 150 deductible):
- Silver: 30y=1,813 | 40y=2,339 | 45y=2,872 | 50y=3,764 | 55y=4,993 | 60y=6,366 | 65y=8,427
- Gold: 30y=2,320 | 40y=3,004 | 45y=3,694 | 50y=4,854 | 55y=6,450 | 60y=8,233 | 65y=10,914
- Platinum: 30y=2,912 | 40y=3,797 | 45y=4,686 | 50y=6,178 | 55y=8,238 | 60y=10,535 | 65y=13,987

Area 2 (Worldwide incl USA): ~2.2–2.5x Area 1.
Always state exact plan name, area, annual premium in EUR, and whether outpatient is included."""

    system_prompt_private = """You are HAL — the private AI assistant for Pantelis Kourbelas. In this private mode you have access to lodge and personal context.

LODGE: You assist as secretary for Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ) and ΚΛΕΙΣ ΑΛΗΘΕΙΑΣ αρ. 1 (A.A.S.R.). Always use Masonic ∴ notation. Style: contemporary Greek Tektonic — NOT archaic. Closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος. Lodge email: st.akropolis.84@gmail.com. Speech order: 18 levels (Μαθηταί → Μέγας Διδάσκαλος).

PERSONAL: Financial adviser, nurse, gym coach. Help with savings plans, retirement modelling, workout programmes, health monitoring.

Never mix lodge content with business sessions. Respond in Greek unless asked otherwise."""

    system = system_prompt_private if is_private else system_prompt_business

    api_key = get_api_key() or st.session_state.get("api_key_input", "")

    # Chat history display
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.info("HAL is ready. Ask anything about insurance, clients, quotes, documents, or use quick actions below.")
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.chat_message("user").write(msg["content"])
                else:
                    st.chat_message("assistant").write(msg["content"])

    # Quick actions
    if not st.session_state.chat_history:
        st.markdown("**Quick actions:**")
        quick = []
        if is_private:
            quick = [
                "Draft a circular to the lodge brothers in Greek Tektonic style",
                "Generate agenda for next lodge session",
                "Write a welfare toast in correct hierarchy order",
                "Create a savings plan for retirement in 15 years",
                "Design a 4-week gym programme for strength",
            ]
        else:
            quick = [
                "Compare Generali vs Morgan Price for a 50-year-old client",
                "Draft a renewal notice email in Greek",
                "Write a Bupa appeal letter for a denied claim",
                "Analyse niche markets for expanding into international health insurance",
                "Generate a quote comparison PPT outline",
                "Draft a cold outreach email to a corporate HR manager",
            ]
        cols = st.columns(2)
        for i, q in enumerate(quick):
            with cols[i % 2]:
                if st.button(q, key=f"quick_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    st.rerun()

    # ── VOICE ─────────────────────────────────────────────────────────────────
    # Voice API keys
    groq_key = (st.secrets.get("GROQ_API_KEY","") or
                st.secrets.get("groq_api_key",""))
    oai_key  = (st.secrets.get("OPENAI_API_KEY","") or
                st.secrets.get("openai_api_key",""))   # fallback if no Groq
    stt_key  = groq_key or oai_key                     # prefer Groq (free)
    el_key   = (st.secrets.get("ELEVENLABS_API_KEY","") or
                st.secrets.get("elevenlabs_api_key",""))
    el_voice = st.secrets.get("ELEVENLABS_VOICE_ID","aTP4J5SJLQl74WTSRXKW")

    voice_tab1, voice_tab2 = st.tabs([
        "🎙️ Quick Voice (Web Speech)",
        "🔊 Full Voice (Groq/Whisper + ElevenLabs)" + (" ✓" if stt_key and el_key else " · setup required"),
    ])

    # ── TAB 1: Web Speech API — instant, free, copy-paste ────────────────────
    with voice_tab1:
        import streamlit.components.v1 as _cv1
        st.caption("Browser speech recognition · Free · Greek · Copy transcript → paste into chat")
        _cv1.html("""<!DOCTYPE html><html><head><style>
body{margin:0;padding:0;font-family:system-ui,sans-serif;background:transparent}
#bar{display:flex;align-items:center;gap:10px;background:rgba(28,20,16,.6);border:1px solid rgba(201,169,110,.3);border-radius:10px;padding:10px 14px}
#mic{background:none;border:2px solid #C9A96E;border-radius:50%;width:36px;height:36px;font-size:18px;cursor:pointer;color:#C9A96E;flex-shrink:0}
#mic.active{background:#C9A96E;color:#1C1410}
#status{font-size:12px;color:#A89880;flex:1}
#result{display:none;flex:2;background:rgba(201,169,110,.1);border:1px solid rgba(201,169,110,.3);border-radius:6px;padding:6px 10px;font-size:13px;color:#E8DDD0;word-break:break-word}
#copy{display:none;background:#C9A96E;color:#1C1410;border:none;border-radius:6px;padding:6px 14px;font-weight:700;cursor:pointer;font-size:12px;flex-shrink:0}
</style></head><body>
<div id="bar">
<button id="mic" onclick="toggleVoice()">🎙️</button>
<div id="status">Click 🎙️ to speak — Chrome / Safari</div>
<div id="result"></div>
<button id="copy" onclick="copyText()">📋 Copy</button>
</div>
<script>
var recognition,listening=false,transcript="";
function toggleVoice(){
  if(!("webkitSpeechRecognition"in window||"SpeechRecognition"in window)){document.getElementById("status").textContent="Not supported — use Chrome";return;}
  if(listening){recognition.stop();return;}
  recognition=new(window.SpeechRecognition||window.webkitSpeechRecognition)();
  recognition.lang="el-GR";recognition.interimResults=true;
  recognition.onstart=function(){listening=true;document.getElementById("mic").classList.add("active");document.getElementById("status").textContent="🔴 Listening...";document.getElementById("result").style.display="none";document.getElementById("copy").style.display="none";};
  recognition.onresult=function(e){transcript=Array.from(e.results).map(r=>r[0].transcript).join("");document.getElementById("result").textContent=transcript;document.getElementById("result").style.display="block";};
  recognition.onend=function(){listening=false;document.getElementById("mic").classList.remove("active");if(transcript){document.getElementById("status").textContent="✅ Copy and paste into chat below ↓";document.getElementById("copy").style.display="block";}else{document.getElementById("status").textContent="Click 🎙️ to speak";}};
  recognition.onerror=function(e){listening=false;document.getElementById("mic").classList.remove("active");document.getElementById("status").textContent="Error: "+e.error+" — try Chrome";};
  recognition.start();
}
function copyText(){if(!transcript)return;navigator.clipboard.writeText(transcript).then(function(){document.getElementById("copy").textContent="✅ Copied!";setTimeout(function(){document.getElementById("copy").textContent="📋 Copy";},2000);});}
</script></body></html>""", height=60, scrolling=False)

    # ── TAB 2: Whisper + ElevenLabs — accurate, speaks back ──────────────────
    with voice_tab2:
        if not stt_key or not el_key:
            st.info("Add **GROQ_API_KEY** (free at console.groq.com) + **ELEVENLABS_API_KEY** to Streamlit secrets.")
            st.caption("ELEVENLABS_VOICE_ID default: aTP4J5SJLQl74WTSRXKW (Eleni) · Groq is free, faster than OpenAI Whisper")
        else:
            st.caption("Record → Whisper transcribes (Greek 95% accuracy) → Claude responds → ElevenLabs speaks back")
            audio_val = st.audio_input("🎙️ Speak to HAL", key="hal_voice_input")
            if audio_val is not None:
                import urllib.request as _urv, json as _jv, base64 as _b64v
                audio_bytes = audio_val.read()
                ab64 = _b64v.b64encode(audio_bytes).decode()

                with st.spinner("🎙️ Transcribing..."):
                    try:
                        if groq_key:
                            # Groq Whisper — free, fast, no billing issues
                            from groq import Groq as _Groq
                            _gc = _Groq(api_key=groq_key)
                            transcript = _gc.audio.transcriptions.create(
                                model="whisper-large-v3",
                                file=("audio.webm", audio_bytes, "audio/webm"),
                                language="el",
                            ).text.strip()
                        else:
                            # Fallback: OpenAI Whisper
                            from openai import OpenAI as _OAI
                            _oc = _OAI(api_key=oai_key)
                            transcript = _oc.audio.transcriptions.create(
                                model="whisper-1",
                                file=("audio.webm", audio_bytes, "audio/webm"),
                                language="el",
                            ).text.strip()
                    except Exception as e:
                        transcript = ""
                        if "401" in str(e):
                            st.error("❌ API key invalid — check GROQ_API_KEY or OPENAI_API_KEY in secrets.")
                        else:
                            st.error(f"Transcription error: {e}")

                if transcript:
                    st.markdown(f"**🗣️ You:** {transcript}")
                    st.session_state.chat_history.append({"role":"user","content":transcript})

                    with st.spinner("HAL thinking..."):
                        try:
                            import anthropic as _ant
                            _cl = _ant.Anthropic(api_key=api_key)
                            # Voice-specific system: formal, no markdown, concise
                            voice_system = system + "\n\nIMPORTANT FOR VOICE MODE: Respond formally and professionally at all times. No bullet points, no markdown, no asterisks. Speak in complete, clear sentences suitable for audio. Keep responses under 3 sentences unless a longer answer is essential. Address the user formally."
                            _r  = _cl.messages.create(
                                model="claude-sonnet-4-6", max_tokens=600,
                                system=voice_system,
                                messages=[{"role":m["role"],"content":m["content"]}
                                          for m in st.session_state.chat_history[-10:]]
                            )
                            reply = _r.content[0].text
                        except Exception as e:
                            reply = f"Error: {e}"
                    st.session_state.chat_history.append({"role":"assistant","content":reply})
                    st.markdown(f"**HAL:** {reply}")

                    with st.spinner("🔊 ElevenLabs speaking..."):
                        # Pronunciation fixes for Greek/English mixed text
                        tts_text = reply
                        _pron = {
                            "Morgan Price":    "Μόργκαν Πράις",
                            "Standard Plus":   "Στάνταρντ Πλας",
                            "Standard":        "Στάνταρντ",
                            "Comprehensive":   "Κόμπριχενσιβ",
                            "International":   "Ιντερνάσιοναλ",
                            "Executive":       "Εξέκιουτιβ",
                            "Platinum":        "Πλάτινουμ",
                            "IMG":             "Άι Εμ Τζι",
                            "April":           "Απρίλ",
                            "Bupa":            "Μπούπα",
                            "outpatient":      "εξωνοσοκομειακά",
                            "inpatient":       "νοσοκομειακή κάλυψη",
                            "deductible":      "απαλλαγή",
                            "premium":         "ασφάλιστρο",
                            "HAL":             "Χαλ",
                            "Ashlar":          "Άσλαρ",
                        }
                        for en, el in _pron.items():
                            tts_text = tts_text.replace(en, el)
                        tts_req = _urv.Request(
                            f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice}",
                            data=_jv.dumps({"text":tts_text,"model_id":"eleven_multilingual_v2",
                                           "voice_settings":{"stability":0.55,"similarity_boost":0.8}}).encode(),
                            headers={"xi-api-key":el_key,"Content-Type":"application/json","Accept":"audio/mpeg"}
                        )
                        try:
                            with _urv.urlopen(tts_req, timeout=30) as r:
                                st.audio(r.read(), format="audio/mpeg", autoplay=True)
                        except Exception as e:
                            st.warning(f"ElevenLabs: {e}")
                else:
                    st.warning("No speech detected — try again.")


    # Input
    user_input = st.chat_input("Message HAL...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        if not api_key:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "⚠️ No API key found. Add Claude_API_Key to your Streamlit secrets."
            })
        else:
            with st.spinner("HAL is thinking..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history
                    ]
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=2000,
                        system=system,
                        messages=messages
                    )
                    reply = response.content[0].text
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"⚠️ Error: {str(e)}"
                    })
        st.rerun()

    if st.session_state.chat_history:
        if st.button("🗑 Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


def render_quotes():
    st.markdown("## 📊 Quote Engine")
    st.caption("Live 2025 rates · Morgan Price · April · IMG · Instant comparison")

    tab_live, tab_pdf, tab_results = st.tabs([
        "⚡ Instant Quote", "📤 Upload & Analyse PDF", "📋 Saved Results"
    ])

    # ══ TAB 1: INSTANT LIVE QUOTE ══════════════════════════════════════════════
    with tab_live:
        if not RATES_LOADED:
            st.warning("rate_tables.py not found in repo. Add it alongside app.py.")
            return

        st.markdown("### Client Details")
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            q_name    = st.text_input("Client name", placeholder="Katia Totikidou")
            q_age     = st.number_input("Age", min_value=0, max_value=80, value=45)
        with qc2:
            q_area    = st.radio("Coverage area",
                                  ["Area 1 — Europe (excl USA)", "Area 2 — Worldwide incl USA"],
                                  horizontal=False)
            area_key  = "area1" if "Area 1" in q_area else "area2"
        with qc3:
            q_notes   = st.text_area("Client priorities / notes", height=100,
                placeholder="e.g. Needs outpatient, travels to USA, cancer history...")

        # Member table
        st.markdown("### Members")
        if "quote_members" not in st.session_state:
            st.session_state.quote_members = [{"name": q_name or "Member 1", "age": q_age}]
        with st.expander("➕ Add family member"):
            m_name = st.text_input("Name", key="m_name")
            m_age  = st.number_input("Age", min_value=0, max_value=80, value=35, key="m_age")
            if st.button("Add member", key="add_member"):
                st.session_state.quote_members.append({"name": m_name, "age": m_age})
                st.rerun()
        for i, m in enumerate(st.session_state.quote_members):
            mc1, mc2 = st.columns([4,1])
            mc1.markdown(f"👤 **{m['name']}** — Age {m['age']}")
            if mc2.button("✕", key=f"del_m_{i}") and len(st.session_state.quote_members) > 1:
                st.session_state.quote_members.pop(i); st.rerun()

        # Plan selection
        st.markdown("### Plans to compare")
        all_plans = [(c, p, n, cov, ded) for c, p, n, cov, ded in RATE_PLANS]
        selected_plans = st.multiselect(
            "Select plans",
            options=[p[2] for p in all_plans],
            default=["Morgan Price Standard", "Morgan Price Comprehensive",
                     "April International", "April Executive",
                     "IMG Silver", "IMG Gold"],
        )

        if st.button("⚡ Generate Comparison", type="primary", use_container_width=True):
            if not st.session_state.quote_members:
                st.warning("Add at least one member.")
            else:
                results = []
                plan_map = {p[2]: p for p in all_plans}

                for plan_name in selected_plans:
                    if plan_name not in plan_map: continue
                    carrier, plan_key, display, coverage, ded_note = plan_map[plan_name]
                    total = 0
                    member_rates = []
                    valid = True
                    for m in st.session_state.quote_members:
                        prem = lookup_premium(carrier, plan_key, m["age"], area_key)
                        if prem is None:
                            valid = False; break
                        total += prem
                        member_rates.append((m["name"], m["age"], prem))
                    if valid:
                        results.append({
                            "plan": display, "carrier": carrier,
                            "total": total, "members": member_rates,
                            "coverage": coverage, "deductible": ded_note,
                        })

                results.sort(key=lambda x: x["total"])
                st.session_state["quote_results"] = results
                st.session_state["quote_client"]  = q_name
                st.session_state["quote_notes"]   = q_notes
                st.session_state["quote_area"]    = q_area
                st.rerun()

        # Display results
        if st.session_state.get("quote_results"):
            results   = st.session_state["quote_results"]
            client    = st.session_state.get("quote_client","Client")
            area_disp = st.session_state.get("quote_area","Area 1")
            members   = st.session_state.get("quote_members",[])

            st.markdown("---")
            st.markdown(f"### 📋 Quote Comparison — {client or 'Client'}")
            st.caption(f"{area_disp} · {len(members)} member(s) · 2025 rates")

            # Summary table
            cheapest = results[0]["total"]
            for i, r in enumerate(results):
                diff     = r["total"] - cheapest
                badge    = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
                diff_str = f"+€{diff:,.0f}/yr" if diff > 0 else "✅ Lowest"
                color    = "#EDFBF0" if i == 0 else "white"

                with st.container():
                    st.markdown(f"""<div style="background:{color};border:1px solid #E8E0D5;
                        border-radius:12px;padding:16px 20px;margin-bottom:10px">
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <div><span style="font-size:18px">{badge}</span>
                            <strong style="font-size:16px;margin-left:8px">{r["plan"]}</strong>
                            <span style="font-size:12px;color:#6B7280;margin-left:10px">{r["deductible"]}</span></div>
                            <div style="text-align:right">
                            <div style="font-size:22px;font-weight:800;color:#1C1410">€{r["total"]:,.0f}/yr</div>
                            <div style="font-size:12px;color:#6B7280">{diff_str}</div>
                            </div>
                        </div>
                        <div style="margin-top:10px;font-size:12px;color:#6B7280">
                        {" · ".join(f"{m[0]}: €{m[2]:,.0f}" for m in r["members"])}
                        </div>
                    </div>""", unsafe_allow_html=True)

            # Export
            st.divider()
            ec1, ec2 = st.columns(2)
            with ec1:
                # Text export
                lines = [f"ASHLAR INSURANCE — Quote Comparison",
                         f"Client: {client} | {area_disp} | {datetime.now().strftime('%d/%m/%Y')}",
                         f"Members: {', '.join(f"{m['name']} ({m['age']}y)" for m in members)}",""]
                for r in results:
                    lines.append(f"{r['plan']}: EUR {r['total']:,.0f}/year")
                    for m in r["members"]:
                        lines.append(f"  {m[0]} (age {m[1]}): EUR {m[2]:,.0f}")
                    lines.append("")
                lines.append("Rates: Morgan Price EU 2025 / April LT 2025 / IMG GPMI Apr-2025")
                quote_text = "\n".join(lines)
                st.download_button("📥 Download quote", quote_text,
                    mime="text/plain", use_container_width=True)
            with ec2:
                if st.button("💬 Send to HAL for narrative", use_container_width=True):
                    qs = "\n".join(f"{r['plan']}: EUR {r['total']:,.0f}/yr" for r in results)
                    notes_txt = ("Notes: " + q_notes) if q_notes else ""
                    msg = f"Quote comparison for {client or 'client'} age {q_age}, {area_disp}:\n\n{qs}\n\n{notes_txt}\n\nWrite a professional email presenting these options and recommending the best fit."
                    st.session_state.chat_history.append({"role":"user","content":msg})
                    st.session_state.active_module = "hal_chat"
                    st.rerun()
            if st.button("🔄 New quote", key="reset_quote"):
                for k in ["quote_results","quote_client","quote_notes","quote_area","quote_members"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

    # ══ TAB 2: PDF UPLOAD ══════════════════════════════════════════════════════
    with tab_pdf:
        st.caption("Upload insurer quote PDFs · Claude extracts & compares")
        uploaded = st.file_uploader("Upload quote PDFs", type=["pdf"], accept_multiple_files=True)
        client_age   = st.number_input("Client age", min_value=0, max_value=100, value=45, key="pdf_age")
        client_notes = st.text_area("Client priorities", placeholder="e.g. Prioritises outpatient, travels to Germany...", key="pdf_notes")
        if st.button("🚀 Analyse PDFs", type="primary", disabled=not uploaded):
            api_key = get_api_key()
            if api_key and uploaded:
                with st.spinner(f"Analysing {len(uploaded)} quotes..."):
                    pdf_names = [f.name for f in uploaded]
                    prompt = (f"Compare these {len(uploaded)} insurance quotes for a {client_age}-year-old: "
                              f"{', '.join(pdf_names)}. "
                              f"Client priorities: {client_notes or 'standard coverage'}. "
                              f"Extract: insurer, plan name, annual premium, key coverage, deductibles, exclusions. "
                              f"Rank from best value to most expensive. Use actual rates from the rate tables if recognisable.")
                    import anthropic
                    client = anthropic.Anthropic(api_key=api_key)
                    r = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000,
                        system=f"You are an expert insurance broker. Rate tables context: Morgan Price Standard age {client_age}y Area1 = EUR {lookup_premium('morgan_price','standard',client_age,'area1'):,} if RATES_LOADED else 'N/A'.",
                        messages=[{"role":"user","content":prompt}])
                    st.markdown(r.content[0].text)

    # ══ TAB 3: SAVED ═══════════════════════════════════════════════════════════
    with tab_results:
        st.info("Quotes generated in the Instant Quote tab appear here. Use 'Send to HAL' to draft a client email.")


def render_documents():
    st.markdown("## 📄 Document Filler")
    st.caption("Upload a blank form + source documents · HAL extracts and fills automatically")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Blank form (PDF)**")
        form_file = st.file_uploader("Upload form to fill", type=["pdf"], key="form_upload")
    with col2:
        st.markdown("**Source documents**")
        source_files = st.file_uploader("Upload contract / policy / data source", type=["pdf", "docx"], accept_multiple_files=True, key="source_upload")

    st.markdown("**Language output**")
    lang = st.radio("", ["Greek (Ελληνικά)", "English"], horizontal=True)

    if st.button("⚡ Fill Form Automatically", type="primary", disabled=not form_file):
        st.info("Form filler ready. Point this to your document_filler app.py for full processing.")


def render_comms():
    st.markdown("## ✉️ Communications Centre")
    st.caption("Emails · Appeal letters · Renewal notices · Quotes · Circulars")

    doc_type = st.selectbox("Document type", [
        "Client email (renewal notice)",
        "Client email (new quote follow-up)",
        "Appeal letter (claim denial)",
        "Complaint letter (insurer)",
        "Provider communication",
        "Cold outreach (corporate HR)",
        "Quote cover letter",
        "General email",
    ])

    col1, col2 = st.columns(2)
    with col1:
        client_name  = st.text_input("Client / recipient name")
        insurer_name = st.text_input("Insurer / company name")
        policy_ref   = st.text_input("Policy / claim reference")
    with col2:
        tone     = st.radio("Tone", ["Professional", "Firm & assertive", "Warm & friendly"], horizontal=True)
        language = st.radio("Language", ["English", "Greek"], horizontal=True)

    context = st.text_area("Key details to include", height=100,
        placeholder="e.g. Claim denied for EUR 12,999.97. Client member since 1996. Annual premium GBP 66,219...")

    if st.button("✍️ Generate Document", type="primary"):
        if not get_api_key():
            st.error("Add Claude_API_Key to Streamlit secrets first.")
        else:
            with st.spinner("HAL is drafting..."):
                import anthropic
                prompt = f"""Write a {doc_type} for {client_name or 'the client'}.
Insurer/company: {insurer_name or 'N/A'}
Policy/claim ref: {policy_ref or 'N/A'}
Tone: {tone}
Language: {language}
Key details: {context}

Produce the full document, ready to send. Include subject line if it's an email."""
                try:
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.markdown("---")
                    st.markdown("### Generated Document")
                    st.markdown(r.content[0].text)
                    st.download_button("📥 Download as text", r.content[0].text, file_name="document.txt")
                except Exception as e:
                    st.error(f"Error: {e}")


# ── Commission functions (inline) ────────────────────────────────────────────
_DEFAULT_COMMISSION_RATES = {
    "3P Insurance":0.15,"Hellas Direct":0.12,"Groupama":0.18,"Generali":0.18,
    "Ethniki":0.16,"Morgan Price":0.20,"NOW Health":0.20,"Bupa Global":0.20,
    "Safe Pet System":0.15,"AXA":0.17,"Interamerican":0.17,"Eurolife":0.16,
    "NN":0.16,"Allianz":0.17,
}

def _calculate_commission(premium, insurer, rate_override=None):
    rate = rate_override or _DEFAULT_COMMISSION_RATES.get(insurer, 0.15)
    return round(float(premium or 0) * rate, 2)

def _commission_report(policies):
    total_premium=0; total_commission=0; by_insurer={}
    for p in policies:
        try: prem=float(str(p.get("premium",0)).replace(",","").replace("€","").replace("£","").strip() or 0)
        except: prem=0
        insurer=p.get("insurer","Unknown")
        comm=_calculate_commission(prem,insurer,p.get("rate_override"))
        total_premium+=prem; total_commission+=comm
        if insurer not in by_insurer: by_insurer[insurer]={"premium":0,"commission":0,"count":0}
        by_insurer[insurer]["premium"]+=prem; by_insurer[insurer]["commission"]+=comm; by_insurer[insurer]["count"]+=1
    return {"total_premium":round(total_premium,2),"total_commission":round(total_commission,2),
            "by_insurer":by_insurer,"policy_count":len(policies)}


# ── POLICY TYPE CONFIG ────────────────────────────────────────────────────────
_POLICY_TYPES = {
    "motor":     {"label":"Motor Insurance","label_el":"Ασφάλεια Οχήματος","icon":"🚗","color":"#1E40AF"},
    "health":    {"label":"Health Insurance","label_el":"Ασφάλεια Υγείας","icon":"❤️","color":"#DC2626"},
    "life":      {"label":"Life Insurance","label_el":"Ασφάλεια Ζωής","icon":"🫀","color":"#7C3AED"},
    "home":      {"label":"Home / Property","label_el":"Ασφάλεια Κατοικίας","icon":"🏠","color":"#059669"},
    "travel":    {"label":"Travel Insurance","label_el":"Ταξιδιωτική Ασφάλεια","icon":"✈️","color":"#0EA5E9"},
    "pet":       {"label":"Pet Insurance","label_el":"Ασφάλεια Κατοικίδιου","icon":"🐾","color":"#0D9488"},
    "liability": {"label":"Professional Liability","label_el":"Επαγγελματική Ευθύνη","icon":"💼","color":"#D97706"},
    "other":     {"label":"Other Policy","label_el":"Άλλη Ασφάλεια","icon":"📋","color":"#6B7280"},
}
_PROVIDERS = ["3P Insurance","Hellas Direct","Groupama","Generali","Ethniki",
              "Morgan Price","NOW Health","Bupa Global","Safe Pet System",
              "AXA","Interamerican","Eurolife","NN","Allianz","Other"]
_PAY_STATUS = ["✅ Paid","🟡 Pending","🔴 Overdue","🔵 Direct Debit"]
_CLM_STATUS = ["🟡 Under review","🔴 Disputed","🟢 Approved","✅ Settled","❌ Rejected"]


def render_commissions():
    st.markdown("## 📈 Commissions Tracker")
    st.caption("Εκτίμηση προμηθειών βάσει ασφαλίστρων · Default rates per insurer")

    tab_calc, tab_rates = st.tabs(["📊 Calculate", "⚙️ Rates"])
    with tab_calc:
        if "comm_policies" not in st.session_state: st.session_state.comm_policies = []
        with st.expander("➕ Add policy"):
            cp1,cp2,cp3 = st.columns(3)
            with cp1:
                cp_client = st.text_input("Client", key="cp_client")
                cp_insurer= st.selectbox("Insurer", _PROVIDERS, key="cp_ins")
            with cp2:
                cp_type = st.selectbox("Type", list(_POLICY_TYPES.keys()),
                    format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",key="cp_type")
                cp_prem = st.number_input("Premium (EUR)", min_value=0.0, key="cp_prem")
            with cp3:
                cp_pno  = st.text_input("Policy No.", key="cp_pno")
                cp_rate = st.number_input("Override rate (%)", min_value=0.0, max_value=50.0,
                    value=float(_DEFAULT_COMMISSION_RATES.get(st.session_state.get("cp_ins",""),0.15)*100),
                    key="cp_rate", format="%.1f")
            if st.button("Add ✓", key="add_comm_pol"):
                st.session_state.comm_policies.append({"client_name":cp_client,"insurer":cp_insurer,
                    "policy_category":cp_type,"premium":cp_prem,"policy_number":cp_pno,"rate_override":cp_rate/100})
                st.rerun()
        if st.session_state.comm_policies:
            rpt = _commission_report(st.session_state.comm_policies)
            s1,s2,s3,s4 = st.columns(4)
            s1.metric("Policies",rpt["policy_count"]); s2.metric("Total Premium",f"€{rpt['total_premium']:,.2f}")
            s3.metric("Est. Commission",f"€{rpt['total_commission']:,.2f}")
            s4.metric("Avg Rate",f"{round(rpt['total_commission']/rpt['total_premium']*100,1) if rpt['total_premium'] else 0}%")
            for ins,data in sorted(rpt["by_insurer"].items(),key=lambda x:x[1]["commission"],reverse=True):
                ci1,ci2,ci3,ci4=st.columns([2,1,1,1])
                ci1.markdown(f"**{ins}**"); ci2.markdown(f"€{data['premium']:,.0f}")
                ci3.markdown(f"**€{data['commission']:,.0f}**"); ci4.markdown(f"{data['count']} policies")
            lines=["Client,Insurer,Type,Premium,Commission,Policy No"]
            for p in st.session_state.comm_policies:
                comm=_calculate_commission(float(p.get("premium",0)),p.get("insurer",""),p.get("rate_override"))
                lines.append(f"{p.get('client_name','')},{p.get('insurer','')},{p.get('policy_category','')},{p.get('premium',0)},{comm},{p.get('policy_number','')}")
            csv_data = "\n".join(lines)
            st.download_button("Export CSV", csv_data, file_name="commissions.csv", mime="text/csv")
        st.markdown("### Default Rates")
        for ins,rate in sorted(_DEFAULT_COMMISSION_RATES.items()):
            r1,r2=st.columns([3,1]); r1.markdown(ins); r2.markdown(f"**{rate*100:.0f}%**")


def render_market():
    st.markdown("## 🔍 Market Intelligence")
    st.caption("Niche analysis · Competitor mapping · Expansion strategy")

    query = st.text_area("Research brief", height=80,
        placeholder="e.g. What are underserved segments in international health insurance for Greeks living abroad?")

    col1, col2 = st.columns(2)
    with col1:
        market = st.multiselect("Markets", ["Greece", "Cyprus", "UK", "UAE", "Germany", "International"], default=["Greece"])
    with col2:
        product = st.multiselect("Products", ["International Health", "Greek Domestic Health", "Life", "Pet", "Expat"], default=["International Health"])

    if st.button("🔬 Analyse Market", type="primary"):
        if not get_api_key() or not query:
            st.warning("Add API key and enter a brief.")
        else:
            with st.spinner("Researching..."):
                import anthropic
                prompt = f"""You are a specialist insurance market analyst for Ashlar Insurance, an independent broker based in Athens expanding from sole trader to international agency.

Research brief: {query}
Target markets: {', '.join(market)}
Products: {', '.join(product)}

Provide:
1. Key niche opportunities with reasoning
2. Underserved client segments
3. Competitive landscape summary
4. Recommended next steps for Ashlar Insurance
5. Specific products or carriers to approach

Be concrete and actionable."""
                try:
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.markdown("### Analysis")
                    st.markdown(r.content[0].text)
                except Exception as e:
                    st.error(f"Error: {e}")


def render_lodge():
    st.markdown("## 🏛️ Lodge Secretary")
    st.caption("Στ∴ ΑΚΡΟΠΟΛΙΣ 84 · Correspondence, circulars, notices")

    doc_type = st.selectbox("Document type", [
        "Circular — general notice",
        "Invitation — session with lecture",
        "Invitation — charitable event",
        "Follow-up — payment / RSVP",
        "Email to Grand Secretariat",
        "Letter for correction / clarification",
        "Internal announcement",
    ])

    addressee = st.text_input("Addressed to", placeholder="Φίλτ∴ Αδ∴ — or Grand Secretary title...")
    subject   = st.text_input("Subject / occasion", placeholder="e.g. Τακτική Συνεδρία, Φιλανθρωπική Εκδήλωση...")
    body      = st.text_area("Key points to include", height=120,
        placeholder="e.g. Meeting on Wednesday at 8pm, lecture by Κραττ∴ Αδ∴ Λεφάκης, followed by Ποτήριον Αγάπης...")

    if st.button("📝 Draft Document", type="primary"):
        if not get_api_key():
            st.error("API key missing.")
        else:
            with st.spinner("Drafting in Masonic style..."):
                import anthropic
                prompt = f"""You are the secretary of Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ).
Draft a {doc_type} with the following:
Addressed to: {addressee}
Subject: {subject}
Key content: {body}

Rules:
- Use contemporary Greek Tektonic style — NOT archaic
- Use ∴ notation throughout (Σεβ∴, Αδ∴, Φίλτ∴, Γραμμ∴, Στ∴ etc.)
- Opening: appropriate salutation for recipient
- Closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος / 6975900189
- From: st.akropolis.84@gmail.com
- Produce complete, ready-to-send document"""
                try:
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1200,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.markdown("---")
                    st.markdown("### Draft")
                    st.markdown(r.content[0].text)
                    st.download_button("📥 Download", r.content[0].text, file_name="lodge_document.txt")
                except Exception as e:
                    st.error(f"Error: {e}")


def render_finance():
    st.markdown("## 💰 Financial Planner")
    st.caption("Personal finance · Savings · Retirement modelling")

    tab1, tab2 = st.tabs(["📊 Retirement Modeller", "💬 Financial Adviser Chat"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            current_age    = st.number_input("Current age", 20, 80, 50)
            retirement_age = st.number_input("Target retirement age", 50, 80, 65)
            monthly_income = st.number_input("Monthly net income (€)", 0, 50000, 3000)
            monthly_save   = st.number_input("Monthly savings (€)", 0, 20000, 500)
        with col2:
            current_savings = st.number_input("Current savings (€)", 0, 1000000, 10000)
            annual_return   = st.slider("Expected annual return (%)", 1.0, 12.0, 5.0, 0.5)
            inflation       = st.slider("Inflation estimate (%)", 1.0, 8.0, 3.0, 0.5)
            target_pension  = st.number_input("Target monthly pension (€)", 0, 20000, 2000)

        if st.button("📈 Model My Retirement", type="primary"):
            years = retirement_age - current_age
            if years > 0:
                import math
                r = annual_return / 100
                months = years * 12
                # Future value of current savings
                fv_savings = current_savings * (1 + r) ** years
                # Future value of monthly contributions
                monthly_r = r / 12
                fv_contributions = monthly_save * (((1 + monthly_r) ** months - 1) / monthly_r)
                total_pot = fv_savings + fv_contributions
                # Sustainable monthly drawdown (4% rule adjusted)
                monthly_drawdown = total_pot * 0.04 / 12
                gap = target_pension - monthly_drawdown

                st.divider()
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Projected Pot", f"€{total_pot:,.0f}")
                col_b.metric("Sustainable Monthly Income", f"€{monthly_drawdown:,.0f}/mo")
                col_c.metric("Gap vs Target", f"€{abs(gap):,.0f}/mo", delta=f"{'Surplus' if gap < 0 else 'Shortfall'}")

                if gap > 0:
                    extra_needed = gap * 12 / (((1 + monthly_r) ** months - 1) / monthly_r)
                    st.warning(f"To close the gap, increase monthly savings by **€{extra_needed:,.0f}** to **€{monthly_save + extra_needed:,.0f}/month**.")
                else:
                    st.success(f"On track for retirement at {retirement_age}. You'll have a surplus of €{abs(gap):,.0f}/month.")

    with tab2:
        fin_query = st.text_area("Ask your financial adviser", placeholder="How much should I save for retirement? What's the best way to reduce tax on commission income?...")
        if st.button("Ask HAL", key="fin_ask", type="primary"):
            if get_api_key() and fin_query:
                import anthropic
                with st.spinner("Thinking..."):
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1000,
                        system="You are a personal financial adviser for Pantelis Kourbelas, a self-employed insurance broker in Greece. Provide practical, Greece-specific financial guidance. Note when professional regulated advice is needed.",
                        messages=[{"role": "user", "content": fin_query}]
                    )
                    st.markdown(r.content[0].text)


def render_health():
    st.markdown("## 💪 Health & Gym Coach")
    st.caption("Personal trainer · Nutritionist · Health monitor")

    tab1, tab2 = st.tabs(["🏋️ Workout Plan", "💬 Health Chat"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            goal     = st.selectbox("Goal", ["Strength & muscle", "Weight loss", "Cardiovascular fitness", "Flexibility & recovery", "General fitness"])
            sessions = st.slider("Sessions per week", 2, 7, 4)
            duration = st.slider("Session duration (mins)", 30, 90, 60)
        with col2:
            equipment = st.multiselect("Equipment available", ["Full gym", "Dumbbells", "Barbell & rack", "Resistance bands", "Bodyweight only", "Cardio machines"])
            level     = st.radio("Level", ["Beginner", "Intermediate", "Advanced"])

        notes = st.text_input("Any injuries or limitations?")

        if st.button("🏗️ Generate Programme", type="primary"):
            if get_api_key():
                with st.spinner("Building your programme..."):
                    import anthropic
                    prompt = f"""Design a {sessions}-day per week workout programme.
Goal: {goal} | Level: {level} | Session: {duration} mins
Equipment: {', '.join(equipment) if equipment else 'bodyweight'}
Limitations: {notes or 'none'}

Provide a full weekly plan with exercises, sets, reps, and rest periods. Include warm-up and cool-down. Make it progressive over 4 weeks."""
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.markdown(r.content[0].text)

    with tab2:
        health_q = st.text_area("Ask your health coach or nurse", placeholder="I have lower back pain — what exercises should I avoid? What should I eat before a morning workout?...")
        if st.button("Ask HAL", key="health_ask", type="primary"):
            if get_api_key() and health_q:
                import anthropic
                with st.spinner("..."):
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=800,
                        system="You are a personal health coach and wellness adviser. Provide evidence-based guidance on fitness, nutrition, and general health. Always recommend professional medical consultation for medical conditions.",
                        messages=[{"role": "user", "content": health_q}]
                    )
                    st.markdown(r.content[0].text)


def render_apps():
    st.markdown("## 🏗️ App Builder")
    st.caption("Describe what you need · HAL writes it · Deploy to Streamlit or Netlify")

    app_type = st.selectbox("App type", [
        "Streamlit app (Python)",
        "Netlify static site (HTML/CSS/JS)",
        "Python script",
        "PDF generator (ReportLab)",
        "PowerPoint generator (python-pptx)",
        "API integration",
    ])
    description = st.text_area("Describe what the app should do", height=120,
        placeholder="e.g. A Streamlit app that takes a client name, age, and selected insurers, then generates a comparison PDF using ReportLab...")

    if st.button("⚡ Generate Code", type="primary"):
        if get_api_key() and description:
            with st.spinner("HAL is coding..."):
                import anthropic
                prompt = f"""You are an expert Python developer building tools for Ashlar Insurance, an insurance brokerage.

Build a complete, working {app_type} that does the following:
{description}

Requirements:
- Production-ready code, not pseudocode
- Include all imports
- For Streamlit: include st.set_page_config, proper layout
- For PDFs: use ReportLab with Greek font support (NotoSans fallback)
- For APIs: use Anthropic claude-sonnet-4-20250514, read key from st.secrets
- Include requirements.txt content at the end as a comment block

Output only the code."""
                client = anthropic.Anthropic(api_key=get_api_key())
                r = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=3000,
                    messages=[{"role": "user", "content": prompt}]
                )
                st.code(r.content[0].text, language="python")
                st.download_button("📥 Download code", r.content[0].text, file_name="hal_generated_app.py")


def render_pets():
    st.markdown("## 🐾 PetsHealth")
    st.caption("petshealth.gr · Pet insurance tools · Client communications")

    tab1, tab2 = st.tabs(["📢 Marketing", "💬 Pet Insurance Adviser"])

    with tab1:
        platform = st.selectbox("Platform", ["LinkedIn post", "Instagram caption", "Email newsletter", "Website copy"])
        topic    = st.text_input("Topic / angle", placeholder="e.g. Why pet insurance in Greece is broken and what we're doing about it")
        if st.button("Generate Content", type="primary"):
            if get_api_key() and topic:
                import anthropic
                with st.spinner("..."):
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=600,
                        system="You write marketing content for petshealth.gr, a pet insurance broker positioning itself as the trustworthy, human-centred alternative in Greece. Tone: confident, warm, independent, slightly critical of the industry.",
                        messages=[{"role": "user", "content": f"Write a {platform} about: {topic}"}]
                    )
                    st.markdown(r.content[0].text)

    with tab2:
        q = st.text_area("Pet insurance question", placeholder="What's the best pet insurance for a 3-year-old Labrador in Greece?...")
        if st.button("Ask HAL", key="pet_ask", type="primary"):
            if get_api_key() and q:
                import anthropic
                with st.spinner("..."):
                    client = anthropic.Anthropic(api_key=get_api_key())
                    r = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=800,
                        system="You are a pet insurance specialist for petshealth.gr, Greece. You know the Greek pet insurance market well and currently recommend Safe Pet System as the most reliable option while seeking trustworthy international partners.",
                        messages=[{"role": "user", "content": q}]
                    )
                    st.markdown(r.content[0].text)


def render_clients():
    st.markdown("## 🤝 Client Tracker")
    st.caption("Active cases · Policy status · Renewal dates · Full case history")

    CLIENTS = [
        {
            "name": "Konstantina Alexopoulou",
            "nickname": "Tzina",
            "insurer": "Bupa Global",
            "policy": "BI-6000-0113-6189",
            "claim_ref": "CL260306821932",
            "product": "International Health — Family Policy",
            "premium": "GBP 66,219/year",
            "member_since": "1996",
            "status": "🔴 Escalated",
            "summary": (
                "**Facial nerve palsy surgery — Claim EUR 12,999.97**\n\n"
                "Surgery at IASO 04–06/02/2026. Surgeon: Dr. Andreas Foustanos. "
                "Procedure: plastic reconstruction local flap (Code 6093009). "
                "Total: EUR 8,500 surgeon + EUR 4,499.97 IASO.\n\n"
                "**Timeline:** Claim filed 6 March 2026. Nine rounds of additional docs requested. "
                "Bupa introduced MCM after Roberta indicated payment was next step. "
                "By 8 May 2026: nine weeks elapsed — exceeded Bupa 8-week complaint threshold.\n\n"
                "**Key arguments:** Surgery reconstructive NOT cosmetic. Conservative treatment failed over 3 months. "
                "Clinical guidelines: Mayo Clinic Facial Reanimation, AAO-HNS Bell's Palsy CPG, Japanese CPG 2023. "
                "Premium GBP 66,219/year — member since 1996 — total premiums > GBP 1.5M.\n\n"
                "**Status:** Formal complaint filed. FSPO (Lincoln House, Dublin 2) — 7-day deadline issued."
            ),
            "next_action": "Chase Bupa for formal complaint response. No resolution within 7 days → refer to FSPO.",
            "contacts": "Dr. Foustanos · IASO hospital · Bupa claims · Roberta (case handler)",
            "documents": "Medical report 31/03/2026 · IASO discharge · Invoice APY BM 0256831 · Payment proofs · Clinical guidelines",
        },
        {
            "name": "Katia Totikidou + Alexia",
            "nickname": "Katia",
            "insurer": "Generali / Morgan Price / NOW Health",
            "policy": "—",
            "claim_ref": "—",
            "product": "Health Insurance Comparison",
            "premium": "TBC",
            "member_since": "—",
            "status": "🟡 Pending",
            "summary": (
                "**Health insurance comparison — Katia (54) + Alexia (17)**\n\n"
                "Based in Greece. German citizenship — German public health covers only within 1 month of leaving Germany. "
                "Does NOT apply as permanent Greek residents. Priority: hospitalisation + diagnostics abroad (Germany, Cyprus). "
                "Personal cancer history — aware coverage extends beyond hospitalisation (PET, diagnostics).\n\n"
                "**Options compared:**\n"
                "1. Generali Family (Greek) — EUR 750/EUR 1,500 shared annual excess. 2nd class (cannot upgrade). No outpatient, no dental, no MRI outside hospitalisation.\n"
                "2. Morgan Price Standard (international) — EUR 500 annual excess. 80% outpatient. Europe. GP/specialist up to EUR 2,500. Physio EUR 500.\n"
                "3. NOW Health (international) — EUR 400 excess. Outpatient EUR 800 (80%). Europe only.\n\n"
                "**Strategy:** Show Generali first, recommend Morgan Price Standard as balanced international solution.\n\n"
                "**Status:** Comparison PPT prepared. Awaiting client decision."
            ),
            "next_action": "Follow up with Katia. Send PPT if not done. Ask if she has reviewed the options.",
            "contacts": "Katia Totikidou",
            "documents": "PPT comparison (Generali vs Morgan Price Standard vs NOW Health Core)",
        },
        {
            "name": "Christos Iatropoulos",
            "nickname": "Christos",
            "insurer": "Morgan Price",
            "policy": "M000106069/1",
            "claim_ref": "Morgan Price claim Apr 2026",
            "product": "International Health — Morgan Price",
            "premium": "—",
            "member_since": "—",
            "status": "🟡 Pending",
            "summary": (
                "**Morgan Price claim — gastrointestinal investigation**\n\n"
                "Condition: Hematochezia (K92.1) + abdominal bloating (K57.30). "
                "Procedure: Colonoscopy + gastroscopy — outpatient 28/04/2026. "
                "Dr. Emmanouil, Gastroenterologist, Metropolitan General Hospital, Mesogeion 264 Cholargos.\n\n"
                "Invoice: 25/02/2026 — Physiotherapy 5 sessions (subacromial impingement) EUR 200.\n\n"
                "**Outstanding:** Claim documents not yet uploaded to Morgan Price portal. "
                "Still needed from doctor: Medical licence number · Governing body · Phone · Signature + stamp.\n\n"
                "**Status:** Claim form filled (29/04/2026). Pending upload to Morgan Price."
            ),
            "next_action": "Upload claim documents to Morgan Price portal. Chase Dr. Emmanouil for signature, stamp and licence number.",
            "contacts": "Dr. Emmanouil (Metropolitan General) · Morgan Price claims",
            "documents": "Morgan Price claim form (29/04/2026) · Gastroscopy/colonoscopy report · Physio invoice EUR 200",
        },
        {
            "name": "Mr. Synodinos",
            "nickname": "Synodinos",
            "insurer": "Lloyd's (binder)",
            "policy": "—",
            "claim_ref": "—",
            "product": "Secure Home Expatriates & Holiday Rental Residences",
            "premium": "TBC",
            "member_since": "—",
            "status": "🔵 In Progress",
            "summary": (
                "**Home insurance — Syros holiday rental property**\n\n"
                "Property: Thesi Rozou, Syros (Poseidonia), Cyclades 84100. Built 1998–2004. "
                "Listed on Booking.com as Bay View House / Bay View Studio. Coverage: 02/04/2026–02/04/2027.\n\n"
                "**Product:** Secure Home Expatriates & Holiday Rental — Lloyd's binder. "
                "NOT a policy yet — no coverage until insurer accepts and full premium paid.\n\n"
                "**Outstanding on form (sent with red arrows):**\n"
                "P.2: Alternative energy sources · Rental period months\n"
                "P.3: Pipe/drainage replaced? · Water pump at basement? · Uninhabited >45 days?\n"
                "P.5: Policyholder signature missing · Pages 8–9: Consent signatures missing\n\n"
                "**Status:** Form sent to client. Awaiting signed completed return."
            ),
            "next_action": "Chase Mr. Synodinos for signed completed form. Verify rental period and energy sources.",
            "contacts": "Mr. Synodinos",
            "documents": "Secure Home Expatriates proposal form (draft) · Booking.com property listings",
        },
        {
            "name": "Syros Stair Accident",
            "nickname": "Syros",
            "insurer": "Personal Accident / Travel",
            "policy": "—",
            "claim_ref": "Personal accident claim",
            "product": "Personal Accident / Cash Benefit",
            "premium": "—",
            "member_since": "—",
            "status": "🟢 Ready to Submit",
            "summary": (
                "**Personal accident — fall on stairs, Syros**\n\n"
                "Client fell on stairs of a house in Syros. Injuries: head trauma + spinal injury. "
                "Treated at General Hospital of Syros 'Vardakeios & Proios' (Tel: 22813 60300).\n\n"
                "**Medical:** Loss of consciousness → 48h neurological monitoring. CT thorax + lumbar-sacral X-rays. "
                "Full blood workup. Imaging: normal (confirms appropriate ruling out — strengthens legitimacy).\n\n"
                "**Assessment — NO RED FLAGS:** Story consistent. Mechanism matches injuries. "
                "Conservative 2-day care is standard protocol for LOC. Clear hospital documentation.\n\n"
                "**Status:** Documentation reviewed. Medical records translated Greek → English. Ready to submit."
            ),
            "next_action": "Submit claim to insurer with full hospital documentation and English translations.",
            "contacts": "General Hospital of Syros Vardakeios & Proios",
            "documents": "Hospital admission · CT results · Neurological assessment · English translations",
        },
        {
            "name": "Tania — Group Renewal",
            "nickname": "Tania",
            "insurer": "Group Health",
            "policy": "Group policy",
            "claim_ref": "—",
            "product": "Group Health Insurance Renewal",
            "premium": "EUR 9,731/year",
            "member_since": "—",
            "status": "🟢 Completed",
            "summary": (
                "**Group health renewal — premium increase communicated to HR**\n\n"
                "HR manager Tania requested year-on-year cost explanation.\n\n"
                "**Premium comparison:**\n"
                "Renewal: EUR 9,731 (Main: EUR 8,520.71 · Dependants: EUR 1,210.32)\n"
                "Previous: EUR 6,950.33 (Main: EUR 6,167.81 · Dependants: EUR 782.52)\n"
                "Increase: EUR 2,771.70 (+39.9%) — Main +EUR 2,343.90 · Dependants +EUR 427.80\n\n"
                "Context provided: Market-wide rate adjustments due to increased medical costs and claims experience 2024–2025.\n\n"
                "**Status:** Renewal processed. Premium breakdown communicated to HR."
            ),
            "next_action": "Confirm renewal paperwork signed. File updated premium schedule.",
            "contacts": "Tania (HR manager)",
            "documents": "Renewal premium schedule · Year-on-year breakdown",
        },
    ]

    # ── TICKET STORE — Google Sheets backed ──────────────────────────────
    DEFAULT_TICKETS = [
        {"id": "TKT-001", "client": "Konstantina Alexopoulou", "subject": "Bupa formal complaint — await response",          "status": "Open",    "priority": "🔴 High",   "created": "2026-05-13", "updated": "2026-05-13"},
        {"id": "TKT-002", "client": "Katia Totikidou",          "subject": "Send PPT comparison Generali vs Morgan Price",    "status": "Pending", "priority": "🟡 Medium", "created": "2026-05-13", "updated": "2026-05-13"},
        {"id": "TKT-003", "client": "Christos Iatropoulos",     "subject": "Upload claim docs to Morgan Price portal",        "status": "Pending", "priority": "🟡 Medium", "created": "2026-05-13", "updated": "2026-05-13"},
        {"id": "TKT-004", "client": "Mr. Synodinos",            "subject": "Chase signed proposal form for Syros property",   "status": "Open",    "priority": "🟡 Medium", "created": "2026-05-13", "updated": "2026-05-13"},
        {"id": "TKT-005", "client": "Syros Stair Accident",     "subject": "Submit personal accident claim to insurer",       "status": "Pending", "priority": "🟢 Low",    "created": "2026-05-13", "updated": "2026-05-13"},
    ]

    # Try loading from Google Sheets on first load
    if "tickets_loaded_from_sheet" not in st.session_state:
        tickets_ws, log_ws = get_gsheet()
        st.session_state._tickets_ws  = tickets_ws
        st.session_state._log_ws      = log_ws
        sheet_tickets = load_tickets_from_sheet(tickets_ws)
        if sheet_tickets is not None and len(sheet_tickets) > 0:
            st.session_state.tickets = sheet_tickets
            # Next ID = max existing + 1
            ids = [int(t["id"].replace("TKT-","")) for t in sheet_tickets if t["id"].startswith("TKT-")]
            st.session_state.next_ticket_id = max(ids) + 1 if ids else 6
        else:
            # First run — seed with defaults and push to sheet
            st.session_state.tickets = DEFAULT_TICKETS
            st.session_state.next_ticket_id = 6
            if tickets_ws:
                for t in DEFAULT_TICKETS:
                    save_ticket_to_sheet(tickets_ws, t)
        st.session_state.tickets_loaded_from_sheet = True

    if "next_ticket_id" not in st.session_state:
        st.session_state.next_ticket_id = 6

    # Sheet handles (may be None if not configured)
    tickets_ws = st.session_state.get("_tickets_ws")
    log_ws     = st.session_state.get("_log_ws")
    sheet_ok   = tickets_ws is not None

    # ── TABS ──────────────────────────────────────────────────────────────
    tab_clients, tab_tickets = st.tabs(["👥 Client Cases", "🎫 Task Tickets"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — CLIENT CASES
    # ══════════════════════════════════════════════════════════════════════
    with tab_clients:
        col_s, col_f = st.columns([3, 1])
        with col_s:
            search = st.text_input("🔍 Search", placeholder="Name, insurer, policy, status...")
        with col_f:
            status_filter = st.selectbox("Status", ["All", "🔴 Escalated", "🟡 Pending", "🔵 In Progress", "🟢"])

        st.divider()
        shown = 0
        for c in CLIENTS:
            if search:
                blob = f"{c['name']} {c['insurer']} {c['policy']} {c['status']} {c['product']}".lower()
                if search.lower() not in blob:
                    continue
            if status_filter != "All" and not c["status"].startswith(status_filter[:2]):
                continue

            shown += 1
            # Find related open tickets
            related = [t for t in st.session_state.tickets if c["name"].split()[0].lower() in t["client"].lower() or c["name"].lower() in t["client"].lower()]
            open_tickets = [t for t in related if t["status"] != "Resolved"]
            ticket_badge = f"  🎫 {len(open_tickets)} open" if open_tickets else ""

            label = f"{c['status'][:2]}  **{c['name']}**  ·  {c['insurer']}  ·  {c['status'][2:].strip()}{ticket_badge}"
            with st.expander(label):
                col1, col2, col3, col4 = st.columns(4)
                col1.markdown(f"**Policy**\n\n{c['policy']}")
                col2.markdown(f"**Product**\n\n{c['product']}")
                col3.markdown(f"**Premium**\n\n{c['premium']}")
                col4.markdown(f"**Member since**\n\n{c['member_since']}")

                st.divider()
                st.markdown("#### Case Summary")
                st.markdown(c["summary"])
                st.divider()

                colA, colB = st.columns(2)
                with colA:
                    st.markdown("**⚡ Next Action**")
                    st.info(c["next_action"])
                with colB:
                    st.markdown("**📎 Documents**")
                    st.caption(c["documents"])
                    st.markdown("**👤 Contacts**")
                    st.caption(c["contacts"])

                # Related tickets
                if open_tickets:
                    st.divider()
                    st.markdown("**🎫 Open Tickets**")
                    for t in open_tickets:
                        tcol1, tcol2, tcol3 = st.columns([1, 5, 2])
                        tcol1.code(t["id"])
                        tcol2.markdown(t["subject"])
                        tcol3.markdown(t["status"])

                st.divider()

                # ── ACTION BUTTONS ────────────────────────────────────────
                b1, b2, b3, b4, b5 = st.columns(5)

                with b1:
                    if st.button("✉️ Email", key=f"email_{c['name']}", use_container_width=True):
                        st.session_state.active_module = "comms"
                        st.rerun()
                with b2:
                    if st.button("💬 Ask HAL", key=f"hal_{c['name']}", use_container_width=True):
                        st.session_state.chat_history.append({
                            "role": "user",
                            "content": f"Give me a full briefing on the {c['name']} case and what I should do next."
                        })
                        st.session_state.active_module = "hal_chat"
                        st.rerun()
                with b3:
                    if st.button("🎫 New ticket", key=f"ticket_{c['name']}", use_container_width=True):
                        st.session_state[f"show_ticket_form_{c['name']}"] = True
                with b4:
                    # Status cycle: Pending → Open → Resolved → Pending
                    cur = c["status"]
                    if "Escalated" in cur or "Pending" in cur or "In Progress" in cur:
                        if st.button("✅ Mark resolved", key=f"resolve_{c['name']}", use_container_width=True):
                            for client in CLIENTS:
                                if client["name"] == c["name"]:
                                    client["status"] = "🟢 Completed"
                            st.success(f"{c['name']} marked as resolved.")
                            st.rerun()
                with b5:
                    if st.button("🗑 Delete", key=f"del_{c['name']}", use_container_width=True):
                        st.session_state[f"confirm_del_{c['name']}"] = True

                # Confirm delete
                if st.session_state.get(f"confirm_del_{c['name']}"):
                    st.warning(f"Delete **{c['name']}** from tracker?")
                    cd1, cd2 = st.columns(2)
                    with cd1:
                        if st.button("Yes, delete", key=f"yes_del_{c['name']}", type="primary"):
                            CLIENTS[:] = [x for x in CLIENTS if x["name"] != c["name"]]
                            st.session_state[f"confirm_del_{c['name']}"] = False
                            st.rerun()
                    with cd2:
                        if st.button("Cancel", key=f"no_del_{c['name']}"):
                            st.session_state[f"confirm_del_{c['name']}"] = False
                            st.rerun()

                # New ticket form
                if st.session_state.get(f"show_ticket_form_{c['name']}"):
                    with st.form(key=f"ticket_form_{c['name']}"):
                        st.markdown("**🎫 Create new ticket**")
                        subj = st.text_input("Task / subject", placeholder="e.g. Send renewal quote")
                        prio = st.selectbox("Priority", ["🔴 High", "🟡 Medium", "🟢 Low"])
                        submitted = st.form_submit_button("Create ticket")
                        if submitted and subj:
                            new_id = f"TKT-{st.session_state.next_ticket_id:03d}"
                            st.session_state.tickets.append({
                                "id": new_id,
                                "client": c["name"],
                                "subject": subj,
                                "status": "Open",
                                "priority": prio,
                            })
                            st.session_state.next_ticket_id += 1
                            st.session_state[f"show_ticket_form_{c['name']}"] = False
                            st.success(f"Ticket {new_id} created.")
                            st.rerun()

        if shown == 0:
            st.info("No clients match your search.")

        st.divider()
        # Add new client button
        with st.expander("➕ Add new client"):
            with st.form("add_client_form"):
                nc1, nc2 = st.columns(2)
                with nc1:
                    new_name    = st.text_input("Full name")
                    new_insurer = st.text_input("Insurer")
                    new_policy  = st.text_input("Policy / member ref")
                    new_product = st.text_input("Product")
                with nc2:
                    new_premium = st.text_input("Premium")
                    new_since   = st.text_input("Member since")
                    new_status  = st.selectbox("Status", ["🟡 Pending", "🔴 Escalated", "🔵 In Progress", "🟢 Completed"])
                new_summary = st.text_area("Case summary / notes")
                new_action  = st.text_input("Next action")
                if st.form_submit_button("Add client"):
                    if new_name:
                        CLIENTS.append({
                            "name": new_name, "nickname": new_name.split()[0],
                            "insurer": new_insurer, "policy": new_policy,
                            "claim_ref": "—", "product": new_product,
                            "premium": new_premium, "member_since": new_since,
                            "status": new_status, "summary": new_summary,
                            "next_action": new_action,
                            "contacts": "—", "documents": "—",
                        })
                        st.success(f"{new_name} added.")
                        st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — TICKETS
    # ══════════════════════════════════════════════════════════════════════
    with tab_tickets:
        st.markdown("### 🎫 Task Tickets")
        st.caption("All open tasks across clients — nothing falls through the cracks")

        # Summary row
        all_t   = st.session_state.tickets
        n_open  = sum(1 for t in all_t if t["status"] == "Open")
        n_pend  = sum(1 for t in all_t if t["status"] == "Pending")
        n_done  = sum(1 for t in all_t if t["status"] == "Resolved")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total tickets", len(all_t))
        mc2.metric("🔴 Open", n_open)
        mc3.metric("🟡 Pending", n_pend)
        mc4.metric("🟢 Resolved", n_done)

        st.divider()

        # Filter
        tf1, tf2 = st.columns([2, 2])
        with tf1:
            t_search = st.text_input("Search tickets", placeholder="Client name, subject, ticket ID...")
        with tf2:
            t_filter = st.selectbox("Filter", ["All", "Open", "Pending", "Resolved"], key="t_filter")

        st.divider()

        # Ticket table
        for i, t in enumerate(st.session_state.tickets):
            if t_search and t_search.lower() not in f"{t['id']} {t['client']} {t['subject']}".lower():
                continue
            if t_filter != "All" and t["status"] != t_filter:
                continue

            status_icon = {"Open": "🔴", "Pending": "🟡", "Resolved": "🟢"}.get(t["status"], "⚪")
            with st.container():
                rc1, rc2, rc3, rc4, rc5, rc6 = st.columns([1.2, 2, 4, 1.5, 1.5, 1.5])
                rc1.code(t["id"])
                rc2.markdown(f"**{t['client'].split()[0]} {t['client'].split()[-1] if len(t['client'].split())>1 else ''}**")
                rc3.markdown(t["subject"])
                rc4.markdown(f"{status_icon} {t['status']}")
                rc5.markdown(t["priority"])

                with rc6:
                    action = st.selectbox(
                        "Action",
                        ["—", "Mark open", "Mark pending", "Mark resolved", "Delete"],
                        key=f"tact_{i}",
                        label_visibility="collapsed"
                    )
                    if action == "Mark open":
                        st.session_state.tickets[i]["status"] = "Open"
                        st.rerun()
                    elif action == "Mark pending":
                        st.session_state.tickets[i]["status"] = "Pending"
                        st.rerun()
                    elif action == "Mark resolved":
                        st.session_state.tickets[i]["status"] = "Resolved"
                        st.rerun()
                    elif action == "Delete":
                        st.session_state.tickets.pop(i)
                        st.rerun()

            st.markdown("---")

        # New ticket form
        st.markdown("### ➕ Create new ticket")
        with st.form("new_ticket_global"):
            fc1, fc2, fc3 = st.columns([2, 3, 1])
            with fc1:
                t_client = st.text_input("Client name")
            with fc2:
                t_subj = st.text_input("Task / subject")
            with fc3:
                t_prio = st.selectbox("Priority", ["🔴 High", "🟡 Medium", "🟢 Low"])
            if st.form_submit_button("Create ticket", type="primary"):
                if t_client and t_subj:
                    new_id = f"TKT-{st.session_state.next_ticket_id:03d}"
                    st.session_state.tickets.append({
                        "id": new_id, "client": t_client,
                        "subject": t_subj, "status": "Open", "priority": t_prio,
                    })
                    st.session_state.next_ticket_id += 1
                    st.success(f"Ticket {new_id} created.")
                    st.rerun()



def render_kira_nurse():
    st.markdown("## 🩺 Kira · AI Nurse")
    st.caption("kiraainurse.streamlit.app · AI health assistant for clients & staff")
    col1,col2 = st.columns(2)
    with col1:
        st.markdown("""<div style="background:linear-gradient(135deg,#2D3FE7,#7B2FE0);border-radius:14px;padding:24px;color:white;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">🩺</div><div style="font-size:18px;font-weight:700">Kira AI Nurse</div><div style="font-size:13px;opacity:.85;margin:8px 0">Symptom triage · Vitals · Clinical report · PubMed evidence</div></div>""",unsafe_allow_html=True)
        st.link_button("🚀 Open Kira","https://kiraainurse.streamlit.app",use_container_width=True)
    with col2:
        st.markdown("""<div style="background:linear-gradient(135deg,#0EA5E9,#2D3FE7);border-radius:14px;padding:24px;color:white;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">📷</div><div style="font-size:18px;font-weight:700">Kira Face Scan</div><div style="font-size:13px;opacity:.85;margin:8px 0">rPPG · Heart rate · Breathing · 60-second scan</div></div>""",unsafe_allow_html=True)
        st.link_button("📷 Open Face Scan","https://kiraainurse.netlify.app",use_container_width=True)
    st.divider()
    tab_share,tab_explain,tab_about = st.tabs(["📤 Share with Client","💬 Explain to Client","ℹ️ About"])
    with tab_share:
        c_name = st.text_input("Client name", placeholder="Katia Totikidou")
        c_lang = st.radio("Language",["Greek","English"],horizontal=True)
        if st.button("✍️ Generate message", type="primary"):
            api_key = get_api_key()
            if api_key and c_name:
                import urllib.request, json as _json, urllib.error
                prompt = (f"Write a short WhatsApp message in {'Greek' if c_lang=='Greek' else 'English'} "
                          f"to {c_name}, a client of Ashlar Insurance. Introduce Kira (https://kiraainurse.streamlit.app), "
                          f"a free AI health assistant. Warm and professional. Under 4 sentences. Include the link.")
                body = _json.dumps({"model":"claude-sonnet-4-6","max_tokens":300,"messages":[{"role":"user","content":prompt}]}).encode()
                req = urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                try:
                    with urllib.request.urlopen(req,timeout=20) as r:
                        msg = _json.loads(r.read())["content"][0]["text"]
                    st.text_area("Message:",value=msg,height=120)
                    import urllib.parse
                    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" style="background:#25D366;color:white;padding:8px 18px;border-radius:8px;text-decoration:none;font-weight:600">WhatsApp →</a>',unsafe_allow_html=True)
                except Exception as e: st.error(f"Error: {e}")
    with tab_explain:
        st.markdown("""**Kira** is a bilingual AI health assistant:\n- Triage · Vitals · Face Scan (rPPG) · Clinical Report · PubMed evidence · RxNorm drug check\n- Use cases: expat clients far from GP, pre-consultation prep, insurance claims documentation""")
    with tab_about:
        st.markdown("""| Component | Technology |\n|---|---|\n| AI | Claude Sonnet + GPT-4o |\n| Face Scan | rPPG CHROM algorithm |\n| Medical DB | PubMed/NCBI |\n| Drug Check | RxNorm |\n| Deploy | Streamlit Cloud + Netlify |""")


def _build_analyzer_prompt(client_data, existing_policies, lang="el"):
    def _pol_line(p):
        parts=[f"- {p.get('type','').title()}: {p.get('provider','')}"]
        if p.get("product"): parts.append(p["product"])
        if p.get("policy_no"): parts.append(f"No.{p['policy_no']}")
        if p.get("premium"): parts.append(f"Premium {p.get('currency','EUR')} {p['premium']}")
        if p.get("renewal_date"): parts.append(f"Expires {p['renewal_date']}")
        if p.get("coverage"): parts.append(f"| Coverage: {p['coverage'][:200]}")
        return " ".join(parts)
    existing_str = "\n".join(_pol_line(p) for p in existing_policies) if existing_policies else "No policies on file"
    carriers_info = """Available carriers: Motor: 3P/Hellas Direct/Groupama/Generali/Ethniki/AXA. Greek Health: Groupama/Generali/Ethniki/Interamerican/Eurolife. International Health: Morgan Price/Bupa Global/NOW Health. Life: Generali/Ethniki/Interamerican/Eurolife/NN/Allianz. Liability: Groupama/Generali/Ethniki/AXA. Pet: Safe Pet System. Key facts: Greek domestic health = no free outpatient/dental/psychiatric/imaging outside hospitalisation. Professional Liability LEGALLY REQUIRED for architects/engineers/doctors/lawyers in Greece. Expats need international health NOT Greek domestic."""
    p=client_data
    if lang=="el":
        return f"""Είσαι σύμβουλος ασφαλίσεων Ashlar Insurance. Ανάλυσε τις ασφαλιστικές ανάγκες:
ΠΕΛΑΤΗΣ: {p.get("name")}, {p.get("age")}y, {p.get("profession")}, {p.get("family")}, εισόδημα {p.get("income")}
Ακίνητο:{"Ναι" if p.get("has_property") else "Όχι"} Όχημα:{"Ναι" if p.get("has_vehicle") else "Όχι"} Κατοικίδιο:{"Ναι" if p.get("has_pets") else "Όχι"} Παιδιά:{"Ναι" if p.get("has_children") else "Όχι"} Expat:{"Ναι" if p.get("is_expat") else "Όχι"}
Σημειώσεις: {p.get("notes","")}
ΥΠΑΡΧΟΥΣΕΣ ΑΣΦΑΛΙΣΕΙΣ:
{existing_str}
{carriers_info}
Δώσε: ## 🔍 ΑΝΑΛΥΣΗ ΠΡΟΦΙΛ | ## ✅ ΚΑΛΥΨΕΙΣ ΠΟΥ ΕΧΕΙ | ## ⚠️ ΚΕΝΑ ΚΑΛΥΨΕΩΝ (με Επείγον🔴/Προτεινόμενο🟡/Προαιρετικό🟢, ασφαλιστές, εκτιμώμενο ασφάλιστρο) | ## 📋 ΠΛΑΝΟ ΔΡΑΣΗΣ | ## 💬 SCRIPT ΕΠΙΚΟΙΝΩΝΙΑΣ"""
    else:
        return f"""You are an insurance adviser at Ashlar Insurance Greece. Analyse needs for:
CLIENT: {p.get("name")}, {p.get("age")}y, {p.get("profession")}, {p.get("family")}, income {p.get("income")}
Property:{"Yes" if p.get("has_property") else "No"} Vehicle:{"Yes" if p.get("has_vehicle") else "No"} Pets:{"Yes" if p.get("has_pets") else "No"} Children:{"Yes" if p.get("has_children") else "No"} Expat:{"Yes" if p.get("is_expat") else "No"}
Notes: {p.get("notes","")}
EXISTING POLICIES:
{existing_str}
{carriers_info}
Provide: ## 🔍 PROFILE ANALYSIS | ## ✅ EXISTING COVERAGE | ## ⚠️ COVERAGE GAPS (Urgent🔴/Recommended🟡/Optional🟢, carriers, estimated premium) | ## 📋 ACTION PLAN | ## 💬 CLIENT SCRIPT"""


def chi_api(endpoint, params=None):
    import urllib.request as _ur, json as _j, urllib.parse as _up
    portal_url=st.secrets.get("CHI_PORTAL_URL","https://chi-insurance-portal-production.up.railway.app")
    api_key=st.secrets.get("CHI_API_KEY","")
    if not api_key: return None
    url=f"{portal_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
    if params: url+="?"+_up.urlencode(params)
    req=_ur.Request(url,headers={"X-API-Key":api_key,"Accept":"application/json"})
    try:
        with _ur.urlopen(req,timeout=10) as r: return _j.loads(r.read())
    except Exception as e: return {"error":str(e)}


def render_chi_analyzer():
    import urllib.request as _ur, json as _j
    st.markdown("## 🧠 AI Insurance Analyzer")
    st.caption("Αναλύει το προφίλ του πελάτη · Εντοπίζει κενά κάλυψης · Προτείνει ασφαλιστικά προγράμματα")
    api_key=get_api_key()
    st.markdown("### 👤 Προφίλ Πελάτη")
    col1,col2,col3=st.columns(3)
    with col1:
        a_name=st.text_input("Όνομα πελάτη *",key="an_name",placeholder="Μαρία Παπαδοπούλου")
        a_age=st.number_input("Ηλικία",min_value=18,max_value=90,value=35,key="an_age")
        a_prof=st.text_input("Επάγγελμα *",key="an_prof",placeholder="Αρχιτέκτονας, Ιατρός...")
    with col2:
        a_family=st.selectbox("Οικογενειακή κατάσταση",["Άγαμος/η","Έγγαμος/η χωρίς παιδιά","Έγγαμος/η με παιδιά","Διαζευγμένος/η"],key="an_family")
        a_income=st.selectbox("Εισόδημα",["< €20k","€20k–€40k","€40k–€80k","€80k–€150k","> €150k"],key="an_income")
        a_notes=st.text_area("Επιπλέον στοιχεία",height=80,key="an_notes")
    with col3:
        a_prop=st.checkbox("🏠 Ιδιοκτήτης ακινήτου",key="an_prop")
        a_vehicle=st.checkbox("🚗 Έχει όχημα",key="an_veh",value=True)
        a_pets=st.checkbox("🐾 Έχει κατοικίδιο",key="an_pet")
        a_kids=st.checkbox("👶 Έχει παιδιά",key="an_kids")
        a_expat=st.checkbox("✈️ Expat / Ταξιδεύει συχνά",key="an_expat")
        a_lang=st.radio("Γλώσσα",["el","en"],horizontal=True,format_func=lambda x:"🇬🇷 Ελληνικά" if x=="el" else "🇬🇧 English",key="an_lang")
    st.markdown("### 📋 Υπάρχουσες Ασφαλίσεις")
    st.caption("Ανεβάστε PDF · ή συνδεθείτε με CHI Portal · ή προσθέστε χειροκίνητα")
    if "an_policies" not in st.session_state: st.session_state.an_policies=[]
    with st.expander("📄 Upload Policy PDFs — AI extracts details automatically",expanded=True):
        uploaded_pdfs=st.file_uploader("Upload policy PDFs",type=["pdf"],accept_multiple_files=True,key="pdf_policies")
        if uploaded_pdfs:
            if st.button("🤖 Extract Policies with AI",type="primary",key="extract_pdfs",use_container_width=True):
                if not api_key: st.error("Add Claude_API_Key to secrets.")
                else:
                    extracted=[]
                    for pdf_file in uploaded_pdfs:
                        with st.spinner(f"Reading {pdf_file.name}..."):
                            try:
                                from PyPDF2 import PdfReader
                                reader = PdfReader(pdf_file)
                                pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)[:8000]
                            except Exception as e:
                                st.warning(f"Could not read {pdf_file.name}: {e}")
                                continue
                            if not pdf_text.strip(): st.warning(f"{pdf_file.name}: no text found"); continue
                            extract_prompt=f'''Extract insurance policy details. Return ONLY JSON:
{{"policy_type":"motor/health/life/home/travel/pet/liability/other","insurer":"","policy_number":"","product":"","premium":"","currency":"EUR","expiry_date":"YYYY-MM-DD","coverage_summary":"","key_exclusions":"","deductible":""}}
POLICY:
{pdf_text}'''
                            body=_j.dumps({"model":"claude-sonnet-4-6","max_tokens":800,"messages":[{"role":"user","content":extract_prompt}]}).encode()
                            req=_ur.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                            try:
                                with _ur.urlopen(req,timeout=30) as r: result=_j.loads(r.read())["content"][0]["text"].strip()
                                if result.startswith("```"): result=result.split("```")[1]; result=result[4:] if result.startswith("json") else result
                                pd=_j.loads(result.strip())
                                extracted.append({"type":pd.get("policy_type","other"),"provider":pd.get("insurer",""),
                                    "policy_no":pd.get("policy_number",""),"product":pd.get("product",""),
                                    "premium":pd.get("premium",""),"currency":pd.get("currency","EUR"),
                                    "renewal_date":pd.get("expiry_date",""),"coverage":pd.get("coverage_summary",""),
                                    "source_file":pdf_file.name,"color":_POLICY_TYPES.get(pd.get("policy_type","other"),_POLICY_TYPES["other"])["color"]})
                                st.success(f"✅ {pdf_file.name} → {pd.get('insurer','')} {pd.get('product','')}")
                            except Exception as e: st.warning(f"Could not parse {pdf_file.name}: {e}")
                    if extracted:
                        existing_nos={p.get("policy_no","") for p in st.session_state.an_policies}
                        new_ones=[p for p in extracted if p.get("policy_no","") not in existing_nos]
                        st.session_state.an_policies.extend(new_ones)
                        st.success(f"✅ Added {len(new_ones)} policies"); st.rerun()
    chi_api_key=st.secrets.get("CHI_API_KEY","")
    if chi_api_key and a_name and len(a_name)>=3:
        if st.button("🔗 Pull from CHI Portal",key="pull_chi"):
            with st.spinner("Fetching..."):
                clients_data=chi_api("clients",{"search":a_name})
                if clients_data and isinstance(clients_data,list) and len(clients_data)>0:
                    match=next((c for c in clients_data if a_name.lower() in c.get("name","").lower()),clients_data[0])
                    cd=chi_api(f"clients/{match['id']}")
                    if cd and "policies" in cd:
                        st.session_state.an_policies=[{"type":p.get("type","other"),"provider":p.get("insurer",""),"policy_no":p.get("policy_number",""),"premium":p.get("premium",""),"renewal_date":p.get("expiry_date",""),"color":_POLICY_TYPES.get(p.get("type","other"),_POLICY_TYPES["other"])["color"]} for p in cd["policies"]]
                        st.success(f"✅ Pulled {len(st.session_state.an_policies)} policies"); st.rerun()
                    else: st.warning("No policies found.")
                else: st.warning(f"No client matching '{a_name}'.")
    with st.expander("➕ Προσθήκη χειροκίνητα"):
        ep1,ep2,ep3=st.columns(3)
        with ep1: ep_type=st.selectbox("Τύπος",list(_POLICY_TYPES.keys()),format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label_el']}",key="ep_type")
        with ep2: ep_prov=st.selectbox("Ασφαλιστής",_PROVIDERS,key="ep_prov")
        with ep3: ep_no=st.text_input("Αρ.",key="ep_no")
        if st.button("Προσθήκη ✓",key="add_an_pol"):
            st.session_state.an_policies.append({"type":ep_type,"provider":ep_prov,"policy_no":ep_no}); st.rerun()
    for i,p in enumerate(st.session_state.an_policies):
        cfg=_POLICY_TYPES.get(p.get("type","other"),_POLICY_TYPES["other"])
        ac1,ac2=st.columns([5,1])
        src=f" · 📄 {p['source_file']}" if p.get("source_file") else ""
        prem=f" · {p.get('currency','EUR')} {p['premium']}" if p.get("premium") else ""
        pno=f" `{p['policy_no']}`" if p.get("policy_no") else ""
        ac1.markdown(f"{cfg['icon']} **{p.get('provider','')}** {p.get('product','')}{pno}{prem}{src}")
        if p.get("coverage"): ac1.caption(p["coverage"][:120])
        if ac2.button("✕",key=f"del_an_{i}"): st.session_state.an_policies.pop(i); st.rerun()
    st.divider()
    if st.button("🧠 Ανάλυση Ασφαλιστικών Αναγκών",type="primary",use_container_width=True,key="run_analysis"):
        if not a_name or not a_prof: st.warning("Συμπληρώστε όνομα και επάγγελμα.")
        elif not api_key: st.error("Προσθέστε Claude_API_Key.")
        else:
            client_data={"name":a_name,"age":a_age,"profession":a_prof,"family":a_family,"income":a_income,
                "notes":a_notes,"has_property":a_prop,"has_vehicle":a_vehicle,"has_pets":a_pets,
                "has_children":a_kids,"is_expat":a_expat}
            prompt=_build_analyzer_prompt(client_data,st.session_state.an_policies,a_lang)
            with st.spinner("Analysing..."):
                body=_j.dumps({"model":"claude-sonnet-4-6","max_tokens":3000,
                    "system":"Είσαι έμπειρος ασφαλιστικός σύμβουλος στην Ελλάδα.",
                    "messages":[{"role":"user","content":prompt}]}).encode()
                req=_ur.Request("https://api.anthropic.com/v1/messages",data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                try:
                    with _ur.urlopen(req,timeout=60) as r:
                        result=_j.loads(r.read())["content"][0]["text"]
                    st.session_state["an_result"]=result; st.session_state["an_client"]=a_name
                except Exception as e: st.error(f"Error: {e}")
    if st.session_state.get("an_result"):
        result=st.session_state["an_result"]; cname=st.session_state["an_client"]
        st.markdown("---"); st.markdown(f"### 📊 {cname}")
        st.markdown(f'<div style="background:white;border-radius:14px;padding:24px;border:1px solid #E8E0D5">',unsafe_allow_html=True)
        st.markdown(result); st.markdown('</div>',unsafe_allow_html=True)
        ab1,ab2,ab3=st.columns(3)
        with ab1:
            dl_text = f"ASHLAR\n{cname}\n\n{result}"
            st.download_button("Download",data=dl_text,file_name=f"analysis_{cname.replace(' ','_')}.txt",mime="text/plain",use_container_width=True)
        with ab3:
            if st.button("🔄 Νέα",use_container_width=True,key="reset_an"):
                for k in ["an_result","an_client","an_policies"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()


def render_chi_portal():
    portal_url=st.secrets.get("CHI_PORTAL_URL","https://chi-insurance-portal-production.up.railway.app")
    gh_token=st.secrets.get("GITHUB_TOKEN",""); repo="chiinsurancebrokers/chi-insurance-portal"
    st.markdown("## 🌐 CHI Insurance Portal"); st.caption(portal_url)
    qa1,qa2,qa3=st.columns(3)
    with qa1: st.link_button("🌐 Open Portal",portal_url,use_container_width=True,type="primary")
    with qa2: st.link_button("🔐 Admin Login",f"{portal_url}/login",use_container_width=True)
    with qa3: st.link_button("📂 GitHub",f"https://github.com/{repo}",use_container_width=True)
    st.divider()
    tab_op,tab_gen,tab_manage=st.tabs(["🚀 Operate","🏗️ Generate Portal","📋 Manage"])
    with tab_op:
        st.markdown(f'''<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);border-radius:16px;padding:28px;text-align:center;margin-bottom:20px"><div style="font-size:40px">🛡️</div><div style="font-size:22px;font-weight:800;color:#C9A96E;margin-bottom:6px">CHI Admin Panel</div><div style="font-size:13px;color:#A89880;margin-bottom:20px">138 Clients · 222 Policies · 30 Expiring</div><a href="{portal_url}" target="_blank" style="background:#C9A96E;color:#1C1410;padding:12px 32px;border-radius:8px;font-weight:800;font-size:15px;text-decoration:none">Open →</a></div>''',unsafe_allow_html=True)
        q1,q2,q3,q4=st.columns(4)
        with q1: st.link_button("👥 Clients",f"{portal_url}/clients",use_container_width=True,type="primary")
        with q2: st.link_button("📄 Policies",f"{portal_url}/policies",use_container_width=True,type="primary")
        with q3: st.link_button("💳 Payments",f"{portal_url}/payments",use_container_width=True,type="primary")
        with q4: st.link_button("📧 Renewals",f"{portal_url}/renewals",use_container_width=True)
        if st.secrets.get("CHI_API_KEY",""):
            st.divider(); st.markdown("#### ⏰ Upcoming Renewals")
            if st.button("🔄 Refresh",key="refresh_renewals"):
                st.session_state["_renewals_data"]=chi_api("renewals"); st.rerun()
            rd=st.session_state.get("_renewals_data")
            if rd and "error" not in (rd or {}):
                for r in rd.get("urgent",[])[:5]: st.markdown(f"🔴 **{r.get('client_name')}** — {r.get('insurer')} · **{r.get('days_left')} days**")
                for r in rd.get("soon",[])[:5]: st.markdown(f"🟡 **{r.get('client_name')}** — {r.get('insurer')} · {r.get('days_left')} days")
        st.divider()
        with st.expander("🔐 Admin credentials"):
            st.markdown(f"URL: [{portal_url}]({portal_url})  \nUsername: `admin`  \nEmail: `xiatropoulos@gmail.com`")
    with tab_gen:
        st.caption("Multi-policy client portal · All insurance types · Push to GitHub")
        if "p2_policies" not in st.session_state: st.session_state.p2_policies=[]; st.session_state.p2_payments=[]; st.session_state.p2_documents=[]; st.session_state.p2_claims=[]
        ci1,ci2,ci3=st.columns(3)
        with ci1: p2_name=st.text_input("Full name *",key="p2_name")
        with ci2: p2_email=st.text_input("Email",key="p2_email")
        with ci3: p2_lang=st.radio("Language",["el","en"],horizontal=True,key="p2_lang")
        st.markdown("#### 📋 Policies")
        with st.expander("➕ Add policy",expanded=len(st.session_state.p2_policies)==0):
            np1,np2,np3=st.columns(3)
            with np1:
                npt=st.selectbox("Type",list(_POLICY_TYPES.keys()),format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",key="np_type")
                npp=st.selectbox("Provider",_PROVIDERS,key="np_prov")
            with np2: npn=st.text_input("Policy no",key="np_no"); nppr=st.text_input("Product",key="np_prod")
            with np3: npm=st.text_input("Premium",key="np_prem"); npc=st.selectbox("Currency",["EUR","GBP","USD"],key="np_cur"); npd=st.date_input("Renewal",key="np_date")
            npo=st.text_input("Notes",key="np_notes")
            if st.button("Add Policy ✓",type="primary",key="add_pol"):
                st.session_state.p2_policies.append({"type":npt,"provider":npp,"policy_no":npn,"product":nppr,"premium":npm,"currency":npc,"renewal_date":str(npd),"status":"Active","notes":npo,"color":_POLICY_TYPES[npt]["color"]}); st.rerun()
        for i,p in enumerate(st.session_state.p2_policies):
            cfg=_POLICY_TYPES.get(p["type"],_POLICY_TYPES["other"]); pc1,pc2=st.columns([5,1])
            pc1.markdown(f"{cfg['icon']} **{p['provider']}** — {p['product']} · {p['currency']} {p['premium']}")
            if pc2.button("✕",key=f"del_pol_{i}"): st.session_state.p2_policies.pop(i); st.rerun()
        if st.button("⚡ Generate Client Portal",type="primary",use_container_width=True,key="gen_p2"):
            if not p2_name: st.warning("Client name required.")
            elif not st.session_state.p2_policies: st.warning("Add at least one policy.")
            else:
                from chi_portal_phase2 import generate_client_portal
                client_data={"name":p2_name,"email":p2_email,"lang":p2_lang}
                html=generate_client_portal(client_data,st.session_state.p2_policies,st.session_state.p2_payments,st.session_state.p2_documents,st.session_state.p2_claims)
                st.session_state["p2_html"]=html; st.session_state["p2_client"]=p2_name
                st.session_state["p2_folder"]=p2_name.lower().replace(" ","-").replace("'","")
                st.success(f"✅ Portal generated for {p2_name}")
        if st.session_state.get("p2_html"):
            html=st.session_state["p2_html"]; cname=st.session_state["p2_client"]; folder=st.session_state["p2_folder"]
            st.download_button("📥 Download index.html",data=html.encode(),file_name="index.html",mime="text/html",use_container_width=True)
            if gh_token:
                if st.button("🚀 Push to GitHub",use_container_width=True,key="push_p2"):
                    import base64 as _b64,urllib.request as _ur,json as _j,urllib.error as _ue
                    path=f"clients/{folder}/index.html"; api=f"https://api.github.com/repos/{repo}/contents/{path}"
                    hdrs={"Authorization":f"token {gh_token}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json","User-Agent":"HAL"}
                    sha=None
                    try:
                        req=_ur.Request(api,headers=hdrs)
                        with _ur.urlopen(req,timeout=8) as r: sha=_j.loads(r.read()).get("sha")
                    except _ue.HTTPError: pass
                    payload={"message":f"{'Update' if sha else 'Add'} portal: {cname}","content":_b64.b64encode(html.encode()).decode(),"branch":"main"}
                    if sha: payload["sha"]=sha
                    req=_ur.Request(api,data=_j.dumps(payload).encode(),headers=hdrs,method="PUT")
                    try:
                        with _ur.urlopen(req,timeout=15) as r: _j.loads(r.read())
                        st.success(f"✅ Pushed → clients/{folder}/index.html")
                    except Exception as e: st.error(f"Push failed: {e}")
    with tab_manage:
        live_stats=chi_api("stats") if st.secrets.get("CHI_API_KEY","") else None
        mc1,mc2=st.columns(2)
        with mc1:
            cc=live_stats.get("total_clients","138") if live_stats and "error" not in live_stats else "138"
            pc=live_stats.get("total_policies","222") if live_stats and "error" not in live_stats else "222"
            ec=live_stats.get("expiring_30_days","30") if live_stats and "error" not in live_stats else "30"
            st.markdown(f'''<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);border-radius:12px;padding:18px 20px;color:#E8DDD0;margin-bottom:12px"><div style="font-size:11px;color:#7A6A5A;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Railway · Live</div><div style="font-size:15px;font-weight:700;color:#C9A96E">chi-insurance-portal</div><div style="font-size:12px;color:#A89880;margin-top:6px">👥 {cc} Clients · 📋 {pc} Policies · ⏰ {ec} Expiring</div><a href="{portal_url}" target="_blank" style="display:inline-block;margin-top:10px;background:#C9A96E;color:#1C1410;padding:5px 14px;border-radius:6px;text-decoration:none;font-weight:700;font-size:12px">Open →</a></div>''',unsafe_allow_html=True)
        with mc2:
            st.markdown('''<div style="background:white;border:1px solid #E8E0D5;border-radius:12px;padding:18px 20px"><div style="font-size:11px;color:#7A6A5A;text-transform:uppercase;margin-bottom:6px">Admin</div><div style="font-size:13px;line-height:2">Username: <code>admin</code><br>Email: <code>xiatropoulos@gmail.com</code></div></div>''',unsafe_allow_html=True)
        st.markdown("### Client Portals")
        portals=[{"client":"Pantelis Kourbelas","url":"panteliskourbelas-chiinsurancebrokers.netlify.app","status":"🟢 Live"}]
        for p in portals:
            pc1,pc2,pc3,pc4=st.columns([2,3,1,1]); pc1.markdown(f"**{p['client']}**")
            if p["url"]: pc2.markdown(f"[{p['url']}](https://{p['url']})"); pc4.link_button("Open",f"https://{p['url']}",use_container_width=True)
            pc3.markdown(p["status"])


def render_kira_pet_hal():
    st.markdown("## 🐾 Kira Pet — AI Veterinary Nurse")
    st.caption("petshealth.gr · AI health assistant for pet insurance clients")
    col1,col2=st.columns(2)
    with col1:
        st.markdown("""<div style="background:linear-gradient(135deg,#059669,#0EA5E9);border-radius:14px;padding:24px;color:white;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">🐾</div><div style="font-size:18px;font-weight:700">Kira Pet App</div><div style="font-size:13px;opacity:.85;margin:8px 0">AI triage · Photo scan · Vet report</div></div>""",unsafe_allow_html=True)
        st.link_button("🚀 Open Kira Pet","https://kiraaipet.streamlit.app",use_container_width=True)
    with col2:
        st.markdown("""<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);border-radius:14px;padding:24px;color:#E8DDD0;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">🌐</div><div style="font-size:18px;font-weight:700;color:#C9A96E">petshealth.gr</div><div style="font-size:13px;opacity:.85;margin:8px 0">Pet insurance brand · Safe Pet System</div></div>""",unsafe_allow_html=True)
        st.link_button("🌐 Open petshealth.gr","https://petshealth.gr",use_container_width=True)
    st.divider()
    tab_content,tab_social=st.tabs(["📢 Pet Insurance Content","📱 Social Media"])
    with tab_content:
        content_type=st.selectbox("Content type",["Email to potential client","LinkedIn post","FAQ: What does pet insurance cover?","Why insure your pet in Greece?","Custom content"])
        custom="" if content_type!="Custom content" else st.text_area("Describe",height=80)
        lang=st.radio("Language",["Greek","English","Bilingual"],horizontal=True)
        if st.button("✍️ Generate",type="primary"):
            api_key=get_api_key()
            if api_key:
                import urllib.request,json as _json
                prompt=f"Write pet insurance content for petshealth.gr (Greek brand, Ashlar Insurance, carrier: Safe Pet System). Content: {content_type if not custom else custom}. Language: {lang}. Professional, warm, genuine."
                body=_json.dumps({"model":"claude-sonnet-4-6","max_tokens":1500,"messages":[{"role":"user","content":prompt}]}).encode()
                req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("Writing..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r: result=_json.loads(r.read())["content"][0]["text"]
                        st.markdown(result)
                    except Exception as e: st.error(f"Error: {e}")
    with tab_social:
        platform=st.selectbox("Platform",["LinkedIn","Instagram","Facebook"])
        angle=st.text_input("Topic",placeholder="e.g. Emergency vet bills in Greece")
        if st.button("📱 Generate",type="primary"):
            api_key=get_api_key()
            if api_key and angle:
                import urllib.request,json as _json
                body=_json.dumps({"model":"claude-sonnet-4-6","max_tokens":600,"messages":[{"role":"user","content":f"Write a {platform} post for petshealth.gr about: {angle}. Greek language, English hashtags."}]}).encode()
                req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":get_api_key(),"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r: st.markdown(_json.loads(r.read())["content"][0]["text"])
                    except Exception as e: st.error(f"Error: {e}")


def render_placeholder(title, icon):
    st.markdown(f"## {icon} {title}")
    st.info(f"This module is loading. Use the HAL Assistant tab to access {title} functionality right now.")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
module = st.session_state.active_module
mode   = st.session_state.mode

if mode == "private" and not st.session_state.private_unlocked:
    render_pin_screen()

elif mode == "business":
    if module == "home":        render_business_home()
    elif module == "hal_chat":  render_hal_chat()
    elif module == "quotes":    render_quotes()
    elif module == "documents": render_documents()
    elif module == "comms":     render_comms()
    elif module == "commissions": render_commissions()
    elif module == "market":    render_market()
    elif module == "clients":   render_clients()
    elif module == "apps":      render_apps()
    elif module == "pets":      render_pets()
    elif module == "kira_nurse":  render_kira_nurse()
    elif module == "chi_analyzer": render_chi_analyzer()
    elif module == "chi_portal":  render_chi_portal()
    elif module == "kira_pet":    render_kira_pet_hal()
    else: render_business_home()

elif mode == "private" and st.session_state.private_unlocked:
    if module == "home":        render_private_home()
    elif module == "hal_chat":  render_hal_chat()
    elif module == "lodge":     render_lodge()
    elif module == "minutes":   render_placeholder("Minutes & Documents", "📋")
    elif module == "attendance": render_placeholder("Attendance Tracker", "👥")
    elif module == "events":    render_placeholder("Events & Gala", "📅")
    elif module == "finance":   render_finance()
    elif module == "health":    render_health()
    elif module == "settings_private": render_placeholder("Private Settings", "🔑")
    else: render_private_home()
