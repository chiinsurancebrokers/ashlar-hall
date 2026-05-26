"""
HAL — Heuristically Programmed Algorithmic Layer
HAL | Ashlar Insurance
Main Dashboard Entry Point
"""

import streamlit as st
import hashlib
import os
import json
from datetime import datetime

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

Respond in the language of the message. Be direct — produce outputs, not advice about producing them. For emails and letters, write them fully ready to send."""

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

    # Input
    # ── VOICE INPUT (Web Speech API) ─────────────────────────────────────────
    st.markdown("""
<div id="voice-bar" style="display:flex;align-items:center;gap:10px;
     background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);
     border-radius:10px;padding:10px 14px;margin-bottom:10px">
  <button id="mic-btn" onclick="toggleVoice()" title="Voice input"
     style="background:none;border:2px solid #C9A96E;border-radius:50%;
     width:38px;height:38px;font-size:18px;cursor:pointer;color:#C9A96E;
     display:flex;align-items:center;justify-content:center;flex-shrink:0">🎙️</button>
  <div id="voice-status" style="font-size:12px;color:#A89880;flex:1">
    Click 🎙️ to speak · Works in Chrome/Safari
  </div>
  <div id="voice-result" style="font-size:13px;color:#E8DDD0;display:none;
       background:rgba(201,169,110,.1);border-radius:6px;padding:6px 10px;
       flex:2;max-width:400px"></div>
  <button id="voice-send" onclick="sendVoice()" style="display:none;
     background:#C9A96E;color:#1C1410;border:none;border-radius:6px;
     padding:6px 14px;font-weight:700;cursor:pointer;font-size:12px">Send →</button>
</div>
<script>
var recognition;var listening=false;var transcript="";
var voiceInput=document.getElementById("stChatInputTextArea")||null;

function toggleVoice(){
  if(!('webkitSpeechRecognition'in window)&&!('SpeechRecognition'in window)){
    document.getElementById("voice-status").textContent="Speech API not supported in this browser. Use Chrome or Safari.";
    return;
  }
  if(listening){stopVoice();return;}
  recognition=new(window.SpeechRecognition||window.webkitSpeechRecognition)();
  recognition.lang=document.documentElement.lang==="el"?"el-GR":"en-US";
  recognition.interimResults=true; recognition.continuous=false;
  recognition.onstart=function(){
    listening=true;
    document.getElementById("mic-btn").style.background="#C9A96E";
    document.getElementById("mic-btn").style.color="#1C1410";
    document.getElementById("voice-status").textContent="Listening... speak now";
    document.getElementById("voice-result").style.display="none";
    document.getElementById("voice-send").style.display="none";
  };
  recognition.onresult=function(e){
    transcript=Array.from(e.results).map(r=>r[0].transcript).join("");
    var res=document.getElementById("voice-result");
    res.textContent=transcript; res.style.display="block";
  };
  recognition.onend=function(){
    listening=false;
    document.getElementById("mic-btn").style.background="none";
    document.getElementById("mic-btn").style.color="#C9A96E";
    document.getElementById("voice-status").textContent="Click Send to submit or 🎙️ to re-record";
    if(transcript) document.getElementById("voice-send").style.display="block";
  };
  recognition.onerror=function(e){
    document.getElementById("voice-status").textContent="Error: "+e.error+". Try Chrome.";
    listening=false;
  };
  recognition.start();
}

function stopVoice(){if(recognition){recognition.stop();}}

function sendVoice(){
  if(!transcript) return;
  // Find Streamlit chat input and inject text
  var inputs=document.querySelectorAll("textarea");
  for(var i=0;i<inputs.length;i++){
    if(inputs[i].placeholder&&inputs[i].placeholder.toLowerCase().includes("message")){
      var nativeInputValueSetter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
      nativeInputValueSetter.call(inputs[i],transcript);
      inputs[i].dispatchEvent(new Event("input",{bubbles:true}));
      inputs[i].focus();
      // Simulate Enter
      setTimeout(function(){
        var enterEvent=new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true});
        document.querySelector("textarea").dispatchEvent(enterEvent);
      }, 200);
      document.getElementById("voice-result").style.display="none";
      document.getElementById("voice-send").style.display="none";
      document.getElementById("voice-status").textContent="Click 🎙️ to speak · Works in Chrome/Safari";
      transcript="";
      break;
    }
  }
}
</script>
""", unsafe_allow_html=True)

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
    st.caption("Upload insurance PDFs · Claude extracts & ranks · Export comparison")

    tab1, tab2 = st.tabs(["📤 Upload & Analyse", "📋 Results"])

    with tab1:
        insurer_type = st.radio(
            "Insurer type",
            ["Greek domestic", "International", "Mixed comparison"],
            horizontal=True
        )

        uploaded = st.file_uploader(
            "Upload quote PDFs (one per insurer)",
            type=["pdf"],
            accept_multiple_files=True
        )

        client_age = st.number_input("Client age", min_value=0, max_value=100, value=45)
        client_notes = st.text_area("Client notes / priorities", placeholder="e.g. Prioritises hospitalisation, travels to Germany, has diabetic history...")

        if st.button("🚀 Analyse Quotes", type="primary", disabled=not uploaded):
            st.info(f"Ready to analyse {len(uploaded)} quotes. Connect to your Quote Engine repo or use the HAL Assistant tab to process these.")

    with tab2:
        st.info("Analysed quotes will appear here. Upload PDFs in the first tab to begin.")


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


def render_commissions():
    st.markdown("## 📈 Commission Tracker")
    st.caption("Upload monthly statements · HAL extracts figures · Builds your P&L")

    uploaded = st.file_uploader("Upload commission statement (PDF or CSV)", type=["pdf", "csv"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total MTD", "— €")
    col2.metric("vs Last Month", "—")
    col3.metric("YTD", "— €")

    st.divider()
    st.info("📌 Upload your first statement to start tracking. HAL will extract all commission lines, group by insurer, and build a running P&L.")


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

    # ── Session-state backed client list — persists across reruns ───────────
    DEFAULT_CLIENTS = [
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
    if "hal_clients" not in st.session_state:
        st.session_state.hal_clients = DEFAULT_CLIENTS
    CLIENTS = st.session_state.hal_clients

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
                    cur = c["status"]
                    if "Escalated" in cur or "Pending" in cur or "In Progress" in cur:
                        if st.button("✅ Mark resolved", key=f"resolve_{c['name']}", use_container_width=True):
                            for client in st.session_state.hal_clients:
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
                            st.session_state.hal_clients = [x for x in st.session_state.hal_clients if x["name"] != c["name"]]
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
                new_contacts = st.text_input("Contacts (doctor, case handler...)")
                new_docs     = st.text_input("Documents / files")
                if st.form_submit_button("Add client", type="primary"):
                    if new_name:
                        st.session_state.hal_clients.append({
                            "name": new_name, "nickname": new_name.split()[0],
                            "insurer": new_insurer, "policy": new_policy,
                            "claim_ref": "—", "product": new_product,
                            "premium": new_premium, "member_since": new_since,
                            "status": new_status, "summary": new_summary,
                            "next_action": new_action,
                            "contacts": new_contacts or "—",
                            "documents": new_docs or "—",
                        })
                        st.success(f"✅ {new_name} added to client tracker.")
                        st.rerun()
                    else:
                        st.warning("Full name is required.")

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
    """Kira AI Nurse — embedded in HAL business mode."""
    st.markdown("## 🩺 Kira · AI Nurse")
    st.caption("kiraainurse.streamlit.app · AI health assistant for clients & staff")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div style="background:linear-gradient(135deg,#2D3FE7,#7B2FE0);border-radius:14px;padding:24px;color:white;margin-bottom:16px">
            <div style="font-size:32px;margin-bottom:8px">🩺</div>
            <div style="font-size:18px;font-weight:700">Kira AI Nurse</div>
            <div style="font-size:13px;opacity:.85;margin:8px 0">Symptom triage · Vitals · Clinical report · PubMed evidence</div>
        </div>""", unsafe_allow_html=True)
        st.link_button("🚀 Open Kira", "https://kiraainurse.streamlit.app", use_container_width=True)

    with col2:
        st.markdown("""<div style="background:linear-gradient(135deg,#0EA5E9,#2D3FE7);border-radius:14px;padding:24px;color:white;margin-bottom:16px">
            <div style="font-size:32px;margin-bottom:8px">📷</div>
            <div style="font-size:18px;font-weight:700">Kira Face Scan</div>
            <div style="font-size:13px;opacity:.85;margin:8px 0">rPPG · Heart rate · Breathing · HRV · 60-second scan</div>
        </div>""", unsafe_allow_html=True)
        st.link_button("📷 Open Face Scan", "https://kiraainurse.netlify.app", use_container_width=True)

    st.divider()

    tab_share, tab_explain, tab_about = st.tabs([
        "📤 Share with Client",
        "💬 Explain to Client",
        "ℹ️ About Kira",
    ])

    with tab_share:
        st.markdown("### Share Kira with a client")
        st.caption("Generate a personalised message to send a client the Kira link")
        c_name = st.text_input("Client name", placeholder="Katia Totikidou")
        c_lang = st.radio("Message language", ["Greek", "English"], horizontal=True)
        if st.button("✍️ Generate message", type="primary"):
            api_key = st.secrets.get("Claude_API_Key","") or st.secrets.get("ANTHROPIC_API_KEY","")
            if api_key and c_name:
                import urllib.request, json as _json
                prompt = (f"Write a short WhatsApp/SMS message in {'Greek' if c_lang=='Greek' else 'English'} "
                          f"to send to {c_name}, a client of Ashlar Insurance. "
                          f"The message introduces Kira (https://kiraainurse.streamlit.app), a free AI health assistant "
                          f"that can assess symptoms, analyse vitals, and generate a clinical report in Greek. "
                          f"Tone: warm and professional. Keep it under 4 sentences. Include the link.")
                body = _json.dumps({"model":"claude-sonnet-4-6","max_tokens":300,
                                    "messages":[{"role":"user","content":prompt}]}).encode()
                req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                import urllib.error
                try:
                    with urllib.request.urlopen(req, timeout=20) as r:
                        msg = _json.loads(r.read())["content"][0]["text"]
                    st.text_area("Message ready to send:", value=msg, height=120)
                    import urllib.parse
                    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" style="background:#25D366;color:white;padding:8px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px">WhatsApp →</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab_explain:
        st.markdown("### What does Kira do?")
        st.markdown("""
**Kira** is a bilingual (Greek/English) AI health assistant for the Greek market. It:

- **Triage:** Asks targeted questions about symptoms, gives structured assessment
- **Vitals:** Interprets heart rate, blood pressure, SpO2, temperature, HRV
- **Face Scan:** Measures HR and breathing via phone camera (rPPG, 60 seconds)
- **Clinical Report:** Full differential diagnosis with PubMed evidence + GPT-4o second opinion
- **Medications:** RxNorm drug interaction check
- **Export:** PDF report + WhatsApp share

**Use cases for Ashlar clients:**
- Expat clients far from their GP — get a clinical assessment before seeing a doctor abroad
- Pre-consultation prep — arrive at the doctor with a structured symptom report
- Understanding a diagnosis — ask Kira what the doctor told them
- Insurance claims — document symptoms and timeline for a claim
        """)

    with tab_about:
        st.markdown("### Technology")
        st.markdown("""
| Component | Technology |
|---|---|
| AI Engine | Claude Sonnet (Anthropic) + GPT-4o |
| Face Scan | rPPG (CHROM algorithm, de Haan & Jeanne 2013) |
| Medical DB | PubMed / NCBI API |
| Drug Check | RxNorm (NIH) |
| BP Model | GPR model trained on PPG-BP Database |
| Deployment | Streamlit Cloud + Netlify |
| Language | Bilingual Greek/English |

**Source:** github.com/chiinsurancebrokers/kira
        """)


# ── AI ANALYZER CONFIG ───────────────────────────────────────────────────────
"""
CHI Insurance AI Analyzer
Analyzes client needs and proposes insurance coverage gaps.
Integrated into HAL as render_chi_analyzer().
"""

# ── PROFESSION TRIGGERS ────────────────────────────────────────────────────────
PROFESSION_TRIGGERS = {
    "architect":         ["liability","home"],
    "engineer":          ["liability","home"],
    "civil engineer":    ["liability","home"],
    "doctor":            ["liability","health"],
    "lawyer":            ["liability"],
    "accountant":        ["liability"],
    "consultant":        ["liability"],
    "pharmacist":        ["liability"],
    "dentist":           ["liability","health"],
    "psychologist":      ["liability"],
    "real estate":       ["liability","home"],
    "business owner":    ["liability","life","health"],
    "self employed":     ["liability","health","life"],
    "teacher":           ["life","health"],
    "driver":            ["motor","life"],
    "pilot":             ["life","health"],
    "athlete":           ["health","life"],
    "expat":             ["health"],
    "freelancer":        ["liability","health"],
    "contractor":        ["liability","home"],
}

COVERAGE_MATRIX = {
    "motor":     {"label":"Motor Insurance",        "label_el":"Ασφάλεια Οχήματος",   "icon":"🚗", "priority":1},
    "health":    {"label":"Health Insurance",       "label_el":"Ασφάλεια Υγείας",     "icon":"❤️", "priority":1},
    "life":      {"label":"Life Insurance",         "label_el":"Ασφάλεια Ζωής",       "icon":"🫀", "priority":2},
    "home":      {"label":"Home / Property",        "label_el":"Ασφάλεια Κατοικίας",  "icon":"🏠", "priority":2},
    "liability": {"label":"Professional Liability", "label_el":"Επαγγελματική Ευθύνη","icon":"💼", "priority":1},
    "travel":    {"label":"Travel Insurance",       "label_el":"Ταξιδιωτική Ασφάλεια","icon":"✈️", "priority":3},
    "pet":       {"label":"Pet Insurance",          "label_el":"Ασφάλεια Κατοικίδιου","icon":"🐾", "priority":3},
    "income":    {"label":"Income Protection",      "label_el":"Ασφάλεια Εισοδήματος","icon":"💰", "priority":2},
    "critical":  {"label":"Critical Illness",       "label_el":"Κρίσιμες Παθήσεις",   "icon":"🏥", "priority":2},
    "education": {"label":"Education / Savings Plan","label_el":"Εκπαιδευτικό Πρόγραμμα","icon":"🎓","priority":3},
}

CARRIERS_PER_TYPE = {
    "motor":    ["3P Insurance","Hellas Direct","Groupama","Generali","Ethniki","AXA"],
    "health":   {"greek":["Groupama","Generali","Ethniki","Interamerican","Eurolife"],
                 "international":["Morgan Price","Bupa Global","NOW Health","Cigna"]},
    "life":     ["Generali","Ethniki","Interamerican","Eurolife","NN","Allianz"],
    "home":     ["Groupama","Generali","Ethniki","AXA","Interamerican"],
    "liability":["Groupama","Generali","Ethniki","AXA","Interamerican","Eurolife"],
    "travel":   ["Groupama","Generali","AXA","Allianz","Eurolife"],
    "pet":      ["Safe Pet System"],
    "income":   ["Generali","Ethniki","Interamerican","Eurolife"],
    "critical": ["Generali","Ethniki","Interamerican","NN"],
    "education":["Interamerican","Eurolife","NN","Allianz"],
}

def _build_analyzer_prompt(client_data, existing_policies, lang="el"):
    """Build the Claude prompt for insurance needs analysis."""

    existing_types = [p.get("type","").lower() for p in existing_policies]
    profession = client_data.get("profession","").lower()
    age = client_data.get("age", "")
    family = client_data.get("family","")
    income = client_data.get("income","")
    assets = client_data.get("assets","")
    notes = client_data.get("notes","")
    is_expat = client_data.get("is_expat", False)
    has_property = client_data.get("has_property", False)
    has_pets = client_data.get("has_pets", False)
    has_children = client_data.get("has_children", False)
    has_vehicle = client_data.get("has_vehicle", False)
    travels_frequently = client_data.get("travels_frequently", False)

    existing_str = "\n".join(f"- {p.get('type','').title()}: {p.get('provider','')} {p.get('policy_no','')}" for p in existing_policies) if existing_policies else "No policies on file"

    carriers_info = """
Available carriers through Ashlar:
- Motor: 3P Insurance, Hellas Direct, Groupama, Generali, Ethniki, AXA
- Greek Health: Groupama, Generali, Ethniki, Interamerican, Eurolife
- International Health: Morgan Price (UK), Bupa Global (UK), NOW Health, Cigna
- Life: Generali, Ethniki, Interamerican, Eurolife, NN, Allianz
- Professional Liability: Groupama, Generali, Ethniki, AXA, Interamerican
- Home: Groupama, Generali, Ethniki, AXA, Interamerican
- Pet: Safe Pet System (via petshealth.gr)
- Travel: Groupama, Generali, AXA, Allianz

Key Greek market facts:
- Greek domestic health plans: NO free-network outpatient, NO dental, NO psychiatric outpatient, NO imaging outside hospitalisation
- International plans: full outpatient, diagnostics, dental (if selected), psychiatric, physio
- Professional Liability is LEGALLY REQUIRED for architects, engineers, doctors, lawyers in Greece
- Greek deductibles: per-hospitalisation OR annual (important to clarify)
- Expats/frequent travellers need international health (NOT Greek domestic)
"""

    if lang == "el":
        prompt = f"""Είσαι σύμβουλος ασφαλίσεων της Ashlar Insurance στην Ελλάδα. Ανάλυσε τις ασφαλιστικές ανάγκες αυτού του πελάτη και προτείνου ασφαλιστικά προγράμματα.

ΣΤΟΙΧΕΙΑ ΠΕΛΑΤΗ:
- Όνομα: {client_data.get('name','')}
- Ηλικία: {age}
- Επάγγελμα: {profession}
- Οικογένεια: {family}
- Εισόδημα: {income}
- Περιουσιακά στοιχεία: {assets}
- Έχει ακίνητο: {'Ναι' if has_property else 'Όχι'}
- Έχει όχημα: {'Ναι' if has_vehicle else 'Όχι'}
- Έχει κατοικίδιο: {'Ναι' if has_pets else 'Όχι'}
- Έχει παιδιά: {'Ναι' if has_children else 'Όχι'}
- Expat / Ταξιδεύει συχνά: {'Ναι' if (is_expat or travels_frequently) else 'Όχι'}
- Επιπλέον σημειώσεις: {notes}

ΥΠΑΡΧΟΥΣΕΣ ΑΣΦΑΛΙΣΕΙΣ:
{existing_str}

{carriers_info}

Δώσε δομημένη ανάλυση:

## 🔍 ΑΝΑΛΥΣΗ ΠΡΟΦΙΛ
Σύντομη εκτίμηση του ασφαλιστικού προφίλ (2-3 προτάσεις)

## ✅ ΚΑΛΥΨΕΙΣ ΠΟΥ ΕΧΕΙ
Τι έχει ήδη και αξιολόγηση

## ⚠️ ΚΕΝΑ ΚΑΛΥΨΕΩΝ
Για κάθε κενό:
- **[Είδος ασφάλισης]** — Επείγον 🔴 / Προτεινόμενο 🟡 / Προαιρετικό 🟢
- Γιατί το χρειάζεται (ειδικά για το επάγγελμα/προφίλ του)
- Προτεινόμενοι ασφαλιστές από το panel μας
- Εκτιμώμενο ετήσιο ασφάλιστρο (εύρος)

## 📋 ΠΛΑΝΟ ΔΡΑΣΗΣ
Προτεραιότητες (1-2-3) με χρονοδιάγραμμα

## 💬 SCRIPT ΕΠΙΚΟΙΝΩΝΙΑΣ
Ένα έτοιμο μήνυμα WhatsApp/email για να στείλεις στον πελάτη"""

    else:
        prompt = f"""You are an insurance adviser at Ashlar Insurance, Greece. Analyse this client's insurance needs and recommend coverage.

CLIENT PROFILE:
- Name: {client_data.get('name','')}
- Age: {age}
- Profession: {profession}
- Family: {family}
- Income: {income}
- Assets: {assets}
- Has property: {'Yes' if has_property else 'No'}
- Has vehicle: {'Yes' if has_vehicle else 'No'}
- Has pets: {'Yes' if has_pets else 'No'}
- Has children: {'Yes' if has_children else 'No'}
- Expat / Travels frequently: {'Yes' if (is_expat or travels_frequently) else 'No'}
- Notes: {notes}

EXISTING POLICIES:
{existing_str}

{carriers_info}

Provide structured analysis:

## 🔍 PROFILE ANALYSIS
Brief assessment of insurance profile (2-3 sentences)

## ✅ EXISTING COVERAGE
What they have and assessment

## ⚠️ COVERAGE GAPS
For each gap:
- **[Insurance type]** — Urgent 🔴 / Recommended 🟡 / Optional 🟢
- Why they need it (specific to their profession/profile)
- Recommended carriers from our panel
- Estimated annual premium (range)

## 📋 ACTION PLAN
Priorities (1-2-3) with timeline

## 💬 CLIENT SCRIPT
Ready WhatsApp/email message to send the client"""

    return prompt


# ── PHASE 2: POLICY TYPE CONFIG ───────────────────────────────────────────────
_POLICY_TYPES = {
    "motor":     {"label":"Motor Insurance",        "label_el":"Ασφάλεια Οχήματος",   "icon":"🚗","color":"#1E40AF"},
    "health":    {"label":"Health Insurance",       "label_el":"Ασφάλεια Υγείας",     "icon":"❤️","color":"#DC2626"},
    "life":      {"label":"Life Insurance",         "label_el":"Ασφάλεια Ζωής",       "icon":"🫀","color":"#7C3AED"},
    "home":      {"label":"Home / Property",        "label_el":"Ασφάλεια Κατοικίας",  "icon":"🏠","color":"#059669"},
    "travel":    {"label":"Travel Insurance",       "label_el":"Ταξιδιωτική Ασφάλεια","icon":"✈️","color":"#0EA5E9"},
    "pet":       {"label":"Pet Insurance",          "label_el":"Ασφάλεια Κατοικίδιου","icon":"🐾","color":"#0D9488"},
    "liability": {"label":"Professional Liability", "label_el":"Επαγγελματική Ευθύνη","icon":"💼","color":"#D97706"},
    "other":     {"label":"Other Policy",           "label_el":"Άλλη Ασφάλεια",        "icon":"📋","color":"#6B7280"},
}
_PROVIDERS = ["3P Insurance","Hellas Direct","Groupama","Generali","Ethniki",
              "Morgan Price","NOW Health","Bupa Global","Safe Pet System",
              "AXA","Interamerican","Eurolife","NN","Allianz","Other"]
_PAY_STATUS  = ["✅ Paid","🟡 Pending","🔴 Overdue","🔵 Direct Debit"]
_CLM_STATUS  = ["🟡 Under review","🔴 Disputed","🟢 Approved","✅ Settled","❌ Rejected"]


def render_commissions():
    """Commissions tracker — calculate commissions from policy data."""
    import urllib.request as _ur, json as _j
    st.markdown("## 📈 Commissions Tracker")
    st.caption("Εκτίμηση προμηθειών βάσει ασφαλίστρων · Default rates per insurer")

    # Commission rates inline


    tab_calc, tab_rates = st.tabs(["📊 Calculate", "⚙️ Commission Rates"])

    with tab_calc:
        st.markdown("### Manual Policy Entry")
        st.caption("Enter policies to calculate estimated commissions")

        if "comm_policies" not in st.session_state:
            st.session_state.comm_policies = []

        with st.expander("➕ Add policy"):
            cp1,cp2,cp3 = st.columns(3)
            with cp1:
                cp_client = st.text_input("Client", key="cp_client")
                cp_insurer= st.selectbox("Insurer", _PROVIDERS, key="cp_ins")
            with cp2:
                cp_type   = st.selectbox("Type", list(_POLICY_TYPES.keys()),
                    format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",
                    key="cp_type")
                cp_prem   = st.number_input("Premium (EUR)", min_value=0.0, key="cp_prem")
            with cp3:
                cp_pno    = st.text_input("Policy No.", key="cp_pno")
                cp_rate   = st.number_input("Override rate (%)", min_value=0.0, max_value=50.0,
                    value=float(_DEFAULT_COMMISSION_RATES.get(st.session_state.get("cp_ins",""),0.15)*100),
                    key="cp_rate", format="%.1f")
            if st.button("Add ✓", key="add_comm_pol"):
                st.session_state.comm_policies.append({
                    "client_name":cp_client,"insurer":cp_insurer,
                    "policy_category":cp_type,"premium":cp_prem,
                    "policy_number":cp_pno,"rate_override":cp_rate/100,
                })
                st.rerun()

        if st.session_state.comm_policies:
            report = _commission_report(st.session_state.comm_policies)
            # Stats
            s1,s2,s3,s4 = st.columns(4)
            s1.metric("Policies",      report["policy_count"])
            s2.metric("Total Premium", f"€{report['total_premium']:,.2f}")
            s3.metric("Est. Commission",f"€{report['total_commission']:,.2f}")
            s4.metric("Avg Rate",f"{round(report['total_commission']/report['total_premium']*100,1) if report['total_premium'] else 0}%")

            st.markdown("#### By Insurer")
            for ins, data in sorted(report["by_insurer"].items(),
                                    key=lambda x:x[1]["commission"],reverse=True):
                ci1,ci2,ci3,ci4 = st.columns([2,1,1,1])
                ci1.markdown(f"**{ins}**")
                ci2.markdown(f"€{data['premium']:,.0f}")
                ci3.markdown(f"**€{data['commission']:,.0f}**")
                ci4.markdown(f"{data['count']} policies")

            st.markdown("#### Policy List")
            for i,p in enumerate(st.session_state.comm_policies):
                comm = _calculate_commission(float(p.get("premium",0)), p.get("insurer",""),
                                            p.get("rate_override"))
                pl1,pl2,pl3 = st.columns([3,1,1])
                pl1.markdown(f"**{p.get('client_name','')}** — {p.get('insurer','')} {p.get('policy_number','')}")
                pl2.markdown(f"€{comm:,.2f}")
                if pl3.button("✕",key=f"del_cp_{i}"):
                    st.session_state.comm_policies.pop(i); st.rerun()

            # Export
            lines = ["Client,Insurer,Type,Premium,Commission,Policy No"]
            for p in st.session_state.comm_policies:
                comm = _calculate_commission(float(p.get("premium",0)),p.get("insurer",""),p.get("rate_override"))
                lines.append(f"{p.get('client_name','')},{p.get('insurer','')},{p.get('policy_category','')},{p.get('premium',0)},{comm},{p.get('policy_number','')}")
            csv_data = "\n".join(lines)
            csv_data = "\n".join(lines)
            st.download_button("Export CSV", csv_data, file_name="commissions.csv", mime="text/csv")
        st.markdown("### Default Commission Rates")
        st.caption("Rates used when no override is specified")
        for ins, rate in sorted(_DEFAULT_COMMISSION_RATES.items()):
            r1,r2 = st.columns([3,1])
            r1.markdown(ins)
            r2.markdown(f"**{rate*100:.0f}%**")
        st.info("To override a rate for a specific policy, use the 'Override rate' field when adding.")


def chi_api(endpoint: str, params: dict = None) -> dict | list | None:
    """Call the CHI Insurance Portal REST API from HAL."""
    import urllib.request as _ur, json as _j, urllib.parse as _up
    portal_url = st.secrets.get("CHI_PORTAL_URL","https://chi-insurance-portal-production.up.railway.app")
    api_key    = st.secrets.get("CHI_API_KEY","")
    if not api_key: return None
    url = f"{portal_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
    if params:
        url += "?" + _up.urlencode(params)
    req = _ur.Request(url, headers={"X-API-Key": api_key, "Accept":"application/json"})
    try:
        with _ur.urlopen(req, timeout=10) as r:
            return _j.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def render_chi_analyzer():
    """AI Insurance Needs Analyzer — profile client and identify coverage gaps."""
    import urllib.request as _ur, json as _j

    st.markdown("## 🧠 AI Insurance Analyzer")
    st.caption("Αναλύει το προφίλ του πελάτη · Εντοπίζει κενά κάλυψης · Προτείνει ασφαλιστικά προγράμματα")

    api_key = st.secrets.get("Claude_API_Key","") or st.secrets.get("ANTHROPIC_API_KEY","")

    # ── Client profile ─────────────────────────────────────────────────────────
    st.markdown("### 👤 Προφίλ Πελάτη")
    col1, col2, col3 = st.columns(3)
    with col1:
        a_name  = st.text_input("Όνομα πελάτη *", key="an_name", placeholder="Μαρία Παπαδοπούλου")
        a_age   = st.number_input("Ηλικία", min_value=18, max_value=90, value=35, key="an_age")
        a_prof  = st.text_input("Επάγγελμα *", key="an_prof",
                                placeholder="Αρχιτέκτονας, Ιατρός, Δικηγόρος, Έμπορος...")
    with col2:
        a_family = st.selectbox("Οικογενειακή κατάσταση",
            ["Άγαμος/η","Έγγαμος/η χωρίς παιδιά","Έγγαμος/η με παιδιά","Διαζευγμένος/η"],
            key="an_family")
        a_income = st.selectbox("Εισόδημα (ετήσιο)",
            ["< €20k","€20k–€40k","€40k–€80k","€80k–€150k","> €150k"],
            key="an_income")
        a_notes  = st.text_area("Επιπλέον στοιχεία", height=80, key="an_notes",
                                placeholder="π.χ. Ιδιόκτητο γραφείο, σκύλος, ταξιδεύει για δουλειά...")
    with col3:
        a_prop    = st.checkbox("🏠 Ιδιοκτήτης ακινήτου", key="an_prop")
        a_vehicle = st.checkbox("🚗 Έχει όχημα", key="an_veh", value=True)
        a_pets    = st.checkbox("🐾 Έχει κατοικίδιο", key="an_pet")
        a_kids    = st.checkbox("👶 Έχει παιδιά", key="an_kids")
        a_expat   = st.checkbox("✈️ Expat / Ταξιδεύει συχνά", key="an_expat")
        a_lang    = st.radio("Γλώσσα ανάλυσης", ["el","en"], horizontal=True,
                             format_func=lambda x: "🇬🇷 Ελληνικά" if x=="el" else "🇬🇧 English",
                             key="an_lang")
        a_children = "Ναι" if a_kids else "Όχι"

    # ── Existing policies — PDF upload / Railway pull / manual ────────────────
    st.markdown("### 📋 Υπάρχουσες Ασφαλίσεις")
    st.caption("Ανεβάστε PDF ασφαλιστηρίων · ή συνδεθείτε με CHI Portal · ή προσθέστε χειροκίνητα")

    if "an_policies" not in st.session_state:
        st.session_state.an_policies = []

    # ── PDF UPLOAD ────────────────────────────────────────────────────────────
    with st.expander("📄 Upload Policy PDFs — AI extracts details automatically", expanded=True):
        uploaded_pdfs = st.file_uploader(
            "Upload one or more insurance policy PDFs",
            type=["pdf"], accept_multiple_files=True, key="pdf_policies"
        )
        if uploaded_pdfs:
            if st.button("🤖 Extract Policies with AI", type="primary",
                         key="extract_pdfs", use_container_width=True):
                api_key = st.secrets.get("Claude_API_Key","") or st.secrets.get("ANTHROPIC_API_KEY","")
                if not api_key:
                    st.error("Add Claude_API_Key to secrets.")
                else:
                    import urllib.request as _ur2, json as _j2
                    extracted = []
                    for pdf_file in uploaded_pdfs:
                        with st.spinner(f"Reading {pdf_file.name}..."):
                            # Extract text from PDF using pypdf
                            try:
                                from pypdf import PdfReader
                                reader = PdfReader(pdf_file)
                                pdf_text = "\n".join(
                                    page.extract_text() or "" for page in reader.pages
                                )[:8000]  # limit to 8k chars
                            except Exception as e:
                                st.warning(f"Could not read {pdf_file.name}: {e}")
                                continue

                            if not pdf_text.strip():
                                st.warning(f"{pdf_file.name}: no text found (scanned PDF?)")
                                continue

                            # Ask Claude to extract structured policy data
                            extract_prompt = f"""Extract insurance policy details from this document.
Return ONLY a JSON object with these exact fields:
{{
  "policy_type": one of: motor/health/life/home/travel/pet/liability/other,
  "insurer": "company name",
  "policy_number": "policy number or empty string",
  "product": "product/plan name",
  "premium": "annual premium amount as number string",
  "currency": "EUR or GBP or USD",
  "expiry_date": "YYYY-MM-DD or empty string",
  "coverage_summary": "2-3 sentence summary of main coverage",
  "key_exclusions": "main exclusions or empty string",
  "deductible": "excess/deductible amount or empty string"
}}

If a field is not found, use empty string. Return ONLY the JSON, no other text.

POLICY DOCUMENT:
{pdf_text}"""

                            body = _j2.dumps({
                                "model":"claude-sonnet-4-6","max_tokens":800,
                                "messages":[{"role":"user","content":extract_prompt}]
                            }).encode()
                            req = _ur2.Request("https://api.anthropic.com/v1/messages",data=body,
                                headers={"x-api-key":api_key,"anthropic-version":"2023-06-01",
                                         "content-type":"application/json"})
                            try:
                                with _ur2.urlopen(req, timeout=30) as r:
                                    result = _j2.loads(r.read())["content"][0]["text"].strip()
                                # Clean JSON
                                if result.startswith("```"):
                                    result = result.split("```")[1]
                                    if result.startswith("json"):
                                        result = result[4:]
                                policy_data = _j2.loads(result.strip())
                                policy_data["source_file"] = pdf_file.name
                                policy_data["color"] = _POLICY_TYPES.get(
                                    policy_data.get("policy_type","other"),
                                    _POLICY_TYPES["other"])["color"]
                                # Map to our policy format
                                extracted.append({
                                    "type":       policy_data.get("policy_type","other"),
                                    "provider":   policy_data.get("insurer",""),
                                    "policy_no":  policy_data.get("policy_number",""),
                                    "product":    policy_data.get("product",""),
                                    "premium":    policy_data.get("premium",""),
                                    "currency":   policy_data.get("currency","EUR"),
                                    "renewal_date":policy_data.get("expiry_date",""),
                                    "coverage":   policy_data.get("coverage_summary",""),
                                    "exclusions": policy_data.get("key_exclusions",""),
                                    "deductible": policy_data.get("deductible",""),
                                    "source_file":pdf_file.name,
                                    "color":      _POLICY_TYPES.get(policy_data.get("policy_type","other"),_POLICY_TYPES["other"])["color"],
                                })
                                st.success(f"✅ {pdf_file.name} → {_POLICY_TYPES.get(policy_data.get('policy_type','other'),_POLICY_TYPES['other'])['icon']} {policy_data.get('insurer','')} {policy_data.get('product','')}")
                            except _j2.JSONDecodeError:
                                st.warning(f"Could not parse {pdf_file.name} — try manual entry")
                            except Exception as e:
                                st.error(f"{pdf_file.name}: {e}")

                    if extracted:
                        # Merge with existing (avoid duplicates by policy_no)
                        existing_nos = {p.get("policy_no","") for p in st.session_state.an_policies}
                        new_ones = [p for p in extracted if p.get("policy_no","") not in existing_nos]
                        st.session_state.an_policies.extend(new_ones)
                        st.success(f"✅ Added {len(new_ones)} policies from PDFs")
                        st.rerun()

    # ── Live pull from CHI Portal ────────────────────────────────────────────
    chi_api_key = st.secrets.get("CHI_API_KEY","")
    if chi_api_key and a_name and len(a_name) >= 3:
        if st.button("🔗 Pull from CHI Portal", key="pull_chi", use_container_width=False):
            with st.spinner("Fetching from Railway..."):
                # Search clients
                clients_data = chi_api("clients", {"search": a_name})
                if clients_data and isinstance(clients_data, list) and len(clients_data) > 0:
                    # Find best match
                    match = next((c for c in clients_data
                                  if a_name.lower() in c.get("name","").lower()), clients_data[0])
                    client_detail = chi_api(f"clients/{match['id']}")
                    if client_detail and "policies" in client_detail:
                        st.session_state.an_policies = [
                            {"type":    p.get("type","other"),
                             "provider":p.get("insurer",""),
                             "policy_no":p.get("policy_number",""),
                             "premium": p.get("premium",""),
                             "renewal_date": p.get("expiry_date",""),
                             "color":   _POLICY_TYPES.get(p.get("type","other"),_POLICY_TYPES["other"])["color"]}
                            for p in client_detail["policies"]
                        ]
                        st.success(f"✅ Pulled {len(st.session_state.an_policies)} policies for {match['name']}")
                        st.rerun()
                    else:
                        st.warning("Client found but no policies. Add manually below.")
                elif isinstance(clients_data, dict) and "error" in clients_data:
                    st.error(f"API error: {clients_data['error']}")
                else:
                    st.warning(f"No client found matching '{a_name}' in CHI Portal.")
    elif not chi_api_key:
        st.caption("💡 Add CHI_API_KEY to Streamlit secrets + add chi_api_routes.py to Railway for auto-pull")

    with st.expander("➕ Προσθήκη υπάρχουσας ασφάλισης"):
        ep1, ep2, ep3 = st.columns(3)
        with ep1:
            ep_type = st.selectbox("Τύπος", list(_POLICY_TYPES.keys()),
                format_func=lambda k: f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label_el']}",
                key="ep_type")
        with ep2:
            ep_prov = st.selectbox("Ασφαλιστής", _PROVIDERS, key="ep_prov")
        with ep3:
            ep_no   = st.text_input("Αρ. ασφαλιστηρίου", key="ep_no")
        if st.button("Προσθήκη ✓", key="add_an_pol"):
            st.session_state.an_policies.append(
                {"type":ep_type,"provider":ep_prov,"policy_no":ep_no})
            st.rerun()

    for i, p in enumerate(st.session_state.an_policies):
        cfg  = _POLICY_TYPES.get(p.get("type","other"), _POLICY_TYPES["other"])
        ac1, ac2 = st.columns([5,1])
        src  = f" · 📄 {p['source_file']}" if p.get("source_file") else ""
        prem = f" · {p.get('currency','EUR')} {p['premium']}" if p.get("premium") else ""
        ren  = f" · Λήξη {p['renewal_date']}" if p.get("renewal_date") else ""
        pno  = f" `{p['policy_no']}`" if p.get("policy_no") else ""
        ac1.markdown(f"{cfg['icon']} **{p.get('provider','')}** {p.get('product','')}{pno}{prem}{ren}{src}")
        if p.get("coverage"):
            ac1.caption(p["coverage"][:120])
        if ac2.button("✕", key=f"del_an_{i}"):
            st.session_state.an_policies.pop(i); st.rerun()

    st.divider()

    # ── Analyse button ─────────────────────────────────────────────────────────
    if st.button("🧠 Ανάλυση Ασφαλιστικών Αναγκών", type="primary",
                 use_container_width=True, key="run_analysis"):
        if not a_name or not a_prof:
            st.warning("Συμπληρώστε όνομα και επάγγελμα.")
        elif not api_key:
            st.error("Προσθέστε Claude_API_Key στα Streamlit secrets.")
        else:
            client_data = {
                "name": a_name, "age": a_age, "profession": a_prof,
                "family": a_family, "income": a_income, "notes": a_notes,
                "has_property": a_prop, "has_vehicle": a_vehicle,
                "has_pets": a_pets, "has_children": a_kids,
                "is_expat": a_expat, "travels_frequently": a_expat,
            }
            prompt = build_analyzer_prompt(client_data, st.session_state.an_policies, a_lang)

            with st.spinner("Claude αναλύει το προφίλ..."):
                body = _j.dumps({
                    "model":"claude-sonnet-4-6","max_tokens":3000,
                    "system":("Είσαι έμπειρος ασφαλιστικός σύμβουλος στην Ελλάδα με βαθιά γνώση "
                              "της ελληνικής και διεθνούς ασφαλιστικής αγοράς."),
                    "messages":[{"role":"user","content":prompt}]
                }).encode()
                req = _ur.Request("https://api.anthropic.com/v1/messages", data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01",
                             "content-type":"application/json"})
                try:
                    with _ur.urlopen(req, timeout=60) as r:
                        result = _j.loads(r.read())["content"][0]["text"]
                    st.session_state["an_result"]  = result
                    st.session_state["an_client"]  = a_name
                    st.session_state["an_prof_val"]= a_prof
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Display results ────────────────────────────────────────────────────────
    if st.session_state.get("an_result"):
        result = st.session_state["an_result"]
        cname  = st.session_state["an_client"]

        st.markdown("---")
        st.markdown(f"### 📊 Ανάλυση: {cname}")
        st.markdown(f'<div style="background:white;border-radius:14px;padding:24px;'
                    f'border:1px solid #E8E0D5;box-shadow:0 2px 8px rgba(0,0,0,.04)">', unsafe_allow_html=True)
        st.markdown(result)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Action buttons ─────────────────────────────────────────────────────
        ab1, ab2, ab3 = st.columns(3)
        with ab1:
            st.download_button("📥 Λήψη ανάλυσης",
                               data=f"ASHLAR INSURANCE — Ανάλυση Αναγκών\n{cname}\n\n{result}",
                               file_name=f"analysis_{cname.replace(' ','_')}.txt",
                               mime="text/plain", use_container_width=True)
        with ab2:
            # Generate proposal HTML
            from datetime import datetime as _dt
            html_proposal = f"""<!DOCTYPE html>
<html lang="el"><head><meta charset="UTF-8">
<title>Ashlar Insurance · Ανάλυση Αναγκών · {cname}</title>
<style>body{{font-family:'DM Sans',system-ui,sans-serif;max-width:800px;margin:0 auto;padding:32px;color:#1C1410}}
.header{{background:linear-gradient(135deg,#1C1410,#3A2E24);color:#E8DDD0;padding:32px;border-radius:12px;margin-bottom:24px}}
.logo{{font-size:13px;color:#C9A96E;letter-spacing:4px;margin-bottom:8px}}
.title{{font-size:24px;font-weight:700}}
.content{{background:white;border:1px solid #E8E0D5;border-radius:12px;padding:24px}}
h2{{color:#C9A96E;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin-top:20px}}
.footer{{text-align:center;font-size:11px;color:#A09080;margin-top:20px}}
</style></head><body>
<div class="header"><div class="logo">ASHLAR INSURANCE</div>
<div class="title">Ανάλυση Ασφαλιστικών Αναγκών</div>
<div style="font-size:13px;opacity:.7;margin-top:8px">{cname} · {_dt.now().strftime("%d/%m/%Y")}</div></div>
<div class="content">{"<br>".join(result.split(chr(10)))}</div>
<div class="footer">Ashlar Insurance · info@chiinsurancebrokers.com · ashlar-assurance.com<br>
Εμπιστευτικό έγγραφο</div></body></html>"""
            st.download_button("📄 Πρόταση HTML",
                               data=html_proposal.encode(),
                               file_name=f"proposal_{cname.replace(' ','_')}.html",
                               mime="text/html", use_container_width=True)
        with ab3:
            if st.button("🔄 Νέα Ανάλυση", use_container_width=True, key="reset_an"):
                for k in ["an_result","an_client","an_prof_val","an_policies"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()



def render_chi_portal():
    portal_url = st.secrets.get("CHI_PORTAL_URL",
                                "https://chi-insurance-portal-production.up.railway.app")
    gh_token   = st.secrets.get("GITHUB_TOKEN","")
    repo       = "chiinsurancebrokers/chi-insurance-portal"

    st.markdown("## 🌐 CHI Insurance Portal")
    st.caption(f"{portal_url}")

    qa1,qa2,qa3 = st.columns(3)
    with qa1: st.link_button("🌐 Open Portal",   portal_url,            use_container_width=True, type="primary")
    with qa2: st.link_button("🔐 Admin Login",   f"{portal_url}/login", use_container_width=True)
    with qa3: st.link_button("📂 GitHub Repo",   f"https://github.com/{repo}", use_container_width=True)

    st.divider()
    tab_op, tab_gen, tab_manage = st.tabs(["🚀 Operate","🏗️ Generate Client Portal","📋 Manage Portals"])

    # ══ TAB: OPERATE ══════════════════════════════════════════════════════════
    with tab_op:
        st.markdown(f"""<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);
            border-radius:16px;padding:28px;text-align:center;margin-bottom:20px">
            <div style="font-size:40px;margin-bottom:10px">🛡️</div>
            <div style="font-size:22px;font-weight:800;color:#C9A96E;margin-bottom:6px">CHI Admin Panel</div>
            <div style="font-size:13px;color:#A89880;margin-bottom:20px">
                138 Clients · 222 Active Policies · 171 Pending Payments · 30 Expiring
            </div>
            <a href="{portal_url}" target="_blank"
               style="background:#C9A96E;color:#1C1410;padding:12px 32px;border-radius:8px;
                      font-weight:800;font-size:15px;text-decoration:none">
                Open Admin Panel →
            </a>
        </div>""", unsafe_allow_html=True)
        q1,q2,q3,q4 = st.columns(4)
        with q1: st.link_button("👥 Clients",       f"{portal_url}/clients",  use_container_width=True, type="primary")
        with q2: st.link_button("📄 Policies",      f"{portal_url}/policies", use_container_width=True, type="primary")
        with q3: st.link_button("💳 Payments",      f"{portal_url}/payments", use_container_width=True, type="primary")
        with q4: st.link_button("📧 Send Renewals", f"{portal_url}/renewals", use_container_width=True)

        # Live renewal queue from API
        if st.secrets.get("CHI_API_KEY",""):
            st.divider()
            st.markdown("#### ⏰ Upcoming Renewals (Live from Railway)")
            if st.button("🔄 Refresh renewal queue", key="refresh_renewals"):
                st.session_state["_renewals_data"] = chi_api("renewals")
                st.rerun()
            renewals_data = st.session_state.get("_renewals_data")
            if renewals_data and "error" not in (renewals_data or {}):
                urgent   = renewals_data.get("urgent",[])
                soon     = renewals_data.get("soon",[])
                upcoming = renewals_data.get("upcoming",[])
                if urgent:
                    st.markdown(f"**🔴 Urgent ({len(urgent)}) — within 7 days:**")
                    for r in urgent[:5]:
                        st.markdown(f"• **{r.get('client_name','')}** — {r.get('insurer','')} {r.get('type','')} · expires {r.get('expiry_date','')} · **{r.get('days_left','')} days**")
                if soon:
                    st.markdown(f"**🟡 Soon ({len(soon)}) — within 30 days:**")
                    for r in soon[:5]:
                        st.markdown(f"• **{r.get('client_name','')}** — {r.get('insurer','')} · {r.get('days_left','')} days")
            elif renewals_data:
                st.error(f"API error: {renewals_data.get('error')}")
            else:
                st.caption("Click Refresh to load renewal queue from Railway.")
        st.divider()
        with st.expander("🔐 Admin credentials"):
            st.markdown(f"""| | |\n|---|---|\n| URL | [{portal_url}]({portal_url}) |\n| Username | `admin` |\n| Email | `xiatropoulos@gmail.com` |""")
        st.info("📊 **Monthly CSV Upload** — 3P format: CLIENT NAME · INSURANCE TYPE · COMPANY · LICENSE PLATE · PREMIUM · EXPIRY DATE  ·  Hellas Direct: Ονοματεπώνυμο · Αρ. Κυκλοφορίας · Ασφάλιστρο · Λήξη")

    # ══ TAB: GENERATE ═════════════════════════════════════════════════════════
    with tab_gen:
        st.caption("Multi-policy personalised portal · All insurance types · Push to GitHub")

        if "p2_policies" not in st.session_state:
            st.session_state.p2_policies  = []
            st.session_state.p2_payments  = []
            st.session_state.p2_documents = []
            st.session_state.p2_claims    = []

        # Client info
        st.markdown("#### 👤 Client")
        ci1,ci2,ci3 = st.columns(3)
        with ci1: p2_name = st.text_input("Full name *", key="p2_name")
        with ci2: p2_email= st.text_input("Email",       key="p2_email")
        with ci3: p2_lang = st.radio("Language",["el","en"],horizontal=True,key="p2_lang")

        # ── Policies ──────────────────────────────────────────────────────────
        st.markdown("#### 📋 Policies")
        with st.expander("➕ Add policy", expanded=len(st.session_state.p2_policies)==0):
            np1,np2,np3 = st.columns(3)
            with np1:
                npt = st.selectbox("Type", list(_POLICY_TYPES.keys()),
                                   format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",
                                   key="np_type")
                npp = st.selectbox("Provider", _PROVIDERS, key="np_prov")
            with np2:
                npn = st.text_input("Policy number", key="np_no")
                nppr= st.text_input("Product / coverage", key="np_prod")
            with np3:
                npm = st.text_input("Premium", key="np_prem")
                npc = st.selectbox("Currency",["EUR","GBP","USD"],key="np_cur")
                npd = st.date_input("Renewal date", key="np_date")
            npo = st.text_input("Notes (optional)", key="np_notes")
            if st.button("Add Policy ✓", type="primary", key="add_pol"):
                st.session_state.p2_policies.append({
                    "type":npt,"provider":npp,"policy_no":npn,"product":nppr,
                    "premium":npm,"currency":npc,
                    "renewal_date":str(npd),"status":"Active",
                    "notes":npo,"color":_POLICY_TYPES[npt]["color"]
                })
                st.success(f"Policy added: {_POLICY_TYPES[npt]['icon']} {npp}")
                st.rerun()

        for i,p in enumerate(st.session_state.p2_policies):
            cfg = _POLICY_TYPES.get(p["type"],_POLICY_TYPES["other"])
            pc1,pc2 = st.columns([5,1])
            pc1.markdown(f"{cfg['icon']} **{p['provider']}** — {p['product']} · {p['currency']} {p['premium']} · Renewal {p['renewal_date']}")
            if pc2.button("✕",key=f"del_pol_{i}"):
                st.session_state.p2_policies.pop(i); st.rerun()

        # ── Payments ──────────────────────────────────────────────────────────
        st.markdown("#### 💳 Payment History")
        with st.expander("➕ Add payment"):
            pp1,pp2,pp3 = st.columns(3)
            with pp1:
                ppd = st.text_input("Date (dd/mm/yyyy)", key="pp_date")
                ppa = st.text_input("Amount", key="pp_amt")
            with pp2:
                ppdesc= st.text_input("Description", key="pp_desc")
                ppc   = st.selectbox("Currency",["EUR","GBP","USD"],key="pp_cur")
            with pp3:
                ppm = st.text_input("Payment method", key="pp_meth", placeholder="Bank transfer, credit card...")
                pps = st.selectbox("Status", _PAY_STATUS, key="pp_stat")
            if st.button("Add Payment ✓", key="add_pay"):
                st.session_state.p2_payments.append(
                    {"date":ppd,"description":ppdesc,"amount":ppa,"currency":ppc,"method":ppm,"status":pps})
                st.rerun()
        for i,pay in enumerate(st.session_state.p2_payments):
            pc1,pc2 = st.columns([5,1])
            pc1.markdown(f"{pay['status']} **{pay['date']}** — {pay['description']} · {pay['currency']} {pay['amount']}")
            if pc2.button("✕",key=f"del_pay_{i}"):
                st.session_state.p2_payments.pop(i); st.rerun()

        # ── Documents ─────────────────────────────────────────────────────────
        st.markdown("#### 📂 Documents")
        with st.expander("➕ Add document link"):
            dd1,dd2,dd3 = st.columns(3)
            with dd1: ddn = st.text_input("Document name", key="dd_name")
            with dd2: ddu = st.text_input("URL (Google Drive, Dropbox...)", key="dd_url")
            with dd3: ddt = st.selectbox("Type",["pdf","word","image","other"],key="dd_type")
            if st.button("Add Document ✓", key="add_doc"):
                st.session_state.p2_documents.append({"name":ddn,"url":ddu,"type":ddt})
                st.rerun()
        for i,doc in enumerate(st.session_state.p2_documents):
            dc1,dc2 = st.columns([5,1])
            dc1.markdown(f"📄 **{doc['name']}** · {doc['url'][:50]}...")
            if dc2.button("✕",key=f"del_doc_{i}"):
                st.session_state.p2_documents.pop(i); st.rerun()

        # ── Claims ────────────────────────────────────────────────────────────
        st.markdown("#### 🔍 Claims")
        with st.expander("➕ Add claim"):
            cl1,cl2,cl3 = st.columns(3)
            with cl1:
                clr = st.text_input("Reference", key="cl_ref")
                clt = st.selectbox("Policy type",list(_POLICY_TYPES.keys()),
                                   format_func=lambda k:f"{_POLICY_TYPES[k]['icon']} {_POLICY_TYPES[k]['label']}",
                                   key="cl_type")
            with cl2:
                cld = st.text_input("Date", key="cl_date")
                cla = st.text_input("Amount", key="cl_amt")
                clc = st.selectbox("Currency",["EUR","GBP","USD"],key="cl_cur")
            with cl3:
                cls_ = st.selectbox("Status", _CLM_STATUS, key="cl_stat")
                cln  = st.text_area("Description", height=68, key="cl_notes")
            if st.button("Add Claim ✓", key="add_clm"):
                st.session_state.p2_claims.append(
                    {"ref":clr,"policy_type":clt,"date":cld,"amount":cla,
                     "currency":clc,"status":cls_,"description":cln})
                st.rerun()
        for i,cl in enumerate(st.session_state.p2_claims):
            cc1,cc2 = st.columns([5,1])
            cc1.markdown(f"{cl['status']} **{cl['ref']}** — {_POLICY_TYPES.get(cl['policy_type'],_POLICY_TYPES['other'])['icon']} {cl['description'][:60]}")
            if cc2.button("✕",key=f"del_cl_{i}"):
                st.session_state.p2_claims.pop(i); st.rerun()

        st.divider()

        # ── Generate button ───────────────────────────────────────────────────
        if st.button("⚡ Generate Client Portal", type="primary",
                     use_container_width=True, key="gen_p2"):
            if not p2_name:
                st.warning("Client name is required.")
            elif not st.session_state.p2_policies:
                st.warning("Add at least one policy.")
            else:
                from chi_portal_phase2 import generate_client_portal
                client_data = {"name":p2_name,"email":p2_email,"lang":p2_lang}
                html = generate_client_portal(
                    client_data,
                    st.session_state.p2_policies,
                    st.session_state.p2_payments,
                    st.session_state.p2_documents,
                    st.session_state.p2_claims,
                )
                st.session_state["p2_html"]   = html
                st.session_state["p2_client"] = p2_name
                st.session_state["p2_folder"] = p2_name.lower().replace(" ","-").replace("'","")
                st.success(f"✅ Portal generated for {p2_name} — {len(st.session_state.p2_policies)} policies")

        # Show result
        if st.session_state.get("p2_html"):
            html   = st.session_state["p2_html"]
            cname  = st.session_state["p2_client"]
            folder = st.session_state["p2_folder"]
            st.download_button("📥 Download index.html", data=html.encode(),
                               file_name="index.html", mime="text/html",
                               use_container_width=True)
            if gh_token:
                if st.button("🚀 Push to GitHub → auto-deploy", use_container_width=True, key="push_p2"):
                    import base64 as _b64, urllib.request as _ur, json as _j, urllib.error as _ue
                    path = f"clients/{folder}/index.html"
                    api  = f"https://api.github.com/repos/{repo}/contents/{path}"
                    hdrs = {"Authorization":f"token {gh_token}","Accept":"application/vnd.github.v3+json",
                            "Content-Type":"application/json","User-Agent":"HAL"}
                    sha = None
                    try:
                        req = _ur.Request(api, headers=hdrs)
                        with _ur.urlopen(req,timeout=8) as r: sha = _j.loads(r.read()).get("sha")
                    except _ue.HTTPError: pass
                    payload = {"message":f"{'Update' if sha else 'Add'} portal: {cname}",
                               "content":_b64.b64encode(html.encode()).decode(),"branch":"main"}
                    if sha: payload["sha"] = sha
                    req = _ur.Request(api,data=_j.dumps(payload).encode(),headers=hdrs,method="PUT")
                    try:
                        with _ur.urlopen(req,timeout=15) as r: _j.loads(r.read())
                        st.success(f"✅ Pushed → clients/{folder}/index.html")
                        st.info("Auto-deploys within 30 seconds.")
                    except Exception as e:
                        st.error(f"Push failed: {e}")
            else:
                st.caption("Add GITHUB_TOKEN to secrets to enable one-click push.")

            if st.button("🔄 New portal", key="reset_p2"):
                for k in ["p2_html","p2_client","p2_folder","p2_policies",
                          "p2_payments","p2_documents","p2_claims"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

    # ══ TAB: MANAGE ═══════════════════════════════════════════════════════════
    with tab_manage:
        # Live stats from API
        live_stats = chi_api("stats") if st.secrets.get("CHI_API_KEY","") else None

        mc1,mc2 = st.columns(2)
        with mc1:
            clients_count  = live_stats.get("total_clients","—")  if live_stats and "error" not in live_stats else "138"
            policies_count = live_stats.get("total_policies","—") if live_stats and "error" not in live_stats else "222"
            expiring_count = live_stats.get("expiring_30_days","—") if live_stats and "error" not in live_stats else "30"
            st.markdown(f"""<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);
                border-radius:12px;padding:18px 20px;color:#E8DDD0;margin-bottom:12px">
                <div style="font-size:11px;color:#7A6A5A;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Railway · Live</div>
                <div style="font-size:15px;font-weight:700;color:#C9A96E">chi-insurance-portal</div>
                <div style="font-size:12px;color:#A89880;margin-top:6px;line-height:1.8">
                    👥 {clients_count} Clients · 📋 {policies_count} Policies<br>
                    ⏰ {expiring_count} Expiring in 30 days
                </div>
                <a href="{portal_url}" target="_blank" style="display:inline-block;margin-top:10px;
                   background:#C9A96E;color:#1C1410;padding:5px 14px;border-radius:6px;
                   text-decoration:none;font-weight:700;font-size:12px">Open →</a>
            </div>""", unsafe_allow_html=True)
        with mc2:
            st.markdown("""<div style="background:white;border:1px solid #E8E0D5;border-radius:12px;padding:18px 20px;margin-bottom:12px">
                <div style="font-size:11px;color:#7A6A5A;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Admin</div>
                <div style="font-size:13px;color:#2C1810;line-height:2">Username: <code>admin</code><br>Email: <code>xiatropoulos@gmail.com</code></div>
            </div>""", unsafe_allow_html=True)

        st.markdown("### Client Portals")
        portals = [{"client":"Pantelis Kourbelas","url":"panteliskourbelas-chiinsurancebrokers.netlify.app","status":"🟢 Live"}]
        if gh_token:
            try:
                import urllib.request as _ur, json as _j
                req = _ur.Request(f"https://api.github.com/repos/{repo}/contents/clients",
                    headers={"Authorization":f"token {gh_token}","Accept":"application/vnd.github.v3+json","User-Agent":"HAL"})
                with _ur.urlopen(req,timeout=8) as r:
                    for item in _j.loads(r.read()):
                        if item.get("type")=="dir":
                            n = item["name"].replace("-"," ").title()
                            if not any(p["client"].lower().replace(" ","")==n.lower().replace(" ","") for p in portals):
                                portals.append({"client":n,"url":"","status":"🔵 GitHub"})
            except: pass

        for p in portals:
            pc1,pc2,pc3,pc4 = st.columns([2,3,1,1])
            pc1.markdown(f"**{p['client']}**")
            if p["url"]: pc2.markdown(f"[{p['url']}](https://{p['url']})")
            else: pc2.caption("Deployed via GitHub")
            pc3.markdown(p["status"])
            if p["url"]: pc4.link_button("Open",f"https://{p['url']}",use_container_width=True)

        st.divider()
        st.link_button("📂 View on GitHub",f"https://github.com/{repo}/tree/main/clients",use_container_width=True)


def render_kira_pet_hal():
    """Kira Pet module embedded in HAL."""
    st.markdown("## 🐾 Kira Pet — AI Veterinary Nurse")
    st.caption("petshealth.gr · AI health assistant for pet insurance clients")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div style="background:linear-gradient(135deg,#059669,#0EA5E9);border-radius:14px;padding:24px;color:white;margin-bottom:16px">
            <div style="font-size:32px;margin-bottom:8px">🐾</div>
            <div style="font-size:18px;font-weight:700">Kira Pet App</div>
            <div style="font-size:13px;opacity:.85;margin:8px 0">AI triage · Photo scan · Vet report · petshealth.gr</div>
        </div>""", unsafe_allow_html=True)
        st.link_button("🚀 Open Kira Pet", "https://kiraaipet.streamlit.app", use_container_width=True)

    with col2:
        st.markdown("""<div style="background:linear-gradient(135deg,#1C1410,#3A2E24);border-radius:14px;padding:24px;color:#E8DDD0;margin-bottom:16px">
            <div style="font-size:32px;margin-bottom:8px">🌐</div>
            <div style="font-size:18px;font-weight:700;color:#C9A96E">petshealth.gr</div>
            <div style="font-size:13px;opacity:.85;margin:8px 0">Pet insurance brand · Safe Pet System · Greece</div>
        </div>""", unsafe_allow_html=True)
        st.link_button("🌐 Open petshealth.gr", "https://petshealth.gr", use_container_width=True)

    st.divider()

    tab_content, tab_social = st.tabs(["📢 Pet Insurance Content", "📱 Social Media"])

    with tab_content:
        content_type = st.selectbox("Content type", [
            "Email to potential client",
            "LinkedIn post — pet insurance awareness",
            "FAQ: What does pet insurance cover?",
            "Comparison: Safe Pet System vs alternatives",
            "Why insure your pet in Greece?",
            "Custom content",
        ])
        if content_type == "Custom content":
            custom = st.text_area("Describe what you need", height=80)
        else:
            custom = ""
        lang = st.radio("Language", ["Greek", "English", "Bilingual"], horizontal=True)
        if st.button("✍️ Generate Content", type="primary"):
            api_key = st.secrets.get("Claude_API_Key","") or st.secrets.get("ANTHROPIC_API_KEY","")
            if not api_key:
                st.error("Add Claude_API_Key to Streamlit secrets.")
            else:
                import urllib.request, json as _json, urllib.error
                prompt = f"""You are a pet insurance content writer for petshealth.gr, a Greek pet insurance brand by Ashlar Insurance.
Brand voice: professional, warm, trustworthy. Carrier: Safe Pet System.
Write: {content_type if not custom else custom}
Language: {lang}
Make it specific, genuine, and avoid generic AI-sounding text."""
                body = _json.dumps({"model":"claude-sonnet-4-6","max_tokens":1500,"messages":[{"role":"user","content":prompt}]}).encode()
                req = urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("Writing..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r:
                            result = _json.loads(r.read())["content"][0]["text"]
                        st.markdown(result)
                        st.download_button("📥 Download", result, file_name="pet_content.txt", mime="text/plain")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_social:
        platform = st.selectbox("Platform", ["LinkedIn", "Instagram", "Facebook", "Email subject line"])
        angle    = st.text_input("Angle / topic", placeholder="e.g. Emergency vet bills in Greece, why you need pet insurance")
        if st.button("📱 Generate Social Post", type="primary"):
            api_key = st.secrets.get("Claude_API_Key","") or st.secrets.get("ANTHROPIC_API_KEY","")
            if api_key and angle:
                import urllib.request, json as _json
                prompt = f"Write a {platform} post for petshealth.gr (Greek pet insurance brand). Topic: {angle}. Include relevant hashtags. Be authentic and engaging. Use Greek language with English hashtags."
                body = _json.dumps({"model":"claude-sonnet-4-6","max_tokens":600,"messages":[{"role":"user","content":prompt}]}).encode()
                req = urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"})
                with st.spinner("Writing..."):
                    try:
                        with urllib.request.urlopen(req,timeout=30) as r:
                            st.markdown(_json.loads(r.read())["content"][0]["text"])
                    except Exception as e:
                        st.error(f"Error: {e}")

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
