"""
HAL — Heuristically Programmed Algorithmic Layer
Christos Iatropoulos | Ashlar Insurance
Main Dashboard Entry Point
"""

import streamlit as st
import hashlib
import os
import json
import re
import base64
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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

# Google Sheets (tickets + conversation persistence)
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# ── MEMORY CONFIG ─────────────────────────────────────────────────────────────
MEMORY_WINDOW_DAYS    = 7
MEMORY_SAVE_MODES     = ["business"]
MEMORY_MAX_INJECT     = 30

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
[data-testid="stAppViewContainer"] { background: #F8F6F2; }
[data-testid="stSidebar"] { background: #1C1410; }
[data-testid="stSidebar"] * { color: #E8DDD0 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #A89880 !important; font-size: 12px !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #A89880 !important; font-size: 12px !important; }
.hal-logo { text-align: center; padding: 24px 0 16px; border-bottom: 1px solid #3A2E24; margin-bottom: 16px; }
.hal-logo .hal-title { font-size: 32px; font-weight: 800; color: #C9A96E !important; letter-spacing: 4px; }
.hal-logo .hal-sub { font-size: 11px; color: #7A6A5A !important; letter-spacing: 2px; text-transform: uppercase; margin-top: 2px; }
.mode-btn { display: block; width: 100%; padding: 10px 16px; margin: 4px 0; border-radius: 8px; border: none; text-align: left; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; }
.mode-btn-business { background: #C9A96E22; color: #C9A96E !important; }
.mode-btn-business:hover { background: #C9A96E44; }
.mode-btn-private { background: #4A3728 22; color: #A89880 !important; }
.hal-card { background: white; border-radius: 12px; padding: 20px 24px; border: 1px solid #E8E0D5; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.hal-card-dark { background: #1C1410; border-radius: 12px; padding: 20px 24px; border: 1px solid #3A2E24; margin-bottom: 16px; }
.module-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 8px; }
.module-tile { background: white; border: 1px solid #E8E0D5; border-radius: 10px; padding: 18px; cursor: pointer; transition: all 0.15s; text-decoration: none; }
.module-tile:hover { border-color: #C9A96E; box-shadow: 0 2px 8px rgba(201,169,110,0.15); }
.module-tile .tile-icon { font-size: 28px; margin-bottom: 8px; }
.module-tile .tile-name { font-size: 14px; font-weight: 600; color: #2C1810; }
.module-tile .tile-desc { font-size: 12px; color: #7A6A5A; margin-top: 4px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-live { background: #EAF3DE; color: #27500A; }
.badge-dev  { background: #FAEEDA; color: #633806; }
.badge-private { background: #FCEBEB; color: #A32D2D; }
.section-header { font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #7A6A5A; border-bottom: 1px solid #E8E0D5; padding-bottom: 8px; margin-bottom: 16px; }
.hal-chat-input { border-radius: 10px !important; }
.hal-response { background: white; border-left: 3px solid #C9A96E; padding: 16px 20px; border-radius: 0 10px 10px 0; margin-top: 8px; }
.pin-container { max-width: 320px; margin: 60px auto; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state.mode = "business"
if "private_unlocked" not in st.session_state:
    st.session_state.private_unlocked = False
if "active_module" not in st.session_state:
    st.session_state.active_module = "home"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = datetime.now().strftime("%Y%m%d-%H%M") + "-" + uuid.uuid4().hex[:6]
if "memory_injected" not in st.session_state:
    st.session_state.memory_injected = False
if "hal_pending_files" not in st.session_state:
    # Files staged in the uploader, not yet attached to a sent message.
    # Each entry: (filename, bytes, mime_type)
    st.session_state.hal_pending_files = []
if "hal_uploader_nonce" not in st.session_state:
    # Bumped after a send so the file_uploader widget remounts empty
    # (Streamlit has no public API to clear an uploader without a key change).
    st.session_state.hal_uploader_nonce = 0

# ── HELPERS ───────────────────────────────────────────────────────────────────
def check_pin(pin_input):
    stored = st.secrets.get("HAL_PIN", "")
    if not stored:
        return False
    return hashlib.sha256(pin_input.encode()).hexdigest() == stored

def get_gsheet():
    if not GSHEETS_AVAILABLE:
        return None, None, None
    try:
        creds_dict = dict(st.secrets.get("gcp_service_account", {}))
        if not creds_dict:
            return None, None, None
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
            return None, None, None
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
        try:
            conv_ws = wb.worksheet("Conversations")
        except Exception:
            conv_ws = wb.add_worksheet("Conversations", rows=10000, cols=6)
            conv_ws.append_row(["Timestamp","SessionID","Mode","Role","Content","Tags"])
        return tickets_ws, log_ws, conv_ws
    except Exception:
        return None, None, None


def save_message_to_sheet(conv_ws, mode, session_id, role, content, tags=""):
    if conv_ws is None:
        return False
    if mode not in MEMORY_SAVE_MODES:
        return False
    try:
        safe_content = (content or "")[:45000]
        conv_ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id, mode, role, safe_content, tags,
        ])
        return True
    except Exception:
        return False


def load_recent_conversations(conv_ws, days=MEMORY_WINDOW_DAYS, mode_filter="business"):
    if conv_ws is None:
        return []
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        rows = conv_ws.get_all_records()
        result = []
        for r in rows:
            ts_str = r.get("Timestamp", "")
            if not ts_str:
                continue
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if ts < cutoff:
                continue
            if mode_filter and r.get("Mode") != mode_filter:
                continue
            result.append({
                "timestamp": ts_str, "session_id": r.get("SessionID",""),
                "mode": r.get("Mode",""), "role": r.get("Role","user"),
                "content": r.get("Content",""), "tags": r.get("Tags",""),
            })
        return result
    except Exception:
        return []


def search_conversations(conv_ws, query, limit=20):
    if conv_ws is None or not query:
        return []
    try:
        rows = conv_ws.get_all_records()
        q = query.lower()
        matches = []
        for r in rows:
            content = (r.get("Content","") or "").lower()
            tags    = (r.get("Tags","") or "").lower()
            if q in content or q in tags:
                matches.append({
                    "timestamp": r.get("Timestamp",""), "session_id": r.get("SessionID",""),
                    "mode": r.get("Mode",""), "role": r.get("Role","user"),
                    "content": r.get("Content",""), "tags": r.get("Tags",""),
                })
        matches.sort(key=lambda x: x["timestamp"], reverse=True)
        return matches[:limit]
    except Exception:
        return []


def summarise_memory_for_context(recent_msgs, max_msgs=MEMORY_MAX_INJECT):
    if not recent_msgs:
        return ""
    # Drop stale HAL replies that paste a fenced ```python/```pptx code block instead of
    # running it — these predate code execution being wired up and, if replayed into context,
    # act as a strong few-shot example pulling new replies back toward the old "paste, don't
    # run" behavior, overriding the explicit instruction not to do that.
    def _is_stale_pasted_code(m):
        return m["role"] == "assistant" and bool(
            re.search(r"```(?:python|py)?\s*\n.{200,}", m["content"], re.DOTALL)
        )
    recent_msgs = [m for m in recent_msgs if not _is_stale_pasted_code(m)]
    if not recent_msgs:
        return ""
    msgs = recent_msgs[-max_msgs:]
    lines = [f"\n\n=== ROLLING MEMORY ({MEMORY_WINDOW_DAYS} days) — your recent business conversations ==="]
    current_session = None
    for m in msgs:
        if m["session_id"] != current_session:
            lines.append(f"\n[Session {m['timestamp']}]")
            current_session = m["session_id"]
        prefix = "USER" if m["role"] == "user" else "HAL"
        snippet = m["content"][:500].replace("\n", " ")
        if len(m["content"]) > 500:
            snippet += "..."
        lines.append(f"{prefix}: {snippet}")
    lines.append("\n=== END MEMORY — use this context to maintain continuity. Reference past discussions when relevant. ===\n")
    return "\n".join(lines)


def load_tickets_from_sheet(ws):
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
    if ws is None:
        return False
    try:
        cell = ws.find(ticket_id)
        if cell:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            ws.update_cell(cell.row, 4, new_status)
            ws.update_cell(cell.row, 7, now)
            if log_ws:
                log_ws.append_row([now, ticket_id, client, "Status change", old_status, new_status])
        return True
    except Exception:
        return False


def delete_ticket_from_sheet(ws, ticket_id):
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


def chi_api(endpoint, params=None):
    import urllib.request as _ur, json as _j, urllib.parse as _up
    portal_url = st.secrets.get("CHI_PORTAL_URL", "https://chi-insurance-portal-production.up.railway.app")
    api_key    = st.secrets.get("CHI_API_KEY", "")
    if not api_key:
        return None
    url = f"{portal_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
    if params:
        url += "?" + _up.urlencode(params)
    req = _ur.Request(url, headers={"X-API-Key": api_key, "Accept": "application/json"})
    try:
        with _ur.urlopen(req, timeout=10) as r:
            return _j.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="hal-logo">
        <div class="hal-title">HAL</div>
        <div class="hal-sub">Ashlar Intelligence Layer</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Mode**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏛 Business", use_container_width=True,
                     type="primary" if st.session_state.mode == "business" else "secondary"):
            st.session_state.mode = "business"
            st.session_state.active_module = "home"
            st.rerun()
    with col2:
        if st.button("🔒 Private", use_container_width=True,
                     type="primary" if st.session_state.mode == "private" else "secondary"):
            st.session_state.mode = "private"
            st.session_state.active_module = "home"
            st.rerun()

    st.divider()

    if st.session_state.mode == "business":
        st.markdown('<div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#7A6A5A;margin-bottom:8px">Ashlar Insurance</div>', unsafe_allow_html=True)

        modules_business = [
            ("🏠", "home",         "Dashboard"),
            ("💬", "hal_chat",     "HAL Assistant"),
            ("🧠", "memory",       "Memory"),
            ("🔄", "renewals",     "Renewals"),
            ("📊", "quotes",       "Quote Engine"),
            ("📄", "documents",    "Document Filler"),
            ("✉️", "comms",        "Communications"),
            ("📈", "commissions",  "Commissions"),
            ("🔍", "market",       "Market Intel"),
            ("🤝", "clients",      "Clients"),
            ("🏗️", "apps",         "App Builder"),
            ("🐾", "pets",         "PetsHealth"),
            ("🩺", "kira_nurse",   "Kira AI Nurse"),
            ("🧠", "chi_analyzer", "Insurance Analyzer"),
            ("🌐", "chi_portal",   "Client Portals"),
            ("🐱", "kira_pet",     "Kira Pet"),
        ]
        for icon, key, label in modules_business:
            active = st.session_state.active_module == key
            if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.active_module = key
                st.rerun()

    else:
        if st.session_state.private_unlocked:
            st.markdown('<div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#7A6A5A;margin-bottom:8px">Private Modules</div>', unsafe_allow_html=True)

            modules_private = [
                ("🏠", "home",             "Dashboard"),
                ("💬", "hal_chat",         "HAL Assistant"),
                ("🏛️", "lodge",            "Lodge Secretary"),
                ("📋", "minutes",          "Minutes & Docs"),
                ("👥", "attendance",       "Attendance"),
                ("📅", "events",           "Events & Gala"),
                ("💰", "finance",          "Financial Planner"),
                ("💪", "health",           "Health & Gym"),
                ("🔑", "settings_private", "Settings"),
            ]
            for icon, key, label in modules_private:
                active = st.session_state.active_module == key
                if st.button(f"{icon}  {label}", key=f"nav_p_{key}", use_container_width=True,
                             type="primary" if active else "secondary"):
                    st.session_state.active_module = key
                    st.rerun()

            st.divider()
            if st.button("🔓 Lock Private Mode", use_container_width=True):
                st.session_state.private_unlocked = False
                st.session_state.mode = "business"
                st.session_state.active_module = "home"
                st.rerun()

    st.divider()
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
    st.caption("Christos Iatropoulos · Your AI business operating system")

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
    st.markdown('<div class="section-header">Business Modules</div>', unsafe_allow_html=True)

    tiles = [
        ("🔄", "Renewals",           "Ιούνιος · Email · WhatsApp outreach",                   "renewals",    "live"),
        ("💬", "HAL Assistant",      "Ask anything — quotes, emails, analysis",                "hal_chat",    "live"),
        ("📊", "Quote Engine",       "Compare insurance proposals via PDF upload",              "quotes",      "live"),
        ("📄", "Document Filler",    "Auto-fill forms from contracts",                          "documents",   "live"),
        ("✉️", "Communications",     "Emails, appeal letters, renewal notices",                 "comms",       "live"),
        ("📈", "Commissions",        "Upload & analyse commission statements",                  "commissions", "dev"),
        ("🔍", "Market Intel",       "Niche analysis & expansion strategy",                     "market",      "live"),
        ("🤝", "Clients",            "Client cases & policy tracker",                           "clients",     "dev"),
        ("🏗️", "App Builder",        "Generate Python/Streamlit/Netlify apps",                  "apps",        "live"),
        ("🐾", "PetsHealth",         "Pet insurance tools & petshealth.gr",                    "pets",        "dev"),
        ("🩺", "Kira AI Nurse",      "AI health assistant — humans (triage, vitals, face scan)","kira_nurse",  "live"),
        ("🐱", "Kira Pet",           "AI Veterinary Nurse — pet owners",                        "kira_pet",    "live"),
        ("🧠", "Insurance Analyzer", "Analyse client profile + identify coverage gaps",          "chi_analyzer","live"),
        ("🌐", "CHI Portal",         "Manage 138 clients · 222 policies · Railway",             "chi_portal",  "live"),
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
        ("Ashlar Quote Engine",           "Streamlit · Claude API",              "github.com/chiinsurancebrokers/chi_quote_engine",                 "Live"),
        ("Ashlar Client Portal (Kourbelas)", "Netlify · HTML/JS",               "panteliskourbelas-chiinsurancebrokers.netlify.app",                "Live"),
        ("CHI Insurance Portal",          "Railway · Python",                    "chi-insurance-portal-production.up.railway.app",                  "Live"),
        ("Document Filler",               "Streamlit · ReportLab · Claude API",  "Internal",                                                        "Live"),
        ("PPT Quote Generator",           "python-pptx · Claude API",            "Internal",                                                        "Live"),
        ("Ashlar Assurance Site",         "WordPress · Breakdance",              "ashlar-assurance.com",                                            "In Build"),
        ("petshealth.gr",                 "HTML · Claude API",                   "petshealth.gr",                                                   "Live"),
        ("Kira AI Nurse",                 "Streamlit · Claude · GPT-4o · rPPG",  "kiraainurse.streamlit.app",                                       "Live"),
        ("Kira Pet — AI Vet Nurse",       "Streamlit · Claude API · Vision",     "kiraaipet.streamlit.app",                                         "Live"),
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
    with col1: st.metric("Next Lodge Meeting", "—")
    with col2: st.metric("Pending Masonic Tasks", "—")
    with col3: st.metric("Savings Rate", "—")

    st.divider()

    tiles = [
        ("🏛️", "Lodge Secretary",  "Correspondence, circulars, notices",      "lodge"),
        ("📋", "Minutes & Docs",   "Generate official Masonic minutes",         "minutes"),
        ("👥", "Attendance",       "Track member presence per session",          "attendance"),
        ("📅", "Events & Gala",    "Gala registrations, payments, lists",        "events"),
        ("💰", "Financial Planner","Savings, retirement modelling",              "finance"),
        ("💪", "Health & Gym",     "Workout plans, health monitor",              "health"),
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


def _hal_build_api_messages(chat_history):
    """
    Translate st.session_state.chat_history into the messages list for the
    Anthropic API. Plain text messages stay strings. Messages with an
    "attachments" field get expanded into a list of content blocks:
      - PDFs: smart-extracted to text if large (saves tokens), otherwise sent
        as a base64 `document` block so Claude reads them natively.
      - Images: base64 `image` blocks.
      - Text-ish (txt/csv/json/md): inlined as a labelled text block.
    """
    api_messages = []
    for m in chat_history:
        atts = m.get("attachments") or []
        if not atts:
            api_messages.append({"role": m["role"], "content": m["content"]})
            continue

        blocks = []
        for fname, fbytes, mime in atts:
            if mime == "application/pdf":
                extracted = None
                try:
                    from extraction import smart_pdf_to_text
                    extracted = smart_pdf_to_text(fbytes, fname)
                except Exception:
                    extracted = None
                if extracted:
                    blocks.append({"type": "text", "text": extracted})
                else:
                    blocks.append({
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.standard_b64encode(fbytes).decode("utf-8"),
                        },
                    })
            elif mime.startswith("image/"):
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": base64.standard_b64encode(fbytes).decode("utf-8"),
                    },
                })
            else:
                # Treat as UTF-8 text; errors="replace" so a stray byte never
                # breaks the whole turn — better degraded than dropped.
                try:
                    text = fbytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = fbytes.decode("utf-8", errors="replace")
                blocks.append({
                    "type": "text",
                    "text": f"=== ATTACHED FILE: {fname} ===\n{text}\n=== END {fname} ===",
                })

        # User's actual prompt goes last so Claude sees the files first, then
        # the question about them.
        blocks.append({"type": "text", "text": m["content"] or "(no message text — see attached files)"})
        api_messages.append({"role": m["role"], "content": blocks})
    return api_messages


def _hal_mime_for(filename: str, fallback: str) -> str:
    """Streamlit's UploadedFile.type is sometimes empty or generic; pin it from
    the extension so PDF/image branches in _hal_build_api_messages fire correctly."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "pdf":  "application/pdf",
        "png":  "image/png",
        "jpg":  "image/jpeg", "jpeg": "image/jpeg",
        "gif":  "image/gif",
        "webp": "image/webp",
        "txt":  "text/plain",
        "csv":  "text/csv",
        "json": "application/json",
        "md":   "text/markdown",
    }.get(ext, fallback or "application/octet-stream")


def render_hal_chat():
    import anthropic

    is_private = st.session_state.mode == "private"
    mode_label = "Private · Lodge & Personal" if is_private else "Business · Ashlar Insurance"
    st.markdown(f"## 💬 HAL Assistant — {mode_label}")

    system_prompt_business = """You are HAL — the AI operating system for Christos Iatropoulos, founder of Ashlar Insurance (formerly CHI Insurance Brokers), Athens, Greece. 

You specialise in international health insurance brokerage. Key knowledge:
- Carriers: Groupama, Generali, Ethniki, Morgan Price, NOW Health, Bupa Global, Safe Pet System
- Greek domestic plans: no free-network outpatient, no dental treatment, no psychiatric outpatient, no MRI/PET/CT outside hospitalisation. Greek deductibles: per-hospitalisation OR annual (important difference).
- International plans: full outpatient, diagnostics, physio, dental, psychiatric depending on plan.
- Bupa Global claim expertise: formal complaint procedure, FSPO (Dublin), 7-day escalation protocol.
- Tech stack: Python, Streamlit, Netlify, Railway, Claude API, ReportLab, python-pptx, Firebase, Google Sheets.
- Brand: Ashlar Insurance (ashlar-assurance.com). Pet brand: petshealth.gr.
- AI products: Kira AI Nurse (kiraainurse.streamlit.app) · Kira Pet (kiraaipet.streamlit.app).
- CHI Portal on Railway: 138 clients / 222 policies / 30 expiring — URL: chi-insurance-portal-production.up.railway.app
- Pantelis Kourbelas is a CLIENT of Ashlar Insurance, NOT the operator.

Respond in the language of the message. Be direct — produce outputs, not advice about producing them. For emails and letters, write them fully ready to send.

MEMORY — IMPORTANT:
You have persistent memory of business conversations from the last 7 days (rolling window). This memory is automatically injected into your context below as "=== ROLLING MEMORY ===". USE IT actively.

LIVE 2025 RATE TABLES (EUR, annual, Area 1 = Europe excl USA):

MORGAN PRICE (area1):
- Standard (HOSPITAL ONLY — NO outpatient): 30y=1,061 | 40y=1,380 | 45y=1,698 | 50y=2,041 | 55y=2,810 | 60y=3,548 | 65y=4,719
- Standard Plus (hospital + outpatient 80% + MRI/CT/PET): 30y=1,322 | 40y=1,719 | 45y=2,136 | 50y=2,495 | 55y=3,436 | 60y=4,338 | 65y=5,810
- Comprehensive (full): 30y=2,247 | 40y=2,921 | 45y=3,690 | 50y=4,104 | 55y=5,656 | 60y=7,849 | 65y=10,647

APRIL (area1):
- International: 30y=1,940 | 40y=2,501 | 45y=2,869 | 50y=3,700 | 55y=4,913 | 60y=6,670 | 65y=10,011
- Executive: 30y=4,459 | 40y=5,743 | 45y=6,596 | 50y=8,640 | 55y=10,678 | 60y=13,675 | 65y=20,142

IMG (area1, EUR 150 deductible):
- Silver: 30y=1,813 | 40y=2,339 | 45y=2,872 | 50y=3,764 | 55y=4,993 | 60y=6,366 | 65y=8,427
- Gold: 30y=2,320 | 40y=3,004 | 45y=3,694 | 50y=4,854 | 55y=6,450 | 60y=8,233 | 65y=10,914
- Platinum: 30y=2,912 | 40y=3,797 | 45y=4,686 | 50y=6,178 | 55y=8,238 | 60y=10,535 | 65y=13,987"""

    system_prompt_private = """You are HAL — the private AI assistant for Christos Iatropoulos. In this private mode you have access to lodge and personal context.

LODGE: You assist as secretary for Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ) and ΚΛΕΙΣ ΑΛΗΘΕΙΑΣ αρ. 1 (A.A.S.R.). Always use Masonic ∴ notation. Style: contemporary Greek Tektonic — NOT archaic. Closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος. Lodge email: st.akropolis.84@gmail.com. Speech order: 18 levels (Μαθηταί → Μέγας Διδάσκαλος).

PERSONAL: Financial adviser, nurse, gym coach. Help with savings plans, retirement modelling, workout programmes, health monitoring.

Never mix lodge content with business sessions. Respond in Greek unless asked otherwise."""

    system = system_prompt_private if is_private else system_prompt_business

    api_key = get_api_key() or st.session_state.get("api_key_input", "")

    # ── MEMORY INJECTION (business mode only) ────────────────────────────────
    if not is_private:
        if "_conv_ws" not in st.session_state:
            try:
                _, _, _conv_ws = get_gsheet()
                st.session_state._conv_ws = _conv_ws
            except Exception:
                st.session_state._conv_ws = None
        conv_ws = st.session_state.get("_conv_ws")
        if conv_ws is not None and not st.session_state.memory_injected:
            recent = load_recent_conversations(conv_ws, days=MEMORY_WINDOW_DAYS, mode_filter="business")
            recent = [m for m in recent if m["session_id"] != st.session_state.session_id]
            if recent:
                memory_block = summarise_memory_for_context(recent)
                system = system + memory_block
                st.session_state.memory_injected = True
                st.session_state._memory_count = len(recent)
        mem_count = st.session_state.get("_memory_count", 0)
        if mem_count > 0:
            st.caption(f"🧠 Memory: {mem_count} messages from last {MEMORY_WINDOW_DAYS} days loaded")

    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.info("HAL is ready. Ask anything about insurance, clients, quotes, documents, or use quick actions below.")
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        atts = msg.get("attachments") or []
                        if atts:
                            chips = " &nbsp; ".join(
                                f"📎 <code>{fn}</code>" for fn, _, _ in atts
                            )
                            st.markdown(
                                f"<div style='font-size:12px;color:#7A6A5A;margin-bottom:4px;'>{chips}</div>",
                                unsafe_allow_html=True,
                            )
                        st.write(msg["content"])
                else:
                    st.chat_message("assistant").write(msg["content"])

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
    groq_key = st.secrets.get("GROQ_API_KEY","") or st.secrets.get("groq_api_key","")
    oai_key  = st.secrets.get("OPENAI_API_KEY","") or st.secrets.get("openai_api_key","")
    stt_key  = groq_key or oai_key
    el_key   = st.secrets.get("ELEVENLABS_API_KEY","") or st.secrets.get("elevenlabs_api_key","")
    el_voice = st.secrets.get("ELEVENLABS_VOICE_ID","aTP4J5SJLQl74WTSRXKW")

    voice_tab1, voice_tab2 = st.tabs([
        "🎙️ Quick Voice (Web Speech)",
        "🔊 Full Voice (Groq/Whisper + ElevenLabs)" + (" ✓" if stt_key and el_key else " · setup required"),
    ])

    with voice_tab1:
        import html as _htmlesc
        st.caption("Browser speech recognition · Free · Greek · Copy transcript → paste into chat")
        _voice_widget_html = """<!DOCTYPE html><html><head><style>
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
  try{recognition.start();}catch(e){document.getElementById("status").textContent="Could not start: "+e.message;}
}
function copyText(){if(!transcript)return;navigator.clipboard.writeText(transcript).then(function(){document.getElementById("copy").textContent="✅ Copied!";setTimeout(function(){document.getElementById("copy").textContent="📋 Copy";},2000);});}
</script></body></html>"""
        # streamlit.components.v1.html() renders inside an <iframe> with no way to grant
        # microphone permission, so SpeechRecognition.start() is blocked by the browser's
        # Permissions Policy before it ever fires onstart/onerror — the mic button looks
        # like it does nothing. Building the iframe by hand lets us add allow="microphone".
        _voice_widget_srcdoc = _htmlesc.escape(_voice_widget_html, quote=True)
        st.markdown(
            f'<iframe srcdoc="{_voice_widget_srcdoc}" height="60" width="100%" '
            f'style="border:none;" allow="microphone" '
            f'sandbox="allow-scripts allow-same-origin allow-modals"></iframe>',
            unsafe_allow_html=True,
        )

    with voice_tab2:
        if not stt_key or not el_key:
            st.info("Add **GROQ_API_KEY** (free at console.groq.com) + **ELEVENLABS_API_KEY** to Streamlit secrets.")
        else:
            st.caption("Record → Whisper transcribes → Claude responds → ElevenLabs speaks back")
            audio_val = st.audio_input("🎙️ Speak to HAL", key="hal_voice_input")
            if audio_val is not None:
                import urllib.request as _urv, json as _jv, base64 as _b64v
                audio_bytes = audio_val.read()
                with st.spinner("🎙️ Transcribing..."):
                    try:
                        if groq_key:
                            from groq import Groq as _Groq
                            _gc = _Groq(api_key=groq_key)
                            transcript = _gc.audio.transcriptions.create(
                                model="whisper-large-v3",
                                file=("audio.webm", audio_bytes, "audio/webm"),
                                language="el",
                            ).text.strip()
                        else:
                            from openai import OpenAI as _OAI
                            _oc = _OAI(api_key=oai_key)
                            transcript = _oc.audio.transcriptions.create(
                                model="whisper-1",
                                file=("audio.webm", audio_bytes, "audio/webm"),
                                language="el",
                            ).text.strip()
                    except Exception as e:
                        transcript = ""
                        st.error(f"Transcription error: {e}")

                if transcript:
                    st.markdown(f"**🗣️ You:** {transcript}")
                    st.session_state.chat_history.append({"role":"user","content":transcript})
                    with st.spinner("HAL thinking..."):
                        try:
                            import anthropic as _ant
                            _cl = _ant.Anthropic(api_key=api_key)
                            voice_system = system + "\n\nIMPORTANT FOR VOICE MODE: No markdown, no bullets. Complete sentences. Under 3 sentences unless essential."
                            _r = _cl.messages.create(
                                model="claude-sonnet-4-6", max_tokens=600,
                                system=voice_system,
                                messages=_hal_build_api_messages(st.session_state.chat_history[-10:])
                            )
                            reply = _r.content[0].text
                        except Exception as e:
                            reply = f"Error: {e}"
                    st.session_state.chat_history.append({"role":"assistant","content":reply})
                    st.markdown(f"**HAL:** {reply}")
                    with st.spinner("🔊 ElevenLabs speaking..."):
                        tts_text = reply
                        _pron = {"Morgan Price":"Μόργκαν Πράις","Standard Plus":"Στάνταρντ Πλας","Standard":"Στάνταρντ","Comprehensive":"Κόμπριχενσιβ","International":"Ιντερνάσιοναλ","Executive":"Εξέκιουτιβ","Platinum":"Πλάτινουμ","IMG":"Άι Εμ Τζι","April":"Απρίλ","Bupa":"Μπούπα","outpatient":"εξωνοσοκομειακά","inpatient":"νοσοκομειακή κάλυψη","deductible":"απαλλαγή","premium":"ασφάλιστρο","HAL":"Χαλ","Ashlar":"Άσλαρ","Kira":"Κίρα"}
                        for en, el in _pron.items():
                            tts_text = tts_text.replace(en, el)
                        tts_req = _urv.Request(
                            f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice}",
                            data=_jv.dumps({"text":tts_text,"model_id":"eleven_multilingual_v2","voice_settings":{"stability":0.55,"similarity_boost":0.8}}).encode(),
                            headers={"xi-api-key":el_key,"Content-Type":"application/json","Accept":"audio/mpeg"}
                        )
                        try:
                            with _urv.urlopen(tts_req, timeout=30) as r:
                                st.audio(r.read(), format="audio/mpeg", autoplay=True)
                        except Exception as e:
                            st.warning(f"ElevenLabs: {e}")
                else:
                    st.warning("No speech detected — try again.")

    # ── FILE ATTACHMENTS ─────────────────────────────────────────────────────
    # Always-visible panel above the chat input. Files staged here are sent
    # with the next message and stay in chat history for follow-ups.
    st.markdown(
        "<div style='font-size:11px;font-weight:600;letter-spacing:2px;"
        "text-transform:uppercase;color:#7A6A5A;margin:8px 0 4px;'>"
        "📎 Attach files for next message</div>",
        unsafe_allow_html=True,
    )
    _up_col, _stage_col = st.columns([3, 2])
    with _up_col:
        _uploaded = st.file_uploader(
            "Drop quotes, screenshots, or text files here — then ask HAL anything about them",
            type=["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv", "json", "md"],
            accept_multiple_files=True,
            key=f"hal_file_uploader_{st.session_state.hal_uploader_nonce}",
            label_visibility="visible",
        )
    # Re-stage on every rerun from whatever the uploader currently holds.
    # UploadedFile objects don't persist across reruns, so snapshot their
    # bytes immediately. Same key + same files = same upload, no double-read.
    if _uploaded:
        st.session_state.hal_pending_files = [
            (f.name, f.getvalue(), _hal_mime_for(f.name, getattr(f, "type", "") or ""))
            for f in _uploaded
        ]
    elif _uploaded is not None:
        # Uploader rendered but empty (user removed everything) — clear stage.
        st.session_state.hal_pending_files = []

    with _stage_col:
        pend = st.session_state.hal_pending_files
        if pend:
            total_kb = sum(len(b) for _, b, _ in pend) / 1024
            st.markdown(
                f"<div style='font-size:12px;color:#A89880;'>"
                f"<b>{len(pend)} file(s) staged</b> · {total_kb:,.0f} KB total<br>"
                + "<br>".join(f"📄 <code>{fn}</code>" for fn, _, _ in pend)
                + "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Clear staged files", key="hal_clear_pending", use_container_width=True):
                st.session_state.hal_pending_files = []
                st.session_state.hal_uploader_nonce += 1
                st.rerun()
        else:
            st.caption("No files staged. Drop PDFs / images / CSV / TXT on the left.")

    # Tailor placeholder to whether files are staged
    if st.session_state.hal_pending_files:
        _placeholder = f"Ask HAL about your {len(st.session_state.hal_pending_files)} staged file(s)…"
    else:
        _placeholder = "Message HAL..."

    user_input = st.chat_input(_placeholder)
    if user_input:
        # Snapshot whatever's staged right now, then clear the stage so the next
        # turn starts fresh (and bump the uploader key so the widget remounts empty).
        _atts_for_msg = list(st.session_state.hal_pending_files)
        st.session_state.hal_pending_files = []
        if _atts_for_msg:
            st.session_state.hal_uploader_nonce += 1

        _user_msg = {"role": "user", "content": user_input}
        if _atts_for_msg:
            _user_msg["attachments"] = _atts_for_msg
        st.session_state.chat_history.append(_user_msg)

        if not is_private:
            conv_ws = st.session_state.get("_conv_ws")
            # Sheet log: append a note about attachments so the memory window
            # later shows "user asked X with these files" rather than orphaned text.
            _log_text = user_input
            if _atts_for_msg:
                _log_text += "\n[attached: " + ", ".join(fn for fn, _, _ in _atts_for_msg) + "]"
            save_message_to_sheet(conv_ws, "business", st.session_state.session_id, "user", _log_text)
        if not api_key:
            st.session_state.chat_history.append({"role": "assistant", "content": "⚠️ No API key found. Add Claude_API_Key to your Streamlit secrets."})
        else:
            with st.spinner("HAL is thinking..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    messages = _hal_build_api_messages(st.session_state.chat_history)
                    code_exec_system = system + """

CODE EXECUTION — you have a sandboxed Python/Bash environment (no internet access inside it).
You MUST use it — not just describe what code would do — whenever the user asks for:
- An actual file: PDF, PPTX, Excel, image, etc. (ReportLab, python-pptx, openpyxl, Pillow are pre-installed)
- A real computed result: precise calculations, data processing, anything error-prone by reasoning alone
Do NOT paste a Python script in your text reply and tell the user to run it themselves — that is the
WRONG behavior for this assistant. Instead, write the script INTO THE SANDBOX, RUN it there, and hand
back the finished artifact. After creating a file in the sandbox, ALWAYS emit it back by running, e.g.:
  echo "===FILE:report.pdf===" && base64 report.pdf && echo "===ENDFILE==="
so the surrounding application can detect, decode, and offer it as a download. Do this for every file
you create that the user should receive. If you find yourself about to write a code block in your text
reply for the user to copy, stop — run it in the sandbox instead.

IMPORTANT — if the ROLLING MEMORY section above contains earlier HAL replies that pasted Python/code as
text instead of running it, those are recorded mistakes from before code execution was wired up. Do NOT
treat them as a style to follow. This instruction always overrides that pattern, no matter how many
times it appears in memory or chat history above."""
                    response = client.beta.messages.create(
                        model="claude-sonnet-4-6", max_tokens=8192,
                        system=code_exec_system, messages=messages,
                        tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
                        betas=["code-execution-2025-08-25"],
                    )
                    all_blocks = list(response.content)

                    # Code execution on a non-trivial task (e.g. building a multi-section PDF) can
                    # pause mid-turn; resubmitting lets Claude continue rather than the user seeing a
                    # cut-off result. Accumulate blocks from every turn — the file/text Claude produced
                    # before a pause must not be dropped when a later turn's response replaces `response`.
                    _continue_attempts = 0
                    while getattr(response, "stop_reason", None) == "pause_turn" and _continue_attempts < 3:
                        messages = messages + [{"role": "assistant", "content": response.content}]
                        response = client.beta.messages.create(
                            model="claude-sonnet-4-6", max_tokens=8192,
                            system=code_exec_system, messages=messages,
                            tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
                            betas=["code-execution-2025-08-25"],
                        )
                        all_blocks.extend(response.content)
                        _continue_attempts += 1

                    reply_parts = []
                    generated_files = []  # list of (filename, raw_bytes)
                    for block in all_blocks:
                        if getattr(block, "type", None) == "text":
                            reply_parts.append(block.text)
                        elif getattr(block, "type", None) == "bash_code_execution_tool_result":
                            content = getattr(block, "content", None)
                            stdout = getattr(content, "stdout", "") if content else ""
                            for fname, b64data in re.findall(
                                r'===FILE:(.+?)===\n(.*?)\n===ENDFILE===', stdout or "", re.DOTALL
                            ):
                                try:
                                    generated_files.append((fname.strip(), base64.b64decode(b64data.strip())))
                                except Exception:
                                    pass  # malformed emit — skip, text reply still shows below

                    reply = "\n".join(reply_parts).strip() or "(no text response)"
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    st.session_state["hal_last_files"] = generated_files  # replace, even if empty — avoid showing stale files from a prior turn
                    if not is_private:
                        conv_ws = st.session_state.get("_conv_ws")
                        save_message_to_sheet(conv_ws, "business", st.session_state.session_id, "assistant", reply)
                except Exception as e:
                    st.session_state.chat_history.append({"role": "assistant", "content": f"⚠️ Error: {str(e)}"})
        st.rerun()

    if st.session_state.get("hal_last_files"):
        st.markdown("---")
        for _i, (fname, fbytes) in enumerate(st.session_state["hal_last_files"]):
            st.download_button(f"⬇️ {fname}", data=fbytes, file_name=fname, key=f"dl_{_i}_{fname}")

    if st.session_state.chat_history:
        if st.button("🗑 Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# RENEWALS MODULE — Live data from CHI Insurance Portal (Railway)
# Uses CHI_PORTAL_URL + CHI_API_KEY (same as chi_api() helper above)
# ══════════════════════════════════════════════════════════════════════════════

# Bank account HTML blocks (per agent)
_BANK_INFO = {
    "3p": """
<h3 style="color:#1976d2;">Τραπεζικοί Λογαριασμοί</h3>
<p style="font-size:13px;color:#555;"><strong>ΔΙΚΑΙΟΥΧΟΣ: 3P INSURANCE AGENTS AE · ΑΦΜ 800478440</strong></p>
<table style="width:100%;border-collapse:collapse;font-size:13px;">
<tr style="background:#f5f5f5;"><td style="padding:8px;border:1px solid #ddd;"><strong>ALPHA BANK</strong></td><td style="padding:8px;border:1px solid #ddd;">GR4801401340134002320003540</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd;"><strong>ΕΘΝΙΚΗ ΤΡΑΠΕΖΑ</strong></td><td style="padding:8px;border:1px solid #ddd;">GR3901108910000089147029808</td></tr>
<tr style="background:#f5f5f5;"><td style="padding:8px;border:1px solid #ddd;"><strong>EUROBANK</strong></td><td style="padding:8px;border:1px solid #ddd;">GR3302602210000370200676490</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd;"><strong>ΠΕΙΡΑΙΩΣ</strong></td><td style="padding:8px;border:1px solid #ddd;">GR6201720890005089072164520</td></tr>
</table>""",
    "ca": """
<h3 style="color:#1976d2;">Τραπεζικοί Λογαριασμοί</h3>
<p style="font-size:13px;color:#555;"><strong>ΔΙΚΑΙΟΥΧΟΣ: CA Insurance Agents · ΑΦΜ 800338387</strong></p>
<table style="width:100%;border-collapse:collapse;font-size:13px;">
<tr style="background:#f5f5f5;"><td style="padding:8px;border:1px solid #ddd;"><strong>ALPHA BANK</strong></td><td style="padding:8px;border:1px solid #ddd;">GR4101401460146002320015029</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd;"><strong>EUROBANK</strong></td><td style="padding:8px;border:1px solid #ddd;">GR6802600270000300201693054</td></tr>
<tr style="background:#f5f5f5;"><td style="padding:8px;border:1px solid #ddd;"><strong>ΕΘΝΙΚΗ ΤΡΑΠΕΖΑ</strong></td><td style="padding:8px;border:1px solid #ddd;">GR7301106690000066900657306</td></tr>
</table>""",
    "bu": """
<h3 style="color:#1976d2;">Κωδικός Πληρωμής RF</h3>
<p style="font-size:13px;color:#555;"><strong>BROKERS UNION Α.Ε. · ΑΦΜ 800319742</strong></p>
<div style="background:#e3f2fd;padding:20px;border-radius:8px;text-align:center;margin:15px 0;">
<p style="margin:0 0 10px 0;font-size:14px;color:#666;">Κωδικός RF για πληρωμή σε οποιαδήποτε τράπεζα:</p>
<p style="margin:0;font-size:20px;font-weight:bold;color:#1565c0;font-family:monospace;">{rf_code}</p>
</div>""",
}


def _rn_fetch(endpoint, params=None):
    """Fetch from CHI Portal using CHI_API_KEY / CHI_PORTAL_URL."""
    portal_url = st.secrets.get("CHI_PORTAL_URL", "https://chi-insurance-portal-production.up.railway.app").rstrip("/")
    api_key    = st.secrets.get("CHI_API_KEY", "")
    if not api_key:
        return None, "CHI_API_KEY not set in Streamlit secrets."
    try:
        r = requests.get(
            f"{portal_url}/api/{endpoint.lstrip('/')}",
            headers={"X-API-Key": api_key},
            params=params,
            timeout=15,
        )
        if r.status_code == 401:
            return None, "API key rejected — check CHI_API_KEY in secrets."
        if r.status_code != 200:
            return None, f"Portal HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"Cannot reach {portal_url} — is Railway running?"
    except Exception as e:
        return None, f"Request error: {e}"


def _days_badge_html(days):
    if days <= 2:
        return f'<span style="background:#dc2626;color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;">🔴 {days}d</span>'
    elif days <= 7:
        return f'<span style="background:#ea580c;color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;">🟠 {days}d</span>'
    elif days <= 14:
        return f'<span style="background:#ca8a04;color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;">🟡 {days}d</span>'
    else:
        return f'<span style="background:#16a34a;color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;">🟢 {days}d</span>'


def _rn_send_gmail(to_email, subject, body_html):
    sender   = st.secrets.get("GMAIL_SENDER", "")
    password = st.secrets.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not sender or not password:
        return False, "GMAIL_SENDER / GMAIL_APP_PASSWORD not set in secrets."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = to_email
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)


def _rn_send_whatsapp(to_phone, message_body):
    sid   = st.secrets.get("TWILIO_SID", "")
    token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
    from_ = st.secrets.get("TWILIO_FROM", "whatsapp:+14155238886")
    if not sid or not token:
        return False, "TWILIO_SID / TWILIO_AUTH_TOKEN not set in secrets."
    phone = re.sub(r"[^\d+]", "", str(to_phone))
    if not phone.startswith("+"):
        phone = "+30" + phone.lstrip("0")
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": from_, "To": f"whatsapp:{phone}", "Body": message_body},
            timeout=15,
        )
        if r.status_code in (200, 201):
            return True, "Sent"
        return False, f"Twilio {r.status_code}: {r.json().get('message', r.text[:200])}"
    except Exception as e:
        return False, str(e)


def _build_renewal_email(policy, agent="3p"):
    client_name = policy.get("client_name", "Πελάτης")
    policy_type = policy.get("type", "Ασφαλιστήριο")
    provider    = policy.get("insurer", "")
    premium     = policy.get("premium", "")
    expiry      = policy.get("expiry_date", policy.get("expiration_date", ""))
    plate       = policy.get("vehicle_plate", policy.get("license_plate", ""))
    rf_code     = policy.get("payment_code", "")
    try:
        exp_display = datetime.strptime(expiry[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        exp_display = expiry
    premium_str = f"EUR {float(premium):.2f}" if premium else ""
    plate_html  = f"<p style='margin:0 0 6px 0;'><strong>Αρ. Κυκλοφορίας:</strong> {plate}</p>" if plate else ""
    bank_html = _BANK_INFO.get(agent, _BANK_INFO["3p"])
    if agent == "bu":
        bank_html = bank_html.format(rf_code=rf_code) if rf_code else '<p style="color:#d32f2f;"><strong>⚠️ Παρακαλούμε επικοινωνήστε μαζί μας για τον κωδικό RF.</strong></p>'
    subject = f"Ανανέωση Ασφαλιστηρίου – {policy_type}" + (f" ({provider})" if provider else "")
    body = f"""<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#1a237e;padding:20px;border-radius:10px;margin-bottom:25px;text-align:center;">
    <h2 style="color:white;margin:0;font-size:20px;">CHI Insurance Brokers</h2>
    <p style="color:#90caf9;margin:6px 0 0 0;font-size:13px;">Ανακοίνωση Ανανέωσης Ασφαλιστηρίου</p>
  </div>
  <p>Αγαπητέ/ή <strong>{client_name}</strong>,</p>
  <p>Σας ενημερώνουμε ότι το ασφαλιστήριό σας λήγει σύντομα και χρειάζεται ανανέωση για να διατηρηθεί η κάλυψή σας αδιάλειπτη.</p>
  <div style="background:#f5f5f5;padding:16px;border-radius:8px;margin:20px 0;border-left:4px solid #1a237e;">
    <p style="margin:0 0 6px 0;"><strong>Είδος ασφάλισης:</strong> {policy_type}{f" – {provider}" if provider else ""}</p>
    {plate_html}
    <p style="margin:0 0 6px 0;"><strong>Ημερομηνία λήξης:</strong> <span style="color:#d32f2f;font-weight:bold;">{exp_display}</span></p>
    {"<p style='margin:0;'><strong>Ποσό ανανέωσης:</strong> <span style='font-size:18px;font-weight:bold;color:#1a237e;'>" + premium_str + "</span></p>" if premium_str else ""}
  </div>
  <p>Για την εξόφληση, παρακαλούμε χρησιμοποιήστε έναν από τους παρακάτω τραπεζικούς λογαριασμούς και επικοινωνήστε μαζί μας για επιβεβαίωση.</p>
  {bank_html}
  <div style="margin-top:25px;padding:15px;background:#e8f5e9;border-radius:8px;">
    <p style="margin:0;font-size:13px;color:#2e7d32;">📞 Για οποιαδήποτε απορία, είμαστε στη διάθεσή σας.<br>✉️ CHI Insurance Brokers</p>
  </div>
  <p style="margin-top:20px;">Με εκτίμηση,<br><strong>CHI Insurance Brokers</strong></p>
</div></body></html>"""
    return subject, body


def _build_renewal_whatsapp(policy):
    client_name = policy.get("client_name", "")
    policy_type = policy.get("type", "ασφαλιστήριο")
    provider    = policy.get("insurer", "")
    expiry      = policy.get("expiry_date", policy.get("expiration_date", ""))
    premium     = policy.get("premium", "")
    days_left   = policy.get("days_left", "")
    try:
        exp_display = datetime.strptime(expiry[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        exp_display = expiry
    premium_str = f"EUR {float(premium):.2f}" if premium else ""
    days_str    = f" ({days_left} ημέρες)" if isinstance(days_left, int) else ""
    lines = [
        f"Αγαπητέ/ή {client_name},", "",
        f"Σας ενημερώνουμε ότι το *{policy_type}{f' – {provider}' if provider else ''}* λήγει στις *{exp_display}*{days_str}.",
    ]
    if premium_str:
        lines.append(f"Ποσό ανανέωσης: *{premium_str}*")
    lines += ["", "Παρακαλούμε επικοινωνήστε μαζί μας για την ανανέωση.", "", "📞 CHI Insurance Brokers"]
    return "\n".join(lines)


def render_renewals():
    st.markdown("## 🔄 Renewals — Ανανεώσεις")
    st.caption("Live data from CHI Insurance Portal (Railway) · Email & WhatsApp outreach")

    portal_ok  = bool(st.secrets.get("CHI_PORTAL_URL") and st.secrets.get("CHI_API_KEY"))
    gmail_ok   = bool(st.secrets.get("GMAIL_SENDER") and st.secrets.get("GMAIL_APP_PASSWORD"))
    twilio_ok  = bool(st.secrets.get("TWILIO_SID") and st.secrets.get("TWILIO_AUTH_TOKEN"))

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Portal API",        "✅ Connected" if portal_ok  else "❌ Not set")
    sc2.metric("Gmail",             "✅ Ready"     if gmail_ok   else "❌ Not set")
    sc3.metric("Twilio / WhatsApp", "✅ Ready"     if twilio_ok  else "❌ Not set")

    if not portal_ok:
        st.error("Ορίστε **CHI_PORTAL_URL** και **CHI_API_KEY** στα Streamlit secrets.")
        with st.expander("⚙️ Πώς να ρυθμίσετε"):
            st.code("""# Streamlit Cloud → Settings → Secrets — προσθήκη:
CHI_PORTAL_URL    = "https://chi-insurance-portal-production.up.railway.app"
CHI_API_KEY       = "your-chi-api-key"        # ίδιο με CHI_API_KEY στο Railway
GMAIL_SENDER      = "your@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
TWILIO_SID        = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN  = "your_auth_token"
TWILIO_FROM       = "whatsapp:+14155238886"
""", language="toml")
        return

    st.divider()

    ctl1, ctl2, ctl3 = st.columns([1, 1, 2])
    with ctl1:
        days_filter = st.selectbox("Εμφάνιση", [7, 14, 30, 60, 90], index=2,
                                   format_func=lambda x: f"Επόμενες {x} μέρες")
    with ctl2:
        agent_default = st.selectbox("Default Agent", ["3p", "ca", "bu"],
                                     format_func=lambda x: {"3p": "3P Insurance", "ca": "CA Insurance", "bu": "Brokers Union"}[x])
    with ctl3:
        if st.button("🔄 Ανανέωση από Portal", type="primary", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("rn_cache_"):
                    del st.session_state[k]

    cache_key = f"rn_cache_{days_filter}"
    if cache_key not in st.session_state:
        with st.spinner("Φόρτωση ανανεώσεων από CHI Portal (Railway)…"):
            data, err = _rn_fetch("/renewals")
            if err:
                data2, err2 = _rn_fetch("/policies/expiring", {"days": days_filter})
                if err2:
                    st.error(f"Portal error: {err}")
                    return
                all_p  = data2 if isinstance(data2, list) else []
                urgent   = [p for p in all_p if p.get("days_left", 99) <= 7]
                soon     = [p for p in all_p if 7  < p.get("days_left", 99) <= 30]
                upcoming = [p for p in all_p if p.get("days_left", 99) > 30]
                data = {"urgent": urgent, "soon": soon, "upcoming": upcoming}
            st.session_state[cache_key] = data

    raw = st.session_state[cache_key]
    all_renewals = [p for p in
                    raw.get("urgent",[]) + raw.get("soon",[]) + raw.get("upcoming",[])
                    if p.get("days_left", 999) <= days_filter]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Σύνολο",            len(all_renewals))
    k2.metric("🔴 Επείγοντα ≤7d",  len([p for p in all_renewals if p.get("days_left",99) <= 7]))
    k3.metric("🟠 ≤14d",           len([p for p in all_renewals if 7  < p.get("days_left",99) <= 14]))
    k4.metric("🟡 ≤30d",           len([p for p in all_renewals if 14 < p.get("days_left",99) <= 30]))

    st.divider()

    if not all_renewals:
        st.info(f"Δεν υπάρχουν ανανεώσεις για τις επόμενες {days_filter} μέρες.")
        return

    if "renewal_sent" not in st.session_state:
        st.session_state.renewal_sent = {}

    sections = [
        ("🔴 Επείγοντα — λήγουν σε ≤ 7 μέρες",  [p for p in all_renewals if p.get("days_left",99) <= 7],          "#fef2f2"),
        ("🟠 Σύντομα — 8 έως 14 μέρες",          [p for p in all_renewals if 7  < p.get("days_left",99) <= 14],    "#fff7ed"),
        ("🟡 Επόμενος μήνας — 15 έως 30 μέρες",  [p for p in all_renewals if 14 < p.get("days_left",99) <= 30],    "#fefce8"),
        ("🟢 Αργότερα — άνω των 30 μερών",        [p for p in all_renewals if p.get("days_left",99) > 30],          "#f0fdf4"),
    ]

    for section_title, policies, bg in sections:
        if not policies:
            continue
        st.markdown(f"### {section_title}")

        for idx, policy in enumerate(policies):
            pid       = str(policy.get("id", f"p{idx}"))
            client    = policy.get("client_name", "—")
            ptype     = policy.get("type", "—")
            provider  = policy.get("insurer", "—")
            email     = policy.get("client_email", "")
            phone     = policy.get("client_phone", "")
            premium   = policy.get("premium", "")
            days_left = policy.get("days_left", "—")
            expiry    = policy.get("expiry_date", policy.get("expiration_date", ""))
            plate     = policy.get("vehicle_plate", policy.get("license_plate", ""))
            sent_info = st.session_state.renewal_sent.get(pid, {})

            try:
                exp_display = datetime.strptime(expiry[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                exp_display = expiry

            premium_display = f"EUR {float(premium):.2f}" if premium else "—"
            plate_str       = f" · 🚗 {plate}" if plate else ""

            with st.container():
                st.markdown(
                    f'<div style="background:{bg};border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin-bottom:10px;">',
                    unsafe_allow_html=True,
                )
                row1a, row1b = st.columns([5, 1])
                with row1a:
                    st.markdown(f"**{client}** · {ptype} · *{provider}*{plate_str}")
                    st.caption(f"Λήξη: **{exp_display}** · Ποσό: {premium_display} · 📧 {email or '—'} · 📱 {phone or '—'}")
                with row1b:
                    if isinstance(days_left, int):
                        st.markdown(_days_badge_html(days_left), unsafe_allow_html=True)

                col_ag, col_pv, col_em, col_wa, col_st = st.columns([1.2, 1.1, 1, 1, 1.5])

                with col_ag:
                    agent = st.selectbox("Agent", ["3p","ca","bu"], key=f"agent_{pid}",
                                         index=["3p","ca","bu"].index(agent_default),
                                         format_func=lambda x: {"3p":"3P","ca":"CA","bu":"BU"}[x],
                                         label_visibility="collapsed")
                with col_pv:
                    if st.button("👁 Preview", key=f"prev_{pid}", use_container_width=True):
                        subj, body = _build_renewal_email(policy, agent)
                        st.session_state[f"rn_prev_{pid}"] = (subj, body, email)
                with col_em:
                    e_sent = sent_info.get("email", False)
                    if st.button("✅ Email" if e_sent else "📤 Email", key=f"remail_{pid}",
                                 use_container_width=True, disabled=e_sent):
                        if not email:
                            st.error(f"Δεν υπάρχει email για {client}")
                        else:
                            subj, body = _build_renewal_email(policy, agent)
                            ok, msg = _rn_send_gmail(email, subj, body)
                            if ok:
                                st.session_state.renewal_sent.setdefault(pid, {})["email"] = True
                                st.success(f"✅ → {email}")
                                st.rerun()
                            else:
                                st.error(f"Email error: {msg}")
                with col_wa:
                    w_sent = sent_info.get("wa", False)
                    if st.button("✅ WA" if w_sent else "💬 WhatsApp", key=f"rwa_{pid}",
                                 use_container_width=True, disabled=w_sent):
                        if not phone:
                            st.error(f"Δεν υπάρχει τηλέφωνο για {client}")
                        else:
                            msg_body = _build_renewal_whatsapp(policy)
                            ok, msg  = _rn_send_whatsapp(phone, msg_body)
                            if ok:
                                st.session_state.renewal_sent.setdefault(pid, {})["wa"] = True
                                st.success(f"✅ → {phone}")
                                st.rerun()
                            else:
                                st.error(f"WhatsApp error: {msg}")
                with col_st:
                    badges = []
                    if sent_info.get("email"): badges.append("📧 Sent")
                    if sent_info.get("wa"):    badges.append("💬 Sent")
                    if badges:
                        st.success(" · ".join(badges))

                st.markdown("</div>", unsafe_allow_html=True)

            # Email preview expander
            prev_key = f"rn_prev_{pid}"
            if prev_key in st.session_state:
                subj, body, default_email = st.session_state[prev_key]
                with st.expander(f"📧 Preview email — {client}", expanded=True):
                    st.markdown(f"**Subject:** `{subj}`")
                    pc1, pc2 = st.columns([3, 1])
                    with pc1:
                        send_to = st.text_input("Αποστολή σε:", value=default_email, key=f"pto_{pid}")
                    with pc2:
                        if st.button("📤 Αποστολή τώρα", key=f"psend_{pid}", type="primary", use_container_width=True):
                            ok, err_msg = _rn_send_gmail(send_to, subj, body)
                            if ok:
                                st.session_state.renewal_sent.setdefault(pid, {})["email"] = True
                                st.success(f"✅ Εστάλη → {send_to}")
                                del st.session_state[prev_key]
                                st.rerun()
                            else:
                                st.error(err_msg)
                    st.components.v1.html(body, height=480, scrolling=True)

    st.divider()
    st.markdown("### 📦 Μαζική Αποστολή")
    urgent_list = [p for p in all_renewals if p.get("days_left", 99) <= 7]

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button(f"📤 Email σε όλους τους επείγοντες ({len(urgent_list)})",
                     use_container_width=True, disabled=len(urgent_list)==0):
            targets = [p for p in urgent_list if p.get("client_email")]
            ok_c = fail_c = 0
            prog = st.progress(0)
            for i, p in enumerate(targets):
                pid = str(p.get("id", i))
                subj, body = _build_renewal_email(p, agent_default)
                ok, _ = _rn_send_gmail(p["client_email"], subj, body)
                if ok:
                    st.session_state.renewal_sent.setdefault(pid, {})["email"] = True
                    ok_c += 1
                else:
                    fail_c += 1
                prog.progress((i+1)/max(len(targets),1))
            st.success(f"✅ {ok_c} emails · ❌ {fail_c} αποτυχίες")
            st.rerun()

    with b2:
        if st.button(f"💬 WhatsApp σε όλους τους επείγοντες ({len(urgent_list)})",
                     use_container_width=True, disabled=len(urgent_list)==0):
            targets = [p for p in urgent_list if p.get("client_phone")]
            ok_c = fail_c = 0
            prog = st.progress(0)
            for i, p in enumerate(targets):
                pid = str(p.get("id", i))
                msg_body = _build_renewal_whatsapp(p)
                ok, _ = _rn_send_whatsapp(p["client_phone"], msg_body)
                if ok:
                    st.session_state.renewal_sent.setdefault(pid, {})["wa"] = True
                    ok_c += 1
                else:
                    fail_c += 1
                prog.progress((i+1)/max(len(targets),1))
            st.success(f"✅ {ok_c} WhatsApp · ❌ {fail_c} αποτυχίες")
            st.rerun()

    with b3:
        if st.button("🔁 Reset sent status", use_container_width=True):
            st.session_state.renewal_sent = {}
            st.rerun()


def render_quotes():
    st.markdown("## 📊 Quote Engine")
    st.caption("Live 2025 rates · Morgan Price · April · IMG · PDF extraction · PPTX generation")

    tab_live, tab_pdf, tab_terms, tab_results = st.tabs([
        "⚡ Instant Quote (Rate Tables)",
        "📄 PDF → AI Extraction → PPTX",
        "🔍 Terms Analyzer (Εξαιρέσεις)",
        "📋 Saved Results",
    ])

    # ══ TAB 1: INSTANT LIVE QUOTE ══════════════════════════════════════════
    with tab_live:
        if not RATES_LOADED:
            st.warning("rate_tables.py not found in repo. Add it alongside app.py.")

        if RATES_LOADED:
            st.markdown("### Client Details")
            qc1, qc2, qc3 = st.columns(3)
            with qc1:
                q_name = st.text_input("Client name", placeholder="Katia Totikidou")
                q_age  = st.number_input("Age", min_value=0, max_value=80, value=45)
            with qc2:
                q_area   = st.radio("Coverage area", ["Area 1 — Europe (excl USA)", "Area 2 — Worldwide incl USA"])
                area_key = "area1" if "Area 1" in q_area else "area2"
            with qc3:
                q_notes = st.text_area("Client priorities / notes", height=100,
                    placeholder="e.g. Needs outpatient, travels to USA, cancer history...")

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
                mc1, mc2 = st.columns([4, 1])
                mc1.markdown(f"👤 **{m['name']}** — Age {m['age']}")
                if mc2.button("✕", key=f"del_m_{i}") and len(st.session_state.quote_members) > 1:
                    st.session_state.quote_members.pop(i)
                    st.rerun()

            st.markdown("### Plans to compare")
            all_plans = list(RATE_PLANS)
            selected_plans = st.multiselect("Select plans",
                options=[p[2] for p in all_plans],
                default=["Morgan Price Standard", "Morgan Price Comprehensive",
                         "April International", "April Executive", "IMG Silver", "IMG Gold"])

            if st.button("⚡ Generate Comparison", type="primary", use_container_width=True):
                if not st.session_state.quote_members:
                    st.warning("Add at least one member.")
                else:
                    results  = []
                    plan_map = {p[2]: p for p in all_plans}
                    for plan_name in selected_plans:
                        if plan_name not in plan_map:
                            continue
                        carrier, plan_key, display, coverage, ded_note = plan_map[plan_name]
                        total = 0; member_rates = []; valid = True
                        for m in st.session_state.quote_members:
                            prem = lookup_premium(carrier, plan_key, m["age"], area_key)
                            if prem is None:
                                valid = False; break
                            total += prem
                            member_rates.append((m["name"], m["age"], prem))
                        if valid:
                            results.append({
                                "plan": display, "carrier": carrier, "total": total,
                                "members": member_rates, "coverage": coverage, "deductible": ded_note
                            })
                    results.sort(key=lambda x: x["total"])
                    st.session_state["quote_results"] = results
                    st.session_state["quote_client"]  = q_name
                    st.session_state["quote_notes"]   = q_notes
                    st.session_state["quote_area"]    = q_area
                    st.rerun()

            if st.session_state.get("quote_results"):
                results   = st.session_state["quote_results"]
                client    = st.session_state.get("quote_client", "Client")
                area_disp = st.session_state.get("quote_area", "Area 1")
                members   = st.session_state.get("quote_members", [])
                st.markdown("---")
                st.markdown(f"### 📋 Quote Comparison — {client or 'Client'}")
                st.caption(f"{area_disp} · {len(members)} member(s) · 2025 rates")
                cheapest = results[0]["total"]
                for i, r in enumerate(results):
                    diff     = r["total"] - cheapest
                    badge    = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
                    diff_str = f"+€{diff:,.0f}/yr" if diff > 0 else "✅ Lowest"
                    color    = "#EDFBF0" if i == 0 else "white"
                    st.markdown(f"""<div style="background:{color};border:1px solid #E8E0D5;
                        border-radius:12px;padding:16px 20px;margin-bottom:10px">
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <div><span style="font-size:18px">{badge}</span>
                            <strong style="font-size:16px;margin-left:8px">{r["plan"]}</strong>
                            <span style="font-size:12px;color:#6B7280;margin-left:10px">{r["deductible"]}</span></div>
                            <div style="text-align:right">
                            <div style="font-size:22px;font-weight:800;color:#1C1410">€{r["total"]:,.0f}/yr</div>
                            <div style="font-size:12px;color:#6B7280">{diff_str}</div></div>
                        </div>
                        <div style="margin-top:10px;font-size:12px;color:#6B7280">
                        {" · ".join(str(m[0]) + ": €" + f"{m[2]:,.0f}" for m in r["members"])}
                        </div></div>""", unsafe_allow_html=True)
                st.divider()
                ec1, ec2 = st.columns(2)
                with ec1:
                    members_str = ", ".join(str(m["name"]) + " (" + str(m["age"]) + "y)" for m in members)
                    lines = [
                        "ASHLAR INSURANCE — Quote Comparison",
                        "Client: " + str(client) + " | " + str(area_disp) + " | " + datetime.now().strftime("%d/%m/%Y"),
                        "Members: " + members_str,
                        "",
                    ]
                    for r in results:
                        lines.append(r["plan"] + ": EUR " + f"{r['total']:,.0f}/year")
                        for m in r["members"]:
                            lines.append("  " + str(m[0]) + " (age " + str(m[1]) + "): EUR " + f"{m[2]:,.0f}")
                        lines.append("")
                    lines.append("Rates: Morgan Price EU 2025 / April LT 2025 / IMG GPMI Apr-2025")
                    st.download_button("📥 Download quote", "\n".join(lines), mime="text/plain", use_container_width=True)
                with ec2:
                    if st.button("💬 Send to HAL for narrative", use_container_width=True):
                        qs    = "\n".join(r["plan"] + ": EUR " + f"{r['total']:,.0f}/yr" for r in results)
                        notes = ("Notes: " + q_notes) if q_notes else ""
                        msg   = ("Quote comparison for " + str(client or "client") + " age " + str(q_age) + ", " + str(area_disp) +
                                 ":\n\n" + qs + "\n\n" + notes +
                                 "\n\nWrite a professional email presenting these options and recommending the best fit.")
                        st.session_state.chat_history.append({"role": "user", "content": msg})
                        st.session_state.active_module = "hal_chat"
                        st.rerun()
                if st.button("🔄 New quote", key="reset_quote"):
                    for k in ["quote_results","quote_client","quote_notes","quote_area","quote_members"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()

    # ══ TAB 2: FULL PDF ENGINE (chi_quote_engine) ══════════════════════════
    with tab_pdf:
        try:
            from config       import BROKER_DEFAULTS, INTER_FILE_DELAY
            from extraction   import compute_score, extract_insurance_data
            from analysis     import generate_recommendation_analysis
            from pptx_builder import generate_pptx
            _QE_LOADED = True
        except ImportError as _qe_err:
            _QE_LOADED = False
            st.error("Quote Engine modules not found: " + str(_qe_err))
            st.info("Add `config.py`, `extraction.py`, `analysis.py`, `pptx_builder.py` to the HAL repo (same folder as `app.py`).")

        try:
            from greek_insurers import detect_comparison_mode, is_greek_insurer, localize_insurance_data
            _GREEK_OK = True
        except ImportError:
            _GREEK_OK = False

        if not _QE_LOADED:
            pass
        else:
            import time as _time
            import hashlib as _hl

            api_key = get_api_key()

            # ── SETTINGS ─────────────────────────────────────────────────────
            st.markdown("### ⚙️ Ρυθμίσεις Παρουσίασης")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown("**👤 Μεσίτης**")
                broker_name  = st.text_input("Όνομα",    value=BROKER_DEFAULTS["name"],  key="qe_broker_name")
                broker_tel   = st.text_input("Τηλέφωνο", value=BROKER_DEFAULTS["tel"],   key="qe_broker_tel")
                broker_email = st.text_input("Email",     value=BROKER_DEFAULTS["email"], key="qe_broker_email")
            with r2:
                st.markdown("**👥 Πελάτης**")
                client_name = st.text_input("Επώνυμο / Όνομα", placeholder="π.χ. Τοτικίδη Κατία", key="qe_client_name")
                n_members   = st.number_input("Αριθμός μελών", 1, 6, 2, key="qe_n_members")
                qe_members  = []
                for i in range(n_members):
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        age = st.number_input(f"Ηλικία #{i+1}", 0, 99, 30 if i==0 else 17, key=f"qe_age_{i}")
                    with mc2:
                        role = st.selectbox("Ρόλος",
                            ["Κύρια Ασφαλισμένη","Κύριος Ασφαλισμένος","Εξαρτώμενο Μέλος","Σύζυγος"],
                            key=f"qe_role_{i}")
                    qe_members.append({"age": age, "role": role})
            with r3:
                st.markdown("**🖼️ Λογότυπο**")
                logo_file  = st.file_uploader("PNG / JPG (προαιρετικό)", type=["png","jpg","jpeg"], key="qe_logo")
                logo_bytes = logo_file.read() if logo_file else None

            st.markdown("---")

            # ── PDF UPLOAD ────────────────────────────────────────────────────
            st.markdown("### 📄 Φόρτωσε τις Ασφαλιστικές Προσφορές (PDF)")
            st.info("Φόρτωσε 2–4 PDF προσφορές. Το Claude εξάγει αυτόματα όλα τα στοιχεία.", icon="ℹ️")
            uploaded_files = st.file_uploader("Επίλεξε PDF αρχεία", type="pdf",
                                               accept_multiple_files=True, key="qe_pdfs")
            if not uploaded_files:
                h1, h2, h3 = st.columns(3)
                with h1: st.markdown("**1️⃣ Ανέβασε PDFs**\nΌλες οι προσφορές που θέλεις να συγκρίνεις")
                with h2: st.markdown("**2️⃣ Claude τα αναλύει**\nΕξάγει κεφάλαια, απαλλαγές, καλύψεις")
                with h3: st.markdown("**3️⃣ Download PPTX**\nΈτοιμη παρουσίαση με το brand σου")
            else:
                if "qe_proposals" not in st.session_state: st.session_state.qe_proposals = {}
                if "qe_pdf_cache" not in st.session_state: st.session_state.qe_pdf_cache = {}

                if st.button("🤖 Ανάλυση με Claude API", type="primary", disabled=not api_key, key="qe_analyse"):
                    if not api_key:
                        st.error("Χρειάζεσαι Claude API key!")
                    else:
                        progress = st.progress(0, text="Αρχικοποίηση...")
                        st.session_state.qe_proposals = {}
                        total = len(uploaded_files)
                        for idx, uf in enumerate(uploaded_files):
                            progress.progress(idx / total, text=f"Ανάλυση {idx+1}/{total}: {uf.name}...")
                            try:
                                pdf_bytes = uf.read()
                                pdf_hash  = _hl.md5(pdf_bytes).hexdigest()
                                if pdf_hash in st.session_state.qe_pdf_cache:
                                    data = st.session_state.qe_pdf_cache[pdf_hash]
                                    st.success(f"⚡ {uf.name} — από cache")
                                else:
                                    data = extract_insurance_data(pdf_bytes, api_key, filename=uf.name)
                                    if _GREEK_OK and is_greek_insurer(data.get("insurer")):
                                        localize_insurance_data(data)
                                    st.session_state.qe_pdf_cache[pdf_hash] = data
                                    st.success(f"✅ {uf.name} → {data.get('insurer','')} {data.get('plan_name','')}")
                                st.session_state.qe_proposals[uf.name] = data
                            except Exception as e:
                                st.error(f"❌ Σφάλμα στο {uf.name}: {e}")
                            if idx < total - 1:
                                _time.sleep(INTER_FILE_DELAY)
                        progress.progress(1.0, text="✅ Ολοκληρώθηκε!")

                if st.session_state.get("qe_proposals"):
                    proposals_list = list(st.session_state.qe_proposals.values())
                    file_names     = list(st.session_state.qe_proposals.keys())

                    if _GREEK_OK:
                        mode = detect_comparison_mode(proposals_list)
                        if mode == "mixed":
                            st.warning(
                                "⚖️ Μεικτή σύγκριση: ελληνικές + διεθνείς εταιρείες. "
                                "Κάποια πεδία (π.χ. πλήρης οδοντιατρική, εξωνοσοκομειακό σε ελεύθερο δίκτυο) "
                                "δεν υπάρχουν καθόλου στην ελληνική αγορά — η σύγκριση δεν είναι 1:1.",
                                icon="⚖️"
                            )
                        elif mode == "greek_only":
                            st.info("🇬🇷 Σύγκριση μόνο ελληνικών εταιρειών — τιμές μεταφράστηκαν αυτόματα.", icon="🇬🇷")

                    st.markdown("---")
                    st.markdown("### 📊 Εξαχθέντα Στοιχεία — Βαθμολογία Κάλυψης")
                    score_cols = st.columns(len(proposals_list))
                    for col, prop in zip(score_cols, proposals_list):
                        sc    = compute_score(prop)
                        emoji = "🟢" if sc >= 7 else ("🟡" if sc >= 5 else "🔴")
                        with col:
                            st.metric(label=f"{prop.get('insurer','?')} — {prop.get('plan_name','?')[:18]}",
                                      value=f"{sc} / 10", delta=f"{emoji} Βαθμολογία Κάλυψης")
                            if prop.get("_risk_flags"):
                                safety = prop.get("_safety_rating", 9.0)
                                s_emoji = "🟢" if safety >= 7 else ("🟡" if safety >= 5 else "🔴")
                                with st.expander(f"{s_emoji} Ασφάλεια όρων: {safety}/10"):
                                    for flag in prop["_risk_flags"]:
                                        st.markdown(f"- {flag}")

                    st.caption("Μπορείς να επεξεργαστείς οποιοδήποτε πεδίο πριν τη δημιουργία.")
                    st.markdown("---")

                    edited_proposals = []
                    prop_tabs = st.tabs([f"📋 {p.get('insurer','?')} — {p.get('plan_name','?')[:20]}"
                                         for p in proposals_list])

                    for ptab, prop, fname in zip(prop_tabs, proposals_list, file_names):
                        with ptab:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown("**📌 Βασικά Στοιχεία**")
                                prop["insurer"]        = st.text_input("Ασφαλιστική",       prop.get("insurer",""),            key=f"ins_{fname}")
                                prop["plan_name"]      = st.text_input("Πλάνο",             prop.get("plan_name",""),          key=f"plan_{fname}")
                                prop["annual_premium"] = st.text_input("Ετήσιο Ασφάλιστρο", str(prop.get("annual_premium","")),key=f"prem_{fname}")
                                cur_val = prop.get("currency","EUR") or "EUR"
                                cur_list = ["EUR","USD","GBP"]
                                prop["currency"]       = st.selectbox("Νόμισμα", cur_list,
                                                            index=cur_list.index(cur_val) if cur_val in cur_list else 0,
                                                            key=f"cur_{fname}")
                                prop["deductible"]     = st.text_input("Απαλλαγή",          prop.get("deductible",""),         key=f"ded_{fname}")
                                prop["max_coverage"]   = st.text_input("Μέγιστο Κεφάλαιο",  str(prop.get("max_coverage","")), key=f"maxcov_{fname}")
                                prop["geography"]      = st.text_input("Γεωγραφία",          prop.get("geography",""),          key=f"geo_{fname}")
                                prop["hospital_class"] = st.text_input("Θέση Νοσηλείας",    prop.get("hospital_class",""),     key=f"hosp_{fname}")
                                prop["waiting_period"] = st.text_input("Αναμονή",            prop.get("waiting_period",""),     key=f"wait_{fname}")
                                prop["preexisting"]    = st.text_input("Προϋπ. Παθήσεις",   prop.get("preexisting",""),        key=f"preex_{fname}")
                            with col2:
                                st.markdown("**✅ Καλύψεις**")
                                prop["inpatient"]               = st.text_input("Νοσηλεία",             prop.get("inpatient",""),               key=f"inp_{fname}")
                                prop["outpatient_limit"]        = st.text_input("Εξωνοσοκ. Όριο",      str(prop.get("outpatient_limit","")),   key=f"outp_{fname}")
                                prop["outpatient_pct"]          = st.text_input("Εξωνοσοκ. %",          str(prop.get("outpatient_pct") or ""),  key=f"outpct_{fname}")
                                prop["mri_ct_pet"]              = st.text_input("MRI / CT / PET",       prop.get("mri_ct_pet",""),              key=f"mri_{fname}")
                                prop["cancer"]                  = st.text_input("Καρκίνος",              prop.get("cancer",""),                  key=f"can_{fname}")
                                prop["physiotherapy"]           = st.text_input("Φυσιοθεραπεία",         prop.get("physiotherapy",""),           key=f"physio_{fname}")
                                prop["chronic_conditions"]      = st.text_input("Χρόνιες Παθήσεις",     prop.get("chronic_conditions",""),      key=f"chron_{fname}")
                                prop["evacuation_repatriation"] = st.text_input("Εκκένωση / Μεταφορά",  prop.get("evacuation_repatriation",""), key=f"evac_{fname}")
                                prop["psychiatric_inpatient"]   = st.text_input("Ψυχ. Νοσηλεία",        prop.get("psychiatric_inpatient",""),   key=f"psyin_{fname}")
                                prop["psychiatric_outpatient"]  = st.text_input("Ψυχ. Εξωτερικά",      prop.get("psychiatric_outpatient",""),  key=f"psyout_{fname}")
                            with col3:
                                st.markdown("**➕ Πρόσθετα & Παρατηρήσεις**")
                                prop["dental_emergency"]   = st.text_input("Οδοντ. Έκτακτη",        prop.get("dental_emergency",""),   key=f"dent_{fname}")
                                prop["wellness_screening"] = st.text_input("Προληπτικός Έλεγχος",    prop.get("wellness_screening",""), key=f"well_{fname}")
                                prop["cancer_screening"]   = st.text_input("Έλεγχος Καρκίνου",       prop.get("cancer_screening",""),   key=f"canscr_{fname}")
                                prop["organ_transplant"]   = st.text_input("Μεταμόσχευση Οργάνου",   prop.get("organ_transplant",""),   key=f"organ_{fname}")
                                prop["hospice_care"]       = st.text_input("Ανακουφιστική Φροντίδα", prop.get("hospice_care",""),       key=f"hosp2_{fname}")
                                prop["home_nursing"]       = st.text_input("Νοσηλεία Κατ' Οίκον",   prop.get("home_nursing",""),       key=f"homenur_{fname}")
                                st.markdown("**💳 Τρόπος Πληρωμής**")
                                freq_options = ["Μηνιαία","Τριμηνιαία","Εξαμηνιαία","Ετήσια"]
                                cur_freq = prop.get("payment_frequency") or "Ετήσια"
                                if cur_freq not in freq_options: cur_freq = "Ετήσια"
                                prop["payment_frequency"] = st.selectbox("Συχνότητα πληρωμής", freq_options,
                                    index=freq_options.index(cur_freq), key=f"freq_{fname}")
                                st.markdown("**📝 Παρατηρήσεις**")
                                notes_raw  = prop.get("key_notes") or []
                                notes_str  = "\n".join(notes_raw) if isinstance(notes_raw, list) else str(notes_raw)
                                edited_notes = st.text_area("Μία παρατήρηση ανά γραμμή", notes_str,
                                    height=120, key=f"notes_{fname}")
                                prop["key_notes"] = [n.strip() for n in edited_notes.splitlines() if n.strip()]
                            edited_proposals.append(prop)

                    # ── RECOMMENDED ───────────────────────────────────────────────
                    st.markdown("---")
                    st.markdown("### 🎯 Επιλογή Πρότασης")
                    insurer_labels = [
                        p.get("insurer","") + " — " + p.get("plan_name","") + " (" + p.get("currency","€") + str(p.get("annual_premium","—")) + ")"
                        for p in edited_proposals
                    ]
                    rec_idx = st.selectbox("Ποια πρόταση ως **ΠΡΟΤΕΙΝΟΜΕΝΗ**;",
                        range(len(insurer_labels)), format_func=lambda i: insurer_labels[i], key="qe_rec_idx")

                    # ── AI ANALYSIS ───────────────────────────────────────────────
                    st.markdown("---")
                    st.markdown("### 🧠 Ανάλυση & Αιτιολόγηση Πρότασης")
                    st.info("Το Claude αναλύει τις προσφορές και παράγει εξατομικευμένη αιτιολόγηση.", icon="💡")

                    if "qe_analysis" not in st.session_state:
                        st.session_state.qe_analysis = None

                    if st.button("🔍 Δημιούργησε Ανάλυση", type="secondary",
                                 disabled=not api_key, key="qe_gen_analysis"):
                        if not client_name:
                            st.warning("Συμπλήρωσε το όνομα του πελάτη!")
                        else:
                            with st.spinner("Δημιουργία ανάλυσης με Claude..."):
                                try:
                                    st.session_state.qe_analysis = generate_recommendation_analysis(
                                        proposals=edited_proposals, recommended_idx=rec_idx,
                                        client_name=client_name, client_members=qe_members, api_key=api_key,
                                    )
                                    st.success("✅ Ανάλυση ολοκληρώθηκε!")
                                except Exception as e:
                                    st.error(f"❌ Σφάλμα: {e}")

                    analysis = st.session_state.get("qe_analysis")
                    if analysis:
                        st.markdown(
                            "<div style='background:#1C3F5E;border-radius:10px;padding:1.2em 1.6em;margin-bottom:1em'>"
                            "<p style='color:#F59E0B;font-size:1.2em;font-weight:700;margin:0'>"
                            + analysis.get("headline","") + "</p></div>",
                            unsafe_allow_html=True
                        )
                        st.markdown("#### 📝 Αιτιολόγηση")
                        st.markdown(analysis.get("main_rationale",""))
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("#### ✅ Βασικοί Λόγοι")
                            for reason in analysis.get("key_reasons",[]): st.markdown(f"- {reason}")
                            st.markdown("#### 🎯 Κριτήρια")
                            for factor in analysis.get("decision_factors",[]): st.markdown(f"- {factor}")
                        with col_b:
                            st.markdown("#### 📊 Αξιολόγηση")
                            tag_colors = {"ΑΡΙΣΤΟ":"#27AE60","ΚΑΛΟ":"#00B4D8","ΜΕΣΑΙΟ":"#E67E22","ΠΕΡΙΟΡΙΣΜΕΝΟ":"#E74C3C"}
                            for v in analysis.get("plan_verdicts",[]):
                                color = tag_colors.get(v.get("tag",""),"#666")
                                st.markdown(
                                    "<div style='border-left:4px solid " + color + ";background:#F4F9FF;"
                                    "border-radius:4px;padding:0.6em 1em;margin-bottom:0.5em'>"
                                    "<strong>" + v.get("insurer","") + " — " + v.get("plan","") + "</strong>"
                                    "<span style='background:" + color + ";color:white;border-radius:4px;"
                                    "padding:2px 8px;font-size:0.75em;margin-left:8px'>" + v.get("tag","") + "</span><br/>"
                                    "<span style='color:#444;font-size:0.9em'>" + v.get("verdict","") + "</span></div>",
                                    unsafe_allow_html=True
                                )
                            if analysis.get("key_concerns"):
                                st.markdown("#### ⚠️ Σημεία Προσοχής")
                                for c in analysis.get("key_concerns",[]): st.markdown(f"- {c}")

                    # ── GENERATE PPTX ─────────────────────────────────────────────
                    st.markdown("---")
                    try:
                        from themes import list_themes
                        _theme_opts = list_themes()
                    except ImportError:
                        _theme_opts = [("ocean", {"name": "Ocean Blue", "emoji": "🌊"})]
                    qe_theme = st.selectbox(
                        "🎨 Θέμα παρουσίασης",
                        options=[k for k, _ in _theme_opts],
                        format_func=lambda k: next(
                            (f"{t['emoji']} {t['name']}" for tk, t in _theme_opts if tk == k), k
                        ),
                        key="qe_theme",
                    )
                    if st.button("🎨 Δημιουργία Παρουσίασης PPTX", type="primary", key="qe_gen_pptx"):
                        if not client_name:
                            st.warning("Συμπλήρωσε το όνομα του πελάτη!")
                        else:
                            with st.spinner("Δημιουργία παρουσίασης..."):
                                try:
                                    pptx_bytes = generate_pptx(
                                        client_name=client_name, client_members=qe_members,
                                        proposals=edited_proposals, recommended_idx=rec_idx,
                                        broker_name=broker_name, broker_tel=broker_tel,
                                        broker_email=broker_email, logo_bytes=logo_bytes,
                                        analysis=st.session_state.get("qe_analysis"),
                                        theme=qe_theme,
                                    )
                                    fname_out = client_name.replace(" ","_") + "_Insurance_" + datetime.now().strftime("%Y%m") + ".pptx"
                                    st.download_button(
                                        label="⬇️ Download Παρουσίαση", data=pptx_bytes,
                                        file_name=fname_out,
                                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                    )
                                    st.success("✅ '" + fname_out + "' είναι έτοιμη!")
                                except Exception as e:
                                    import traceback
                                    st.error("Σφάλμα: " + str(e))
                                    st.code(traceback.format_exc())

                elif uploaded_files and not st.session_state.get("qe_proposals"):
                    st.info("👆 Πάτα 'Ανάλυση με Claude API' για να εξαχθούν τα στοιχεία από τα PDFs.")

    # ══ TAB 3: TERMS ANALYZER (chi-quote-demo-app) ══════════════════════════
    with tab_terms:
        try:
            from terms_analyzer import analyze_terms_pdf
            _TERMS_LOADED = True
        except ImportError as _ta_err:
            _TERMS_LOADED = False
            st.error("terms_analyzer module not found: " + str(_ta_err))

        try:
            from language_profiles import detect_pdf_language
            _LANG_OK = True
        except ImportError:
            _LANG_OK = False

        if _TERMS_LOADED:
            st.caption(
                "Ανέβασε το πλήρες Terms & Conditions PDF μιας ασφαλιστικής (όχι την προσφορά) — "
                "σκανάρει για κρυφές εξαιρέσεις, όρια και αμφίσημες ρήτρες."
            )
            api_key_terms = get_api_key()
            ta_c1, ta_c2 = st.columns([2, 1])
            with ta_c1:
                terms_file = st.file_uploader(
                    "Terms / Wording PDF", type="pdf", key="ta_pdf"
                )
            with ta_c2:
                terms_insurer = st.text_input("Ασφαλιστική", placeholder="π.χ. Generali", key="ta_insurer")
                _detected_lang_idx = 0
                if _LANG_OK and terms_file is not None:
                    try:
                        import fitz as _fitz_peek
                        _peek_bytes = terms_file.getvalue()
                        _peek_doc = _fitz_peek.open(stream=_peek_bytes, filetype="pdf")
                        _peek_text = "".join(p.get_text() for p in _peek_doc[:2])
                        _peek_doc.close()
                        _detected_lang_idx = 0 if detect_pdf_language(_peek_text) == "el" else 1
                    except Exception:
                        pass  # auto-detect is a convenience only — selectbox below still works manually
                terms_lang = st.selectbox(
                    "Γλώσσα ανάλυσης", ["el", "en"], index=_detected_lang_idx, key="ta_lang"
                )

            if st.button("🔍 Ανάλυση Όρων", type="primary",
                         disabled=not (terms_file and api_key_terms), key="ta_run"):
                with st.spinner("Σκανάρισμα όρων για εξαιρέσεις..."):
                    try:
                        result = analyze_terms_pdf(
                            terms_file.getvalue(),
                            insurer=terms_insurer or terms_file.name,
                            api_key=api_key_terms,
                            lang=terms_lang,
                            filename=terms_file.name,
                        )
                        st.session_state["ta_result"] = result
                    except Exception as e:
                        import traceback
                        st.error("Σφάλμα ανάλυσης: " + str(e))
                        st.code(traceback.format_exc())

            ta_result = st.session_state.get("ta_result")
            if ta_result:
                st.markdown("---")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Σελίδες σκαναρισμένες", ta_result.get("pages_scanned", 0))
                rc2.metric("🔴 Κρίσιμες εξαιρέσεις", ta_result.get("critical_count", 0))
                rc3.metric("🟠 Σημαντικές εξαιρέσεις", ta_result.get("high_count", 0))

                if ta_result.get("summary_flags"):
                    st.markdown("#### Σύνοψη")
                    for flag in ta_result["summary_flags"]:
                        st.markdown(f"- {flag}")

                if ta_result.get("exclusions"):
                    st.markdown("#### 📋 Όλα τα ευρήματα")
                    _sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}
                    _cat_label = {
                        "life_support":      "Τεχνητή υποστήριξη ζωής",
                        "dialysis":          "Αιμοκάθαρση",
                        "terminal_care":     "Παρηγορητική φροντίδα",
                        "mental_health":     "Ψυχική υγεία",
                        "pre_existing":      "Προϋπάρχουσες παθήσεις",
                        "waiting_period":    "Περίοδος αναμονής",
                        "benefit_cap":       "Ανώτατο κεφάλαιο παροχής",
                        "general_exclusion": "Γενική εξαίρεση",
                        "other":             "Εξαίρεση",
                    }
                    for exc in ta_result["exclusions"]:
                        emoji = _sev_emoji.get(exc.get("severity", "MEDIUM"), "⚪")
                        label = _cat_label.get(exc.get("category", "other"), exc.get("category", "Εξαίρεση"))
                        with st.expander(f"{emoji} {label}"):
                            st.markdown(exc.get("description", ""))
                            if exc.get("exact_wording"):
                                st.caption(f"« {exc['exact_wording']} »")
                            if exc.get("limit_value"):
                                st.markdown(f"**Όριο:** {exc['limit_value']}")

                if ta_result.get("ambiguous_clauses"):
                    st.markdown("#### ⚠️ Αμφίσημοι όροι")
                    for term in ta_result["ambiguous_clauses"]:
                        st.markdown(f"- {term}")
        else:
            st.info("Πρόσθεσε `terms_analyzer.py` και `exclusions_detector.py` στο HAL repo.")

    # ══ TAB 4: SAVED RESULTS ═══════════════════════════════════════════════
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
        source_files = st.file_uploader("Upload contract / policy / data source", type=["pdf","docx"], accept_multiple_files=True, key="source_upload")
    lang = st.radio("Language output", ["Greek (Ελληνικά)", "English"], horizontal=True)
    if st.button("⚡ Fill Form Automatically", type="primary", disabled=not form_file):
        st.info("Form filler ready. Point this to your document_filler app.py for full processing.")


def render_comms():
    st.markdown("## ✉️ Communications Centre")
    st.caption("Emails · Appeal letters · Renewal notices · Quotes · Circulars")
    doc_type = st.selectbox("Document type", [
        "Client email (renewal notice)","Client email (new quote follow-up)",
        "Appeal letter (claim denial)","Complaint letter (insurer)",
        "Provider communication","Cold outreach (corporate HR)",
        "Quote cover letter","General email",
    ])
    col1, col2 = st.columns(2)
    with col1:
        client_name  = st.text_input("Client / recipient name")
        insurer_name = st.text_input("Insurer / company name")
        policy_ref   = st.text_input("Policy / claim reference")
    with col2:
        tone     = st.radio("Tone", ["Professional","Firm & assertive","Warm & friendly"], horizontal=True)
        language = st.radio("Language", ["English","Greek"], horizontal=True)
    context = st.text_area("Key details to include", height=100,
        placeholder="e.g. Claim denied for EUR 12,999.97. Client member since 1996...")
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
                    r = client.messages.create(model="claude-sonnet-4-6", max_tokens=1500,
                        messages=[{"role":"user","content":prompt}])
                    st.markdown("---")
                    st.markdown("### Generated Document")
                    st.markdown(r.content[0].text)
                    st.download_button("📥 Download as text", r.content[0].text, file_name="document.txt")
                except Exception as e:
                    st.error(f"Error: {e}")


_DEFAULT_COMMISSION_RATES = {
    "3P Insurance":0.15,"Hellas Direct":0.12,"Groupama":0.18,"Generali":0.18,
    "Ethniki":0.16,"Morgan Price":0.20,"NOW Health":0.20,"Bupa Global":0.20,
    "Safe Pet System":0.15,"AXA":0.17,"Interamerican":0.17,"Eurolife":0.16,
    "NN":0.16,"Allianz":0.17,
}
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
    return {"total_premium":round(total_premium,2),"total_commission":round(total_commission,2),"by_insurer":by_insurer,"policy_count":len(policies)}

def render_commissions():
    st.markdown("## 📈 Commissions Tracker")
    st.caption("Εκτίμηση προμηθειών βάσει ασφαλίστρων · Default rates per insurer")
    tab_calc, tab_rates = st.tabs(["📊 Calculate","⚙️ Rates"])
    with tab_calc:
        if "comm_policies" not in st.session_state: st.session_state.comm_policies=[]
        with st.expander("➕ Add policy"):
            cp1,cp2,cp3=st.columns(3)
            with cp1:
                cp_client=st.text_input("Client",key="cp_client")
                cp_insurer=st.selectbox("Insurer",_PROVIDERS,key="cp_ins")
            with cp2:
                cp_type=st.selectbox("Type",list(_POLICY_TYPES.keys()),format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",key="cp_type")
                cp_prem=st.number_input("Premium (EUR)",min_value=0.0,key="cp_prem")
            with cp3:
                cp_pno=st.text_input("Policy No.",key="cp_pno")
                cp_rate=st.number_input("Override rate (%)",min_value=0.0,max_value=50.0,value=float(_DEFAULT_COMMISSION_RATES.get(st.session_state.get("cp_ins",""),0.15)*100),key="cp_rate",format="%.1f")
            if st.button("Add ✓",key="add_comm_pol"):
                st.session_state.comm_policies.append({"client_name":cp_client,"insurer":cp_insurer,"policy_category":cp_type,"premium":cp_prem,"policy_number":cp_pno,"rate_override":cp_rate/100}); st.rerun()
        if st.session_state.comm_policies:
            rpt=_commission_report(st.session_state.comm_policies)
            s1,s2,s3,s4=st.columns(4)
            s1.metric("Policies",rpt["policy_count"]); s2.metric("Total Premium",f"€{rpt['total_premium']:,.2f}")
            s3.metric("Est. Commission",f"€{rpt['total_commission']:,.2f}")
            s4.metric("Avg Rate",f"{round(rpt['total_commission']/rpt['total_premium']*100,1) if rpt['total_premium'] else 0}%")
            for ins,data in sorted(rpt["by_insurer"].items(),key=lambda x:x[1]["commission"],reverse=True):
                ci1,ci2,ci3,ci4=st.columns([2,1,1,1])
                ci1.markdown(f"**{ins}**"); ci2.markdown(f"€{data['premium']:,.0f}"); ci3.markdown(f"**€{data['commission']:,.0f}**"); ci4.markdown(f"{data['count']} policies")
            lines=["Client,Insurer,Type,Premium,Commission,Policy No"]
            for p in st.session_state.comm_policies:
                comm=_calculate_commission(float(p.get("premium",0)),p.get("insurer",""),p.get("rate_override"))
                lines.append(f"{p.get('client_name','')},{p.get('insurer','')},{p.get('policy_category','')},{p.get('premium',0)},{comm},{p.get('policy_number','')}")
            st.download_button("Export CSV","\n".join(lines),file_name="commissions.csv",mime="text/csv")
    with tab_rates:
        for ins,rate in sorted(_DEFAULT_COMMISSION_RATES.items()):
            r1,r2=st.columns([3,1]); r1.markdown(ins); r2.markdown(f"**{rate*100:.0f}%**")


def render_market():
    st.markdown("## 🔍 Market Intelligence")
    st.caption("Niche analysis · Competitor mapping · Expansion strategy")
    query=st.text_area("Research brief",height=80,placeholder="e.g. What are underserved segments in international health insurance for Greeks living abroad?")
    col1,col2=st.columns(2)
    with col1: market=st.multiselect("Markets",["Greece","Cyprus","UK","UAE","Germany","International"],default=["Greece"])
    with col2: product=st.multiselect("Products",["International Health","Greek Domestic Health","Life","Pet","Expat"],default=["International Health"])
    if st.button("🔬 Analyse Market",type="primary"):
        if not get_api_key() or not query: st.warning("Add API key and enter a brief.")
        else:
            with st.spinner("Researching..."):
                import anthropic
                prompt=f"""You are a specialist insurance market analyst for Ashlar Insurance, Athens.\nResearch brief: {query}\nMarkets: {', '.join(market)}\nProducts: {', '.join(product)}\nProvide: 1. Key niche opportunities 2. Underserved segments 3. Competitive landscape 4. Next steps 5. Specific products/carriers. Be concrete and actionable."""
                try:
                    client=anthropic.Anthropic(api_key=get_api_key())
                    r=client.messages.create(model="claude-sonnet-4-6",max_tokens=2000,messages=[{"role":"user","content":prompt}])
                    st.markdown("### Analysis"); st.markdown(r.content[0].text)
                except Exception as e: st.error(f"Error: {e}")


def render_lodge():
    st.markdown("## 🏛️ Lodge Secretary")
    st.caption("Στ∴ ΑΚΡΟΠΟΛΙΣ 84 · Correspondence, circulars, notices")
    doc_type=st.selectbox("Document type",["Circular — general notice","Invitation — session with lecture","Invitation — charitable event","Follow-up — payment / RSVP","Email to Grand Secretariat","Letter for correction / clarification","Internal announcement"])
    addressee=st.text_input("Addressed to",placeholder="Φίλτ∴ Αδ∴ — or Grand Secretary title...")
    subject=st.text_input("Subject / occasion",placeholder="e.g. Τακτική Συνεδρία, Φιλανθρωπική Εκδήλωση...")
    body=st.text_area("Key points to include",height=120,placeholder="e.g. Meeting on Wednesday at 8pm, lecture by Κραττ∴ Αδ∴ Λεφάκης...")
    if st.button("📝 Draft Document",type="primary"):
        if not get_api_key(): st.error("API key missing.")
        else:
            with st.spinner("Drafting in Masonic style..."):
                import anthropic
                prompt=f"""You are the secretary of Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ).\nDraft a {doc_type}:\nAddressed to: {addressee}\nSubject: {subject}\nKey content: {body}\nRules: Contemporary Greek Tektonic, ∴ notation, closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος / 6975900189\nFrom: st.akropolis.84@gmail.com"""
                try:
                    client=anthropic.Anthropic(api_key=get_api_key())
                    r=client.messages.create(model="claude-sonnet-4-6",max_tokens=1200,messages=[{"role":"user","content":prompt}])
                    st.markdown("---"); st.markdown("### Draft"); st.markdown(r.content[0].text)
                    st.download_button("📥 Download",r.content[0].text,file_name="lodge_document.txt")
                except Exception as e: st.error(f"Error: {e}")


def render_finance():
    st.markdown("## 💰 Financial Planner")
    st.caption("Personal finance · Savings · Retirement modelling")
    tab1,tab2=st.tabs(["📊 Retirement Modeller","💬 Financial Adviser Chat"])
    with tab1:
        col1,col2=st.columns(2)
        with col1:
            current_age=st.number_input("Current age",20,80,50)
            retirement_age=st.number_input("Target retirement age",50,80,65)
            monthly_income=st.number_input("Monthly net income (€)",0,50000,3000)
            monthly_save=st.number_input("Monthly savings (€)",0,20000,500)
        with col2:
            current_savings=st.number_input("Current savings (€)",0,1000000,10000)
            annual_return=st.slider("Expected annual return (%)",1.0,12.0,5.0,0.5)
            inflation=st.slider("Inflation estimate (%)",1.0,8.0,3.0,0.5)
            target_pension=st.number_input("Target monthly pension (€)",0,20000,2000)
        if st.button("📈 Model My Retirement",type="primary"):
            years=retirement_age-current_age
            if years>0:
                r=annual_return/100; months=years*12
                fv_savings=current_savings*(1+r)**years
                monthly_r=r/12
                fv_contributions=monthly_save*(((1+monthly_r)**months-1)/monthly_r)
                total_pot=fv_savings+fv_contributions
                monthly_drawdown=total_pot*0.04/12
                gap=target_pension-monthly_drawdown
                st.divider()
                col_a,col_b,col_c=st.columns(3)
                col_a.metric("Projected Pot",f"€{total_pot:,.0f}")
                col_b.metric("Sustainable Monthly Income",f"€{monthly_drawdown:,.0f}/mo")
                col_c.metric("Gap vs Target",f"€{abs(gap):,.0f}/mo",delta=f"{'Surplus' if gap<0 else 'Shortfall'}")
                if gap>0:
                    extra_needed=gap*12/(((1+monthly_r)**months-1)/monthly_r)
                    st.warning(f"Increase monthly savings by **€{extra_needed:,.0f}** to **€{monthly_save+extra_needed:,.0f}/month**.")
                else:
                    st.success(f"On track for retirement at {retirement_age}. Surplus €{abs(gap):,.0f}/month.")
    with tab2:
        fin_query=st.text_area("Ask your financial adviser",placeholder="How much should I save for retirement?...")
        if st.button("Ask HAL",key="fin_ask",type="primary"):
            if not get_api_key():
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not fin_query:
                st.warning("Type a question first.")
            else:
                import anthropic
                with st.spinner("Thinking..."):
                    try:
                        client=anthropic.Anthropic(api_key=get_api_key())
                        r=client.messages.create(model="claude-sonnet-4-6",max_tokens=1000,
                            system="You are a personal financial adviser for Christos Iatropoulos, a self-employed insurance broker in Greece. Provide practical, Greece-specific financial guidance.",
                            messages=[{"role":"user","content":fin_query}])
                        st.markdown(r.content[0].text)
                    except Exception as e:
                        st.error(f"Error: {e}")


def render_health():
    st.markdown("## 💪 Health & Gym Coach")
    st.caption("Personal trainer · Nutritionist · Health monitor")
    tab1,tab2=st.tabs(["🏋️ Workout Plan","💬 Health Chat"])
    with tab1:
        col1,col2=st.columns(2)
        with col1:
            goal=st.selectbox("Goal",["Strength & muscle","Weight loss","Cardiovascular fitness","Flexibility & recovery","General fitness"])
            sessions=st.slider("Sessions per week",2,7,4)
            duration=st.slider("Session duration (mins)",30,90,60)
        with col2:
            equipment=st.multiselect("Equipment available",["Full gym","Dumbbells","Barbell & rack","Resistance bands","Bodyweight only","Cardio machines"])
            level=st.radio("Level",["Beginner","Intermediate","Advanced"])
        notes=st.text_input("Any injuries or limitations?")
        if st.button("🏗️ Generate Programme",type="primary"):
            if not get_api_key():
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            else:
                with st.spinner("Building your programme..."):
                    import anthropic
                    prompt=f"""Design a {sessions}-day per week workout programme.\nGoal: {goal} | Level: {level} | Session: {duration} mins\nEquipment: {', '.join(equipment) if equipment else 'bodyweight'}\nLimitations: {notes or 'none'}\nProvide a full weekly plan with exercises, sets, reps, and rest periods. Include warm-up and cool-down. Make it progressive over 4 weeks."""
                    try:
                        client=anthropic.Anthropic(api_key=get_api_key())
                        r=client.messages.create(model="claude-sonnet-4-6",max_tokens=1500,messages=[{"role":"user","content":prompt}])
                        st.markdown(r.content[0].text)
                    except Exception as e:
                        st.error(f"Error: {e}")
    with tab2:
        health_q=st.text_area("Ask your health coach or nurse",placeholder="I have lower back pain — what exercises should I avoid?...")
        if st.button("Ask HAL",key="health_ask",type="primary"):
            if not get_api_key():
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not health_q:
                st.warning("Type a question first.")
            else:
                import anthropic
                with st.spinner("..."):
                    try:
                        client=anthropic.Anthropic(api_key=get_api_key())
                        r=client.messages.create(model="claude-sonnet-4-6",max_tokens=800,
                            system="You are a personal health coach and wellness adviser. Always recommend professional medical consultation for medical conditions.",
                            messages=[{"role":"user","content":health_q}])
                        st.markdown(r.content[0].text)
                    except Exception as e:
                        st.error(f"Error: {e}")


def render_apps():
    st.markdown("## 🏗️ App Builder")
    st.caption("Describe what you need · HAL writes it · Deploy to Streamlit or Netlify")
    app_type=st.selectbox("App type",["Streamlit app (Python)","Netlify static site (HTML/CSS/JS)","Python script","PDF generator (ReportLab)","PowerPoint generator (python-pptx)","API integration"])
    description=st.text_area("Describe what the app should do",height=120,placeholder="e.g. A Streamlit app that takes a client name, age, and selected insurers, then generates a comparison PDF...")
    if st.button("⚡ Generate Code",type="primary"):
        if not get_api_key():
            st.error("Add Claude_API_Key to Streamlit secrets first.")
        elif not description:
            st.warning("Describe the app first.")
        else:
            with st.spinner("HAL is coding..."):
                import anthropic
                prompt=f"""Build a complete, working {app_type}:\n{description}\nRequirements: Production-ready, all imports, Greek font support for PDFs, read API key from st.secrets. Output only the code."""
                try:
                    client=anthropic.Anthropic(api_key=get_api_key())
                    r=client.messages.create(model="claude-sonnet-4-6",max_tokens=3000,messages=[{"role":"user","content":prompt}])
                    st.code(r.content[0].text,language="python")
                    st.download_button("📥 Download code",r.content[0].text,file_name="hal_generated_app.py")
                except Exception as e:
                    st.error(f"Error: {e}")


def render_pets():
    st.markdown("## 🐾 PetsHealth")
    st.caption("petshealth.gr · Pet insurance tools · Client communications")
    tab1,tab2=st.tabs(["📢 Marketing","💬 Pet Insurance Adviser"])
    with tab1:
        platform=st.selectbox("Platform",["LinkedIn post","Instagram caption","Email newsletter","Website copy"])
        topic=st.text_input("Topic / angle",placeholder="e.g. Why pet insurance in Greece is broken and what we're doing about it")
        if st.button("Generate Content",type="primary"):
            if not get_api_key():
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not topic:
                st.warning("Enter a topic / angle first.")
            else:
                import anthropic
                with st.spinner("..."):
                    try:
                        client=anthropic.Anthropic(api_key=get_api_key())
                        r=client.messages.create(model="claude-sonnet-4-6",max_tokens=600,
                            system="You write marketing content for petshealth.gr, a pet insurance broker in Greece. Tone: confident, warm, independent. Mention Kira Pet (kiraaipet.streamlit.app) when relevant.",
                            messages=[{"role":"user","content":f"Write a {platform} about: {topic}"}])
                        st.markdown(r.content[0].text)
                    except Exception as e:
                        st.error(f"Error: {e}")
    with tab2:
        q=st.text_area("Pet insurance question",placeholder="What's the best pet insurance for a 3-year-old Labrador in Greece?...")
        if st.button("Ask HAL",key="pet_ask",type="primary"):
            if not get_api_key():
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not q:
                st.warning("Type a question first.")
            else:
                import anthropic
                with st.spinner("..."):
                    try:
                        client=anthropic.Anthropic(api_key=get_api_key())
                        r=client.messages.create(model="claude-sonnet-4-6",max_tokens=800,
                            system="You are a pet insurance specialist for petshealth.gr, Greece. Recommend Safe Pet System as the most reliable option. Also know about Kira Pet (kiraaipet.streamlit.app).",
                            messages=[{"role":"user","content":q}])
                        st.markdown(r.content[0].text)
                    except Exception as e:
                        st.error(f"Error: {e}")


def render_clients():
    st.markdown("## 🤝 Client Tracker")
    st.caption("Active cases · Policy status · Renewal dates · Full case history")

    CLIENTS = [
        {
            "name": "Konstantina Alexopoulou", "nickname": "Tzina", "insurer": "Bupa Global",
            "policy": "BI-6000-0113-6189", "claim_ref": "CL260306821932",
            "product": "International Health — Family Policy", "premium": "GBP 66,219/year",
            "member_since": "1996", "status": "🔴 Escalated",
            "summary": (
                "**Facial nerve palsy surgery — Claim EUR 12,999.97**\n\n"
                "Surgery at IASO 04–06/02/2026. Surgeon: Dr. Andreas Foustanos. "
                "Procedure: plastic reconstruction local flap (Code 6093009). "
                "Total: EUR 8,500 surgeon + EUR 4,499.97 IASO.\n\n"
                "**Status:** Formal complaint filed. FSPO (Lincoln House, Dublin 2) — 7-day deadline issued."
            ),
            "next_action": "Chase Bupa for formal complaint response. No resolution within 7 days → refer to FSPO.",
            "contacts": "Dr. Foustanos · IASO hospital · Bupa claims · Roberta (case handler)",
            "documents": "Medical report 31/03/2026 · IASO discharge · Invoice APY BM 0256831 · Payment proofs",
        },
        {
            "name": "Katia Totikidou + Alexia", "nickname": "Katia",
            "insurer": "Generali / Morgan Price / NOW Health", "policy": "—", "claim_ref": "—",
            "product": "Health Insurance Comparison", "premium": "TBC", "member_since": "—",
            "status": "🟡 Pending",
            "summary": (
                "**Health insurance comparison — Katia (54) + Alexia (17)**\n\n"
                "Based in Greece. German citizenship. Priority: hospitalisation + diagnostics abroad. "
                "Personal cancer history. PPT comparison prepared. Awaiting client decision."
            ),
            "next_action": "Follow up with Katia. Send PPT if not done.",
            "contacts": "Katia Totikidou",
            "documents": "PPT comparison (Generali vs Morgan Price Standard vs NOW Health Core)",
        },
        {
            "name": "Christos Iatropoulos (own claim)", "nickname": "Christos",
            "insurer": "Morgan Price", "policy": "M000106069/1",
            "claim_ref": "Morgan Price claim Apr 2026",
            "product": "International Health — Morgan Price", "premium": "—", "member_since": "—",
            "status": "🟡 Pending",
            "summary": (
                "**Morgan Price claim — gastrointestinal investigation (operator's own claim)**\n\n"
                "Condition: Hematochezia (K92.1) + abdominal bloating (K57.30). "
                "Colonoscopy + gastroscopy outpatient 28/04/2026. Dr. Emmanouil, Metropolitan General.\n\n"
                "**Status:** Claim form filled (29/04/2026). Pending upload to Morgan Price."
            ),
            "next_action": "Upload claim documents to Morgan Price portal. Chase Dr. Emmanouil for signature + stamp.",
            "contacts": "Dr. Emmanouil (Metropolitan General) · Morgan Price claims",
            "documents": "Morgan Price claim form · Gastroscopy/colonoscopy report · Physio invoice EUR 200",
        },
        {
            "name": "Pantelis Kourbelas", "nickname": "Pantelis",
            "insurer": "Various", "policy": "—", "claim_ref": "—",
            "product": "Client portal — multi-policy", "premium": "—", "member_since": "—",
            "status": "🔵 Active Client",
            "summary": "**Active client of Ashlar Insurance**\n\nClient portal: panteliskourbelas-chiinsurancebrokers.netlify.app (Netlify, live). Template for white-label client portals.",
            "next_action": "Maintain portal. Check for renewals.",
            "contacts": "Pantelis Kourbelas",
            "documents": "Netlify client portal",
        },
        {
            "name": "Mr. Synodinos", "nickname": "Synodinos",
            "insurer": "Lloyd's (binder)", "policy": "—", "claim_ref": "—",
            "product": "Secure Home Expatriates & Holiday Rental Residences",
            "premium": "TBC", "member_since": "—", "status": "🔵 In Progress",
            "summary": "**Home insurance — Syros holiday rental property**\n\nProperty: Thesi Rozou, Syros. Bay View House / Bay View Studio on Booking.com. Form sent to client. Awaiting signed completed return.",
            "next_action": "Chase Mr. Synodinos for signed completed form.",
            "contacts": "Mr. Synodinos",
            "documents": "Secure Home Expatriates proposal form (draft)",
        },
    ]

    DEFAULT_TICKETS = [
        {"id":"TKT-001","client":"Konstantina Alexopoulou","subject":"Bupa formal complaint — await response","status":"Open","priority":"🔴 High","created":"2026-05-13","updated":"2026-05-13"},
        {"id":"TKT-002","client":"Katia Totikidou","subject":"Send PPT comparison Generali vs Morgan Price","status":"Pending","priority":"🟡 Medium","created":"2026-05-13","updated":"2026-05-13"},
        {"id":"TKT-003","client":"Christos Iatropoulos","subject":"Upload claim docs to Morgan Price portal","status":"Pending","priority":"🟡 Medium","created":"2026-05-13","updated":"2026-05-13"},
        {"id":"TKT-004","client":"Mr. Synodinos","subject":"Chase signed proposal form for Syros property","status":"Open","priority":"🟡 Medium","created":"2026-05-13","updated":"2026-05-13"},
    ]

    if "tickets_loaded_from_sheet" not in st.session_state:
        tickets_ws, log_ws, conv_ws = get_gsheet()
        st.session_state._tickets_ws = tickets_ws
        st.session_state._log_ws     = log_ws
        st.session_state._conv_ws    = conv_ws
        sheet_tickets = load_tickets_from_sheet(tickets_ws)
        if sheet_tickets is not None and len(sheet_tickets) > 0:
            st.session_state.tickets = sheet_tickets
            ids = [int(t["id"].replace("TKT-","")) for t in sheet_tickets if t["id"].startswith("TKT-")]
            st.session_state.next_ticket_id = max(ids) + 1 if ids else 5
        else:
            st.session_state.tickets = DEFAULT_TICKETS
            st.session_state.next_ticket_id = 5
            if tickets_ws:
                for t in DEFAULT_TICKETS:
                    save_ticket_to_sheet(tickets_ws, t)
        st.session_state.tickets_loaded_from_sheet = True

    if "next_ticket_id" not in st.session_state:
        st.session_state.next_ticket_id = 5

    tickets_ws = st.session_state.get("_tickets_ws")
    tab_clients, tab_tickets = st.tabs(["👥 Client Cases","🎫 Task Tickets"])

    with tab_clients:
        col_s, col_f = st.columns([3,1])
        with col_s: search = st.text_input("🔍 Search", placeholder="Name, insurer, policy, status...")
        with col_f: status_filter = st.selectbox("Status",["All","🔴 Escalated","🟡 Pending","🔵 In Progress","🟢"])
        st.divider()
        shown = 0
        for c in CLIENTS:
            if search:
                blob = f"{c['name']} {c['insurer']} {c['policy']} {c['status']} {c['product']}".lower()
                if search.lower() not in blob: continue
            if status_filter != "All" and not c["status"].startswith(status_filter[:2]): continue
            shown += 1
            related = [t for t in st.session_state.tickets if c["name"].split()[0].lower() in t["client"].lower()]
            open_tickets = [t for t in related if t["status"] != "Resolved"]
            ticket_badge = f"  🎫 {len(open_tickets)} open" if open_tickets else ""
            label = f"{c['status'][:2]}  **{c['name']}**  ·  {c['insurer']}  ·  {c['status'][2:].strip()}{ticket_badge}"
            with st.expander(label):
                col1,col2,col3,col4 = st.columns(4)
                col1.markdown(f"**Policy**\n\n{c['policy']}")
                col2.markdown(f"**Product**\n\n{c['product']}")
                col3.markdown(f"**Premium**\n\n{c['premium']}")
                col4.markdown(f"**Member since**\n\n{c['member_since']}")
                st.divider(); st.markdown("#### Case Summary"); st.markdown(c["summary"]); st.divider()
                colA, colB = st.columns(2)
                with colA: st.markdown("**⚡ Next Action**"); st.info(c["next_action"])
                with colB: st.markdown("**📎 Documents**"); st.caption(c["documents"]); st.markdown("**👤 Contacts**"); st.caption(c["contacts"])
                if open_tickets:
                    st.divider(); st.markdown("**🎫 Open Tickets**")
                    for t in open_tickets:
                        tcol1,tcol2,tcol3 = st.columns([1,5,2]); tcol1.code(t["id"]); tcol2.markdown(t["subject"]); tcol3.markdown(t["status"])
                st.divider()
                b1,b2,b3 = st.columns(3)
                with b1:
                    if st.button("✉️ Email",key=f"email_{c['name']}",use_container_width=True):
                        st.session_state.active_module="comms"; st.rerun()
                with b2:
                    if st.button("💬 Ask HAL",key=f"hal_{c['name']}",use_container_width=True):
                        st.session_state.chat_history.append({"role":"user","content":f"Give me a full briefing on the {c['name']} case and what I should do next."})
                        st.session_state.active_module="hal_chat"; st.rerun()
                with b3:
                    if st.button("✅ Mark resolved",key=f"resolve_{c['name']}",use_container_width=True):
                        for client_ in CLIENTS:
                            if client_["name"]==c["name"]: client_["status"]="🟢 Completed"
                        st.rerun()
        if shown==0: st.info("No clients match your search.")

    with tab_tickets:
        st.markdown("### 🎫 Task Tickets")
        all_t=st.session_state.tickets
        n_open=sum(1 for t in all_t if t["status"]=="Open"); n_pend=sum(1 for t in all_t if t["status"]=="Pending"); n_done=sum(1 for t in all_t if t["status"]=="Resolved")
        mc1,mc2,mc3,mc4=st.columns(4)
        mc1.metric("Total tickets",len(all_t)); mc2.metric("🔴 Open",n_open); mc3.metric("🟡 Pending",n_pend); mc4.metric("🟢 Resolved",n_done)
        st.divider()
        for i,t in enumerate(st.session_state.tickets):
            status_icon={"Open":"🔴","Pending":"🟡","Resolved":"🟢"}.get(t["status"],"⚪")
            rc1,rc2,rc3,rc4,rc5=st.columns([1,2,4,1.5,1.5])
            rc1.code(t["id"]); rc2.markdown(f"**{t['client']}**"); rc3.markdown(t["subject"]); rc4.markdown(f"{status_icon} {t['status']}"); rc5.markdown(t["priority"])
            st.markdown("---")


def render_kira_nurse():
    st.markdown("## 🩺 Kira · AI Nurse")
    st.caption("kiraainurse.streamlit.app · AI health assistant for clients & staff")
    col1,col2=st.columns(2)
    with col1:
        st.markdown("""<div style="background:linear-gradient(135deg,#2D3FE7,#7B2FE0);border-radius:14px;padding:24px;color:white;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">🩺</div><div style="font-size:18px;font-weight:700">Kira AI Nurse</div><div style="font-size:13px;opacity:.85;margin:8px 0">Symptom triage · Vitals · Clinical report · PubMed evidence</div></div>""",unsafe_allow_html=True)
        st.link_button("🚀 Open Kira","https://kiraainurse.streamlit.app",use_container_width=True,type="primary")
    with col2:
        st.markdown("""<div style="background:linear-gradient(135deg,#0EA5E9,#2D3FE7);border-radius:14px;padding:24px;color:white;margin-bottom:16px"><div style="font-size:32px;margin-bottom:8px">📷</div><div style="font-size:18px;font-weight:700">Kira Face Scan</div><div style="font-size:13px;opacity:.85;margin:8px 0">rPPG · Heart rate · Breathing · 60-second scan</div></div>""",unsafe_allow_html=True)
        st.link_button("📷 Open Face Scan","https://kiraainurse.netlify.app",use_container_width=True)
    st.divider()
    tab_share,tab_explain,tab_about=st.tabs(["📤 Share with Client","💬 Explain to Client","ℹ️ About"])
    with tab_share:
        c_name=st.text_input("Client name",placeholder="Katia Totikidou")
        c_lang=st.radio("Language",["Greek","English"],horizontal=True)
        if st.button("✍️ Generate message",type="primary"):
            api_key=get_api_key()
            if not api_key:
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not c_name:
                st.warning("Enter a client name first.")
            else:
                import urllib.request,json as _json
                prompt=(f"Write a short WhatsApp message in {'Greek' if c_lang=='Greek' else 'English'} to {c_name}, a client of Ashlar Insurance. Introduce Kira (https://kiraainurse.streamlit.app), a free AI health assistant. Warm and professional. Under 4 sentences. Include the link.")
                body=_json.dumps({"model":"claude-sonnet-4-6","max_tokens":300,"messages":[{"role":"user","content":prompt}]}).encode()
                req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                try:
                    with urllib.request.urlopen(req,timeout=20) as r: msg=_json.loads(r.read())["content"][0]["text"]
                    st.text_area("Message:",value=msg,height=120)
                    import urllib.parse
                    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" style="background:#25D366;color:white;padding:8px 18px;border-radius:8px;text-decoration:none;font-weight:600">WhatsApp →</a>',unsafe_allow_html=True)
                except Exception as e: st.error(f"Error: {e}")
    with tab_explain:
        st.markdown("**Kira** is a bilingual AI health assistant:\n- Triage · Vitals · Face Scan (rPPG) · Clinical Report · PubMed evidence · RxNorm drug check\n- Use cases: expat clients far from GP, pre-consultation prep, insurance claims documentation")
    with tab_about:
        st.markdown("| Component | Technology |\n|---|---|\n| AI | Claude Sonnet + GPT-4o |\n| Face Scan | rPPG CHROM algorithm |\n| Medical DB | PubMed/NCBI |\n| Drug Check | RxNorm |\n| Deploy | Streamlit Cloud + Netlify |")


def _build_analyzer_prompt(client_data, existing_policies, lang="el"):
    def _pol_line(p):
        parts=[f"- {p.get('type','').title()}: {p.get('provider','')}"]
        if p.get("product"): parts.append(p["product"])
        if p.get("policy_no"): parts.append(f"No.{p['policy_no']}")
        if p.get("premium"): parts.append(f"Premium {p.get('currency','EUR')} {p['premium']}")
        if p.get("renewal_date"): parts.append(f"Expires {p['renewal_date']}")
        if p.get("coverage"): parts.append(f"| Coverage: {p['coverage'][:200]}")
        return " ".join(parts)
    existing_str="\n".join(_pol_line(p) for p in existing_policies) if existing_policies else "No policies on file"
    carriers_info="Available carriers: Motor: 3P/Hellas Direct/Groupama/Generali/Ethniki/AXA. Greek Health: Groupama/Generali/Ethniki/Interamerican/Eurolife. International Health: Morgan Price/Bupa Global/NOW Health. Life: Generali/Ethniki/Interamerican/Eurolife/NN/Allianz. Liability: Groupama/Generali/Ethniki/AXA. Pet: Safe Pet System. Key facts: Greek domestic health=no free outpatient/dental/psychiatric/imaging outside hospitalisation. Professional Liability LEGALLY REQUIRED for architects/engineers/doctors/lawyers. Expats need international health NOT Greek domestic."
    p=client_data
    if lang=="el":
        return f"""Είσαι σύμβουλος ασφαλίσεων Ashlar Insurance. Ανάλυσε τις ασφαλιστικές ανάγκες:\nΠΕΛΑΤΗΣ: {p.get("name")}, {p.get("age")}y, {p.get("profession")}, {p.get("family")}, εισόδημα {p.get("income")}\nΑκίνητο:{"Ναι" if p.get("has_property") else "Όχι"} Όχημα:{"Ναι" if p.get("has_vehicle") else "Όχι"} Κατοικίδιο:{"Ναι" if p.get("has_pets") else "Όχι"} Παιδιά:{"Ναι" if p.get("has_children") else "Όχι"} Expat:{"Ναι" if p.get("is_expat") else "Όχι"}\nΣημειώσεις: {p.get("notes","")}\nΥΠΑΡΧΟΥΣΕΣ ΑΣΦΑΛΙΣΕΙΣ:\n{existing_str}\n{carriers_info}\nΔώσε: ## 🔍 ΑΝΑΛΥΣΗ ΠΡΟΦΙΛ | ## ✅ ΚΑΛΥΨΕΙΣ ΠΟΥ ΕΧΕΙ | ## ⚠️ ΚΕΝΑ ΚΑΛΥΨΕΩΝ (με Επείγον🔴/Προτεινόμενο🟡/Προαιρετικό🟢, ασφαλιστές, εκτιμώμενο ασφάλιστρο) | ## 📋 ΠΛΑΝΟ ΔΡΑΣΗΣ | ## 💬 SCRIPT ΕΠΙΚΟΙΝΩΝΙΑΣ"""
    else:
        return f"""You are an insurance adviser at Ashlar Insurance Greece.\nCLIENT: {p.get("name")}, {p.get("age")}y, {p.get("profession")}, {p.get("family")}, income {p.get("income")}\nProperty:{"Yes" if p.get("has_property") else "No"} Vehicle:{"Yes" if p.get("has_vehicle") else "No"} Pets:{"Yes" if p.get("has_pets") else "No"} Children:{"Yes" if p.get("has_children") else "No"} Expat:{"Yes" if p.get("is_expat") else "No"}\nNotes: {p.get("notes","")}\nEXISTING POLICIES:\n{existing_str}\n{carriers_info}\nProvide: ## 🔍 PROFILE ANALYSIS | ## ✅ EXISTING COVERAGE | ## ⚠️ COVERAGE GAPS (Urgent🔴/Recommended🟡/Optional🟢, carriers, estimated premium) | ## 📋 ACTION PLAN | ## 💬 CLIENT SCRIPT"""


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
                                reader=PdfReader(pdf_file)
                                pdf_text="\n".join(page.extract_text() or "" for page in reader.pages)[:8000]
                            except Exception as e:
                                st.warning(f"Could not read {pdf_file.name}: {e}"); continue
                            if not pdf_text.strip(): st.warning(f"{pdf_file.name}: no text found"); continue
                            extract_prompt=f'Extract insurance policy details. Return ONLY JSON:\n{{"policy_type":"motor/health/life/home/travel/pet/liability/other","insurer":"","policy_number":"","product":"","premium":"","currency":"EUR","expiry_date":"YYYY-MM-DD","coverage_summary":"","key_exclusions":"","deductible":""}}\nPOLICY:\n{pdf_text}'
                            body=_j.dumps({"model":"claude-sonnet-4-6","max_tokens":800,"messages":[{"role":"user","content":extract_prompt}]}).encode()
                            req=_ur.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                            try:
                                with _ur.urlopen(req,timeout=30) as r: result=_j.loads(r.read())["content"][0]["text"].strip()
                                if result.startswith("```"): result=result.split("```")[1]; result=result[4:] if result.startswith("json") else result
                                pd_data=_j.loads(result.strip())
                                extracted.append({"type":pd_data.get("policy_type","other"),"provider":pd_data.get("insurer",""),"policy_no":pd_data.get("policy_number",""),"product":pd_data.get("product",""),"premium":pd_data.get("premium",""),"currency":pd_data.get("currency","EUR"),"renewal_date":pd_data.get("expiry_date",""),"coverage":pd_data.get("coverage_summary",""),"source_file":pdf_file.name})
                                st.success(f"✅ {pdf_file.name} → {pd_data.get('insurer','')} {pd_data.get('product','')}")
                            except Exception as e: st.warning(f"Could not parse {pdf_file.name}: {e}")
                    if extracted:
                        existing_nos={p.get("policy_no","") for p in st.session_state.an_policies}
                        new_ones=[p for p in extracted if p.get("policy_no","") not in existing_nos]
                        st.session_state.an_policies.extend(new_ones)
                        st.success(f"✅ Added {len(new_ones)} policies"); st.rerun()
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
            client_data={"name":a_name,"age":a_age,"profession":a_prof,"family":a_family,"income":a_income,"notes":a_notes,"has_property":a_prop,"has_vehicle":a_vehicle,"has_pets":a_pets,"has_children":a_kids,"is_expat":a_expat}
            prompt=_build_analyzer_prompt(client_data,st.session_state.an_policies,a_lang)
            with st.spinner("Analysing..."):
                body=_j.dumps({"model":"claude-sonnet-4-6","max_tokens":3000,"system":"Είσαι έμπειρος ασφαλιστικός σύμβουλος στην Ελλάδα.","messages":[{"role":"user","content":prompt}]}).encode()
                req=_ur.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                try:
                    with _ur.urlopen(req,timeout=60) as r:
                        result=_j.loads(r.read())["content"][0]["text"]
                    st.session_state["an_result"]=result; st.session_state["an_client"]=a_name
                except Exception as e: st.error(f"Error: {e}")
    if st.session_state.get("an_result"):
        result=st.session_state["an_result"]; cname=st.session_state["an_client"]
        st.markdown("---"); st.markdown(f"### 📊 {cname}"); st.markdown(result)


def render_chi_portal():
    portal_url=st.secrets.get("CHI_PORTAL_URL","https://chi-insurance-portal-production.up.railway.app")
    repo="chiinsurancebrokers/chi-insurance-portal"
    st.markdown("## 🌐 CHI Insurance Portal"); st.caption(portal_url)
    qa1,qa2,qa3=st.columns(3)
    with qa1: st.link_button("🌐 Open Portal",portal_url,use_container_width=True,type="primary")
    with qa2: st.link_button("🔐 Admin Login",f"{portal_url}/login",use_container_width=True)
    with qa3: st.link_button("📂 GitHub",f"https://github.com/{repo}",use_container_width=True)
    st.divider()
    st.markdown(f'<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);border-radius:16px;padding:28px;text-align:center;margin-bottom:20px"><div style="font-size:40px">🛡️</div><div style="font-size:22px;font-weight:800;color:#C9A96E;margin-bottom:6px">CHI Admin Panel</div><div style="font-size:13px;color:#A89880;margin-bottom:20px">138 Clients · 222 Policies · 30 Expiring</div></div>',unsafe_allow_html=True)
    q1,q2,q3,q4=st.columns(4)
    with q1: st.link_button("👥 Clients",f"{portal_url}/clients",use_container_width=True,type="primary")
    with q2: st.link_button("📄 Policies",f"{portal_url}/policies",use_container_width=True,type="primary")
    with q3: st.link_button("💳 Payments",f"{portal_url}/payments",use_container_width=True,type="primary")
    with q4: st.link_button("📧 Renewals",f"{portal_url}/renewals",use_container_width=True)
    st.divider()
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
        st.link_button("🚀 Open Kira Pet","https://kiraaipet.streamlit.app",use_container_width=True,type="primary")
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
            if not api_key:
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            else:
                import urllib.request,json as _json
                prompt=f"Write pet insurance content for petshealth.gr (Greek brand, Ashlar Insurance, carrier: Safe Pet System). Content: {content_type if not custom else custom}. Language: {lang}. Mention Kira Pet (kiraaipet.streamlit.app) when relevant. Professional, warm, genuine."
                body=_json.dumps({"model":"claude-sonnet-4-6","max_tokens":1500,"messages":[{"role":"user","content":prompt}]}).encode()
                req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("Writing..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r: st.markdown(_json.loads(r.read())["content"][0]["text"])
                    except Exception as e: st.error(f"Error: {e}")
    with tab_social:
        platform=st.selectbox("Platform",["LinkedIn","Instagram","Facebook"])
        angle=st.text_input("Topic",placeholder="e.g. Emergency vet bills in Greece")
        if st.button("📱 Generate",type="primary"):
            api_key=get_api_key()
            if not api_key:
                st.error("Add Claude_API_Key to Streamlit secrets first.")
            elif not angle:
                st.warning("Enter a topic first.")
            else:
                import urllib.request,json as _json
                body=_json.dumps({"model":"claude-sonnet-4-6","max_tokens":600,"messages":[{"role":"user","content":f"Write a {platform} post for petshealth.gr about: {angle}. Greek language, English hashtags. Mention Kira Pet (kiraaipet.streamlit.app) if relevant."}]}).encode()
                req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r: st.markdown(_json.loads(r.read())["content"][0]["text"])
                    except Exception as e: st.error(f"Error: {e}")


def render_memory():
    st.markdown("## 🧠 HAL Memory")
    st.caption(f"Persistent business conversations · {MEMORY_WINDOW_DAYS}-day rolling auto-context · Full search across all history")
    if "_conv_ws" not in st.session_state:
        try:
            _,_,_conv_ws=get_gsheet(); st.session_state._conv_ws=_conv_ws
        except Exception: st.session_state._conv_ws=None
    conv_ws=st.session_state.get("_conv_ws")
    if conv_ws is None:
        st.error("⚠️ Google Sheets not connected. Configure `gcp_service_account` and `HAL_SHEET_ID` in Streamlit secrets.")
        return
    tab_search,tab_browse,tab_stats,tab_settings=st.tabs(["🔍 Search","📅 Browse Recent","📊 Stats","⚙️ Settings"])
    with tab_search:
        st.markdown("### Search every conversation HAL has stored")
        q=st.text_input("Search term",placeholder="e.g. Ergo, Bupa, Tzina, colonoscopy, Generali...")
        if q:
            with st.spinner("Searching..."): results=search_conversations(conv_ws,q,limit=50)
            if not results: st.info(f"No matches for '{q}'.")
            else:
                st.success(f"Found {len(results)} matches")
                sessions={}
                for r in results: sessions.setdefault(r["session_id"],[]).append(r)
                for sid,msgs in sessions.items():
                    with st.expander(f"📅 Session {msgs[0]['timestamp'][:10]} — {len(msgs)} match(es)"):
                        for m in msgs:
                            icon="🧑" if m["role"]=="user" else "🤖"
                            st.markdown(f"**{icon} {m['role'].title()}** · `{m['timestamp']}`")
                            content=m["content"]
                            if len(content)>600:
                                idx=content.lower().find(q.lower())
                                content=("..." if idx>200 else "")+content[max(0,idx-200):idx+400]+"..."
                            st.markdown(f"> {content}"); st.divider()
    with tab_browse:
        st.markdown(f"### Last {MEMORY_WINDOW_DAYS} days of business conversations")
        days=st.slider("Days to show",1,30,MEMORY_WINDOW_DAYS,key="browse_days")
        with st.spinner("Loading..."): recent=load_recent_conversations(conv_ws,days=days,mode_filter="business")
        if not recent: st.info(f"No conversations in the last {days} days.")
        else:
            sessions={}
            for r in recent: sessions.setdefault(r["session_id"],[]).append(r)
            session_keys=sorted(sessions.keys(),key=lambda k:sessions[k][0]["timestamp"],reverse=True)
            st.caption(f"{len(recent)} messages across {len(sessions)} session(s)")
            for sid in session_keys:
                msgs=sessions[sid]; first_ts=msgs[0]["timestamp"]
                first_user=next((m for m in msgs if m["role"]=="user"),None)
                preview=(first_user["content"][:80] if first_user else "")
                with st.expander(f"📅 {first_ts} — {len(msgs)} msgs — {preview}..."):
                    for m in msgs:
                        with st.chat_message("user" if m["role"]=="user" else "assistant"):
                            st.caption(m["timestamp"]); st.markdown(m["content"])
            st.divider()
            if st.button("📥 Export visible to text",use_container_width=True):
                lines=[f"HAL Memory Export — {datetime.now().strftime('%Y-%m-%d %H:%M')}",f"Last {days} days · {len(recent)} messages",""]
                for sid in session_keys:
                    lines.append(f"\n=== Session {sid} ===")
                    for m in sessions[sid]:
                        lines.append(f"\n[{m['timestamp']}] {m['role'].upper()}:"); lines.append(m["content"])
                st.download_button("Download .txt","\n".join(lines),file_name=f"hal_memory_{datetime.now().strftime('%Y%m%d')}.txt",mime="text/plain",use_container_width=True)
    with tab_stats:
        st.markdown("### Memory Statistics")
        with st.spinner("Calculating..."):
            try:
                all_rows=conv_ws.get_all_records(); total=len(all_rows)
                sessions_set=set(r.get("SessionID","") for r in all_rows if r.get("SessionID"))
                user_msgs=sum(1 for r in all_rows if r.get("Role")=="user")
                hal_msgs=sum(1 for r in all_rows if r.get("Role")=="assistant")
                from datetime import timedelta
                cutoff=datetime.now()-timedelta(days=MEMORY_WINDOW_DAYS)
                recent_count=sum(1 for r in all_rows if r.get("Timestamp") and datetime.strptime(r["Timestamp"],"%Y-%m-%d %H:%M:%S")>=cutoff)
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Total messages",f"{total:,}"); c2.metric("Total sessions",len(sessions_set))
                c3.metric(f"Last {MEMORY_WINDOW_DAYS}d",recent_count); c4.metric("User : HAL",f"{user_msgs}:{hal_msgs}")
                st.caption(f"🧠 Current session ID: `{st.session_state.session_id}`")
            except Exception as e: st.warning(f"Could not load stats: {e}")
    with tab_settings:
        st.markdown("### Memory Settings")
        st.markdown(f"| Setting | Value |\n|---|---|\n| Rolling window | **{MEMORY_WINDOW_DAYS} days** |\n| Modes saved | **{', '.join(MEMORY_SAVE_MODES)}** |\n| Max injected messages | **{MEMORY_MAX_INJECT}** |\n| Storage | Google Sheets tab `Conversations` |\n| Private/lodge mode | **NEVER stored** |")
        st.divider()
        with st.expander("🗑 Clear current session from memory"):
            if st.button("Reset current session memory",type="secondary"):
                try:
                    cell_list=conv_ws.findall(st.session_state.session_id)
                    rows_to_delete=sorted({c.row for c in cell_list},reverse=True)
                    for row in rows_to_delete: conv_ws.delete_rows(row)
                    st.session_state.chat_history=[]; st.session_state.memory_injected=False
                    st.success(f"Cleared {len(rows_to_delete)} rows."); st.rerun()
                except Exception as e: st.error(f"Could not clear: {e}")


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
    if module == "home":           render_business_home()
    elif module == "hal_chat":     render_hal_chat()
    elif module == "memory":       render_memory()
    elif module == "renewals":     render_renewals()
    elif module == "quotes":       render_quotes()
    elif module == "documents":    render_documents()
    elif module == "comms":        render_comms()
    elif module == "commissions":  render_commissions()
    elif module == "market":       render_market()
    elif module == "clients":      render_clients()
    elif module == "apps":         render_apps()
    elif module == "pets":         render_pets()
    elif module == "kira_nurse":   render_kira_nurse()
    elif module == "chi_analyzer": render_chi_analyzer()
    elif module == "chi_portal":   render_chi_portal()
    elif module == "kira_pet":     render_kira_pet_hal()
    else: render_business_home()

elif mode == "private" and st.session_state.private_unlocked:
    if module == "home":             render_private_home()
    elif module == "hal_chat":       render_hal_chat()
    elif module == "lodge":          render_lodge()
    elif module == "minutes":        render_placeholder("Minutes & Documents", "📋")
    elif module == "attendance":     render_placeholder("Attendance Tracker", "👥")
    elif module == "events":         render_placeholder("Events & Gala", "📅")
    elif module == "finance":        render_finance()
    elif module == "health":         render_health()
    elif module == "settings_private": render_placeholder("Private Settings", "🔑")
    else: render_private_home()
