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
            ("🎙️", "voice_chat", "HAL Voice"),
            ("📊", "quotes", "Quote Engine"),
            ("📄", "documents", "Document Filler"),
            ("✉️", "comms", "Communications"),
            ("📈", "commissions", "Commissions"),
            ("🔍", "market", "Market Intel"),
            ("🤝", "clients", "Clients"),
            ("🏗️", "apps", "App Builder"),
            ("🐾", "pets", "PetsHealth"),
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
                ("🎙️", "voice_chat", "HAL Voice"),
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


def _extract_pdf_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from a PDF using pypdf / PyPDF2 (whichever is installed)."""
    import io
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i+1}]\n{text.strip()}")
        return "\n\n".join(pages) if pages else "[No readable text found in PDF]"
    except Exception as e:
        return f"[PDF extraction failed for {filename}: {e}]"


def _build_api_content(user_text: str, uploaded_files) -> tuple[list, list[str]]:
    """
    Convert user text + uploaded files into a Claude API content list.
    Returns (api_content_list, attachment_names).
    """
    import base64
    api_content = []
    attachment_names = []

    for uf in (uploaded_files or []):
        attachment_names.append(uf.name)
        file_bytes = uf.read()
        mime = uf.type or ""

        if mime == "application/pdf" or uf.name.lower().endswith(".pdf"):
            pdf_text = _extract_pdf_text(file_bytes, uf.name)
            size_kb = round(len(file_bytes) / 1024, 1)
            api_content.append({
                "type": "text",
                "text": (
                    f"<document filename='{uf.name}' size='{size_kb} KB'>\n"
                    f"{pdf_text}\n"
                    f"</document>"
                ),
            })

        elif mime.startswith("image/") and mime in (
            "image/jpeg", "image/png", "image/gif", "image/webp"
        ):
            b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
            api_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            })

        elif mime in ("text/plain", "text/csv") or uf.name.lower().endswith((".txt", ".csv")):
            text = file_bytes.decode("utf-8", errors="replace")
            api_content.append({
                "type": "text",
                "text": f"<document filename='{uf.name}'>\n{text}\n</document>",
            })

        else:
            # Unsupported — note it so user knows
            api_content.append({
                "type": "text",
                "text": f"[Attached file '{uf.name}' — type '{mime}' not directly readable; please describe what you need from it.]",
            })

    # User message always last so it reads naturally
    api_content.append({"type": "text", "text": user_text})
    return api_content, attachment_names


# ─────────────────────────────────────────────────────────────────────────────
# VOICE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

# Browser-side recorder + Web Speech API component
# Returns a dict via Streamlit component value:
#   {"transcript": str, "audio_b64": str|None}
_VOICE_COMPONENT_HTML = """
<style>
  body { margin:0; font-family: sans-serif; }
  #vc { display:flex; flex-direction:column; align-items:center; gap:12px; padding:16px 0; }
  #btn {
    width:72px; height:72px; border-radius:50%; border:none; cursor:pointer;
    background:#C9A96E; color:#1C1410; font-size:28px;
    box-shadow:0 2px 8px rgba(201,169,110,.35);
    transition:all .15s;
  }
  #btn.recording { background:#E2462C; box-shadow:0 0 0 8px rgba(226,70,44,.2); animation:pulse 1.2s ease-in-out infinite; }
  #btn:disabled { opacity:.45; cursor:default; }
  @keyframes pulse { 0%,100%{box-shadow:0 0 0 4px rgba(226,70,44,.2)} 50%{box-shadow:0 0 0 12px rgba(226,70,44,.08)} }
  #status { font-size:13px; color:#7A6A5A; min-height:18px; }
  #transcript-box {
    width:92%; min-height:48px; padding:8px 12px; border-radius:8px;
    border:1px solid #E8E0D5; font-size:13px; background:#FBF8F4;
    color:#2C1810; resize:none; outline:none;
  }
  #send-btn {
    padding:8px 24px; border-radius:8px; border:none; cursor:pointer;
    background:#C9A96E; color:#1C1410; font-size:13px; font-weight:600;
  }
  #send-btn:disabled { opacity:.4; cursor:default; }
</style>
<div id="vc">
  <button id="btn" title="Hold to record">🎙️</button>
  <div id="status">Click the mic to start recording</div>
  <textarea id="transcript-box" placeholder="Transcript will appear here — you can edit before sending…" rows="3"></textarea>
  <button id="send-btn" disabled>Send to HAL ➜</button>
</div>
<script>
(function(){
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  const box = document.getElementById('transcript-box');
  const sendBtn = document.getElementById('send-btn');
  let recognition = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  const LANG = window.HAL_LANG || 'el-GR';
  const MODE = window.HAL_STT_MODE || 'webspeech';  // 'webspeech' | 'whisper'

  box.addEventListener('input', () => { sendBtn.disabled = box.value.trim().length === 0; });

  // ── SEND ──────────────────────────────────────────────────────────────
  sendBtn.addEventListener('click', () => {
    const text = box.value.trim();
    if (!text) return;
    window.parent.postMessage({type:'hal_voice_send', text: text, audio: window._lastAudioB64 || null}, '*');
    box.value = '';
    sendBtn.disabled = true;
    window._lastAudioB64 = null;
    status.textContent = 'Sent — waiting for HAL…';
  });

  // ── RECORDING ─────────────────────────────────────────────────────────
  btn.addEventListener('click', () => {
    if (isRecording) stopRecording();
    else startRecording();
  });

  function startRecording() {
    isRecording = true;
    btn.classList.add('recording');
    btn.textContent = '⏹️';
    audioChunks = [];
    window._lastAudioB64 = null;

    if (MODE === 'webspeech' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SR();
      recognition.lang = LANG;
      recognition.interimResults = true;
      recognition.continuous = false;
      status.textContent = 'Listening…';
      recognition.onresult = e => {
        let interim = '', final = '';
        for (let r of e.results) { if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript; }
        box.value = (final || interim).trim();
        sendBtn.disabled = box.value.length === 0;
      };
      recognition.onend = () => { stopRecording(); };
      recognition.onerror = (e) => { status.textContent = 'Mic error: '+e.error; stopRecording(); };
      recognition.start();
    } else {
      // Whisper mode — just record audio bytes
      navigator.mediaDevices.getUserMedia({audio:true}).then(stream => {
        status.textContent = 'Recording… click ⏹️ when done';
        mediaRecorder = new MediaRecorder(stream, {mimeType:'audio/webm'});
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = () => {
          stream.getTracks().forEach(t => t.stop());
          const blob = new Blob(audioChunks, {type:'audio/webm'});
          const reader = new FileReader();
          reader.onloadend = () => {
            window._lastAudioB64 = reader.result.split(',')[1];
            status.textContent = 'Recording ready — transcribing…';
            box.value = '…transcribing via ElevenLabs…';
            sendBtn.disabled = true;
            window.parent.postMessage({type:'hal_whisper_audio', audio: window._lastAudioB64}, '*');
          };
          reader.readAsDataURL(blob);
        };
        mediaRecorder.start();
      }).catch(e => { status.textContent = 'Mic access denied'; stopRecording(); });
    }
  }

  function stopRecording() {
    isRecording = false;
    btn.classList.remove('recording');
    btn.textContent = '🎙️';
    if (recognition) { try { recognition.stop(); } catch(e){} recognition = null; }
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    if (MODE === 'webspeech') status.textContent = box.value ? 'Edit transcript then send ↑' : 'Nothing heard — try again';
  }

  // ── RECEIVE transcript back from Streamlit (Whisper result) ───────────
  window.addEventListener('message', e => {
    if (e.data && e.data.type === 'hal_whisper_result') {
      box.value = e.data.text || '';
      sendBtn.disabled = box.value.trim().length === 0;
      status.textContent = 'Transcript ready — edit or send ↑';
    }
    if (e.data && e.data.type === 'hal_speaking') {
      status.textContent = 'HAL is speaking…';
    }
    if (e.data && e.data.type === 'hal_ready') {
      status.textContent = 'Click the mic to start recording';
    }
  });
})();
</script>
"""

_TTS_PLAY_HTML = """
<script>
(function(){{
  const text = {text_json};
  const lang = {lang_json};
  window.parent.postMessage({{type:'hal_speaking'}}, '*');
  if (window.speechSynthesis) {{
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = 0.95;
    u.pitch = 1.0;
    u.onend = () => window.parent.postMessage({{type:'hal_ready'}}, '*');
    window.speechSynthesis.speak(u);
  }}
}})();
</script>
"""

# ── HAL Avatar Face ───────────────────────────────────────────────────────────
# Canvas-rendered humanoid face. Pass state via window.HAL_AVATAR_STATE:
#   'idle' | 'listening' | 'thinking' | 'speaking'
_HAL_AVATAR_HTML = """
<style>
  body{{margin:0;background:#000}}
  #av{{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 0 6px;background:#000;border-radius:12px}}
  #lbl{{font-size:9px;letter-spacing:2px;color:#C9A96E55;font-family:monospace;text-transform:uppercase}}
</style>
<div id="av">
  <canvas id="fc" width="240" height="290"></canvas>
  <div id="lbl">HAL · {state_label}</div>
</div>
<script>
(function(){{
  const cv=document.getElementById('fc'), cx=cv.getContext('2d');
  const W=cv.width, H=cv.height, mx=W/2, my=H/2-8;
  let state='{init_state}', t=0;
  let blinkClock=0, nextBlink=3+Math.random()*2, blinkAmt=0;
  let scanY=0, scanDir=1, mouthWave=0, thinkAngle=0;
  const particles=Array.from({{length:22}},()=>({{
    angle:Math.random()*Math.PI*2,
    r:110+Math.random()*14,
    speed:(Math.random()-.5)*0.009,
    size:Math.random()*1.6+.4,
    alpha:Math.random()*0.45+0.08
  }}));

  window.addEventListener('message',e=>{{
    if(e.data&&e.data.hal_state) state=e.data.hal_state;
  }});
  if(window.HAL_AVATAR_STATE) state=window.HAL_AVATAR_STATE;

  function ac(a){{return state==='listening'?`rgba(93,202,165,${{a}})`:state==='thinking'?`rgba(100,170,255,${{a}})`:`rgba(201,169,110,${{a}})`}}

  function draw(){{
    cx.clearRect(0,0,W,H);
    const br=Math.sin(t*.38)*.011;
    cx.save(); cx.translate(mx,my); cx.scale(1+br,1+br);

    // halo
    const h=cx.createRadialGradient(0,0,75,0,0,130);
    h.addColorStop(0,ac(state==='speaking'?.15+Math.abs(Math.sin(t*6))*.1:.09));
    h.addColorStop(1,'rgba(0,0,0,0)');
    cx.fillStyle=h; cx.beginPath(); cx.arc(0,0,130,0,Math.PI*2); cx.fill();

    // neck
    cx.save(); cx.translate(0,110);
    const ng=cx.createLinearGradient(-16,0,16,0);
    ng.addColorStop(0,'#0A0806'); ng.addColorStop(.35,'#1C1610'); ng.addColorStop(.65,'#1C1610'); ng.addColorStop(1,'#0A0806');
    cx.fillStyle=ng; cx.beginPath(); cx.moveTo(-15,0); cx.lineTo(-18,46); cx.lineTo(18,46); cx.lineTo(15,0); cx.closePath(); cx.fill();
    cx.strokeStyle=ac(.12); cx.lineWidth=.4;
    [-6,0,6].forEach(x=>{{cx.beginPath();cx.moveTo(x,3);cx.lineTo(x,42);cx.stroke()}});
    cx.restore();

    // shoulders
    cx.save(); cx.translate(0,112);
    cx.fillStyle='#0D0B08'; cx.strokeStyle=ac(.2); cx.lineWidth=.6;
    cx.beginPath(); cx.moveTo(-18,44); cx.bezierCurveTo(-55,48,-80,38,-90,34); cx.lineTo(-98,50); cx.bezierCurveTo(-72,56,-44,52,-18,52); cx.closePath(); cx.fill(); cx.stroke();
    cx.beginPath(); cx.moveTo(18,44); cx.bezierCurveTo(55,48,80,38,90,34); cx.lineTo(98,50); cx.bezierCurveTo(72,56,44,52,18,52); cx.closePath(); cx.fill(); cx.stroke();
    cx.restore();

    // face oval
    cx.save(); cx.scale(1,1.11);
    const fg=cx.createRadialGradient(-10,-15,15,0,0,96);
    fg.addColorStop(0,'#1E1A14'); fg.addColorStop(.6,'#141008'); fg.addColorStop(1,'#0A0806');
    cx.fillStyle=fg; cx.beginPath(); cx.arc(0,0,96,0,Math.PI*2); cx.fill();
    cx.strokeStyle=ac(.28); cx.lineWidth=.8; cx.stroke();
    cx.restore();

    // brow
    cx.strokeStyle=ac(.1); cx.lineWidth=1.2;
    cx.beginPath(); cx.moveTo(-46,-38); cx.bezierCurveTo(-32,-46,-16,-48,0,-47); cx.bezierCurveTo(16,-48,32,-46,46,-38); cx.stroke();

    // EYES
    [[-30,0],[30,0]].forEach(([ex],idx)=>{{
      const eg=state==='thinking'?.88+Math.sin(t*3+idx)*.1:state==='listening'?.82+Math.sin(t*2)*.1:state==='speaking'?.78+Math.sin(t*5+idx)*.14:.72+Math.sin(t*.8+idx)*.05;
      const bs=blinkAmt>0?Math.max(.05,1-blinkAmt*6):1;
      cx.save(); cx.translate(ex,-13); cx.scale(1,bs);
      cx.fillStyle='rgba(0,0,0,.7)'; cx.beginPath(); cx.ellipse(0,0,17,10,0,0,Math.PI*2); cx.fill();
      [20,15,10].forEach((r,i)=>{{
        const g2=cx.createRadialGradient(0,0,0,0,0,r);
        g2.addColorStop(0,ac(eg*(.75-i*.18))); g2.addColorStop(1,'rgba(0,0,0,0)');
        cx.fillStyle=g2; cx.beginPath(); cx.arc(0,0,r,0,Math.PI*2); cx.fill();
      }});
      cx.fillStyle=ac(eg); cx.beginPath(); cx.arc(0,0,7,0,Math.PI*2); cx.fill();
      cx.fillStyle='#050302'; cx.beginPath(); cx.arc(0,0,3.5,0,Math.PI*2); cx.fill();
      cx.fillStyle='rgba(255,255,255,.5)'; cx.beginPath(); cx.arc(-1.5,-1.5,1.5,0,Math.PI*2); cx.fill();
      cx.strokeStyle=ac(.32); cx.lineWidth=.7;
      cx.beginPath(); cx.moveTo(-17,0); cx.bezierCurveTo(-9,-10,9,-10,17,0); cx.stroke();
      cx.beginPath(); cx.moveTo(-17,0); cx.bezierCurveTo(-9,8,9,8,17,0); cx.stroke();
      cx.restore();
    }});

    // think dot
    if(state==='thinking'){{ thinkAngle+=.05; const tx=Math.cos(thinkAngle)*22,ty=Math.sin(thinkAngle*.7)*9-13; cx.fillStyle=`rgba(100,170,255,${{.55+Math.sin(t*8)*.3}})`; cx.beginPath(); cx.arc(tx,ty,1.5,0,Math.PI*2); cx.fill(); }}

    // nose
    cx.strokeStyle=ac(.09); cx.lineWidth=.6;
    cx.beginPath(); cx.moveTo(-4,8); cx.bezierCurveTo(-6,22,-7,32,-10,38); cx.stroke();
    cx.beginPath(); cx.moveTo(4,8); cx.bezierCurveTo(6,22,7,32,10,38); cx.stroke();
    cx.beginPath(); cx.moveTo(-10,38); cx.bezierCurveTo(-6,43,6,43,10,38); cx.stroke();

    // cheeks
    cx.strokeStyle=ac(.06); cx.lineWidth=.5;
    cx.beginPath(); cx.moveTo(-58,8); cx.bezierCurveTo(-48,22,-36,34,-22,41); cx.stroke();
    cx.beginPath(); cx.moveTo(58,8); cx.bezierCurveTo(48,22,36,34,22,41); cx.stroke();

    // MOUTH
    const mY=62, mW=34;
    cx.save(); cx.translate(0,mY);
    if(state==='speaking'){{
      mouthWave+=.18;
      const op=Math.abs(Math.sin(mouthWave))*7+1.5;
      cx.strokeStyle=ac(.7); cx.lineWidth=1;
      cx.beginPath();
      for(let i=0;i<=mW*2;i++){{ const x=-mW+i,w=Math.sin(i*.14+mouthWave)*2; i===0?cx.moveTo(x,-op+w):cx.lineTo(x,-op+w); }}
      cx.stroke();
      cx.beginPath();
      for(let i=0;i<=mW*2;i++){{ const x=-mW+i,w=Math.sin(i*.14+mouthWave+Math.PI)*2; i===0?cx.moveTo(x,op+w):cx.lineTo(x,op+w); }}
      cx.stroke();
      cx.fillStyle='rgba(5,3,2,.85)'; cx.beginPath(); cx.ellipse(0,0,mW,op+2,0,0,Math.PI*2); cx.fill();
    }} else if(state==='listening'){{
      cx.strokeStyle=`rgba(93,202,165,${{.45+Math.sin(t*3)*.2}})`; cx.lineWidth=1.2;
      cx.beginPath();
      for(let i=0;i<=mW*2;i++){{ const x=-mW+i,w=Math.sin(i*.1+t*4)*2.2*Math.sin(t*1.4); i===0?cx.moveTo(x,w):cx.lineTo(x,w); }}
      cx.stroke();
    }} else {{
      const rc=Math.sin(t*.28)*.7;
      cx.strokeStyle=ac(.32); cx.lineWidth=.9;
      cx.beginPath(); cx.moveTo(-mW,rc); cx.bezierCurveTo(-mW*.5,rc+2.5,mW*.5,rc+2.5,mW,rc); cx.stroke();
      cx.fillStyle=ac(.38); cx.beginPath(); cx.arc(-mW,rc,1.2,0,Math.PI*2); cx.fill();
      cx.beginPath(); cx.arc(mW,rc,1.2,0,Math.PI*2); cx.fill();
    }}
    cx.restore();

    // jaw
    cx.strokeStyle=ac(.1); cx.lineWidth=.5;
    cx.beginPath(); cx.moveTo(-30,80); cx.bezierCurveTo(-14,96,14,96,30,80); cx.stroke();

    // scan line
    if(state==='thinking'){{
      scanY+=scanDir*1.4; if(scanY>90||scanY<-90) scanDir*=-1;
      cx.save(); cx.beginPath(); cx.arc(0,0,96,0,Math.PI*2); cx.clip();
      const sg=cx.createLinearGradient(0,scanY-5,0,scanY+5);
      sg.addColorStop(0,'rgba(100,170,255,0)'); sg.addColorStop(.5,'rgba(100,170,255,.16)'); sg.addColorStop(1,'rgba(100,170,255,0)');
      cx.fillStyle=sg; cx.fillRect(-100,scanY-5,200,10); cx.restore();
    }}

    // particles
    particles.forEach(p=>{{
      p.angle+=p.speed;
      const px=Math.cos(p.angle)*p.r, py=Math.sin(p.angle)*p.r*.82;
      if(Math.sqrt(px*px+py*py)>90){{
        cx.fillStyle=ac(p.alpha*(state==='speaking'?1.4:1));
        cx.beginPath(); cx.arc(px,py,p.size,0,Math.PI*2); cx.fill();
      }}
    }});

    // circuit accents
    cx.strokeStyle=ac(.05+Math.sin(t*.6)*.015); cx.lineWidth=.35;
    cx.beginPath(); cx.moveTo(-40,-60); cx.lineTo(-40,-52); cx.lineTo(-28,-52); cx.stroke();
    cx.beginPath(); cx.moveTo(40,-60); cx.lineTo(40,-52); cx.lineTo(28,-52); cx.stroke();
    cx.beginPath(); cx.moveTo(0,-74); cx.lineTo(0,-62); cx.stroke();

    cx.restore();

    // status ring
    const rp=state==='speaking'?Math.abs(Math.sin(t*6)):state==='listening'?.38+Math.sin(t*2)*.18:state==='thinking'?.38+Math.sin(t*4)*.25:.22+Math.sin(t)*.08;
    cx.strokeStyle=ac(rp); cx.lineWidth=1.5;
    cx.setLineDash(state==='thinking'?[5,3]:[]);
    cx.beginPath(); cx.arc(mx,H-16,8,0,Math.PI*2); cx.stroke();
    cx.setLineDash([]);
    cx.fillStyle=ac(.12); cx.beginPath(); cx.arc(mx,H-16,8,0,Math.PI*2); cx.fill();
  }}

  function loop(){{
    t+=.016;
    blinkClock+=.016;
    if(blinkClock>=nextBlink&&blinkAmt===0) blinkAmt=.01;
    if(blinkAmt>0){{ blinkAmt+=.1; if(blinkAmt>=1){{blinkAmt=0;blinkClock=0;nextBlink=2+Math.random()*4;}} }}
    draw();
    requestAnimationFrame(loop);
  }}
  loop();
}})();
</script>
"""


def _elevenlabs_stt(audio_bytes: bytes, api_key: str, language: str = "el") -> str:
    """Transcribe audio via ElevenLabs Scribe. Requires Speech to Text -> Access on the key."""
    import io
    import requests as req

    # Detect format from magic bytes (streamlit-mic-recorder may return WAV or WebM)
    if audio_bytes[:4] == b'RIFF':
        fname, mime = "audio.wav", "audio/wav"
    elif audio_bytes[:4] == b'\x1a\x45\xdf\xa3':
        fname, mime = "audio.webm", "audio/webm"
    elif audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb':
        fname, mime = "audio.mp3", "audio/mpeg"
    else:
        fname, mime = "audio.webm", "audio/webm"

    # Field name MUST be "file" (not "audio") — ElevenLabs API spec
    post_data = {"model_id": "scribe_v1"}
    if language and language != "auto":
        post_data["language_code"] = language

    try:
        resp = req.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": api_key},
            files={"file": (fname, io.BytesIO(audio_bytes), mime)},
            data=post_data,
            timeout=40,
        )
        resp.raise_for_status()
        return resp.json().get("text", "")
    except Exception as e:
        return f"[ElevenLabs STT error: {e}]"


def _whisper_transcribe(audio_bytes: bytes, openai_api_key: str, language: str = "el") -> str:
    """Send audio bytes to OpenAI Whisper API and return transcript."""
    import io
    import requests as req
    try:
        resp = req.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {openai_api_key}"},
            files={"file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm")},
            data={"model": "whisper-1", "language": language},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("text", "")
    except Exception as e:
        return f"[Whisper error: {e}]"


def _elevenlabs_tts(text: str, api_key: str, voice_id: str = "onwK4e9ZLuTAKqWW03F9") -> bytes | None:
    """Call ElevenLabs TTS and return MP3 bytes (or None on error)."""
    import requests as req
    try:
        resp = req.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.55, "similarity_boost": 0.80}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


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

When documents are provided, analyse them thoroughly before responding.
Respond in the language of the message. Be direct — produce outputs, not advice about producing them. For emails and letters, write them fully ready to send."""

    system_prompt_private = """You are HAL — the private AI assistant for Pantelis Kourbelas. In this private mode you have access to lodge and personal context.

LODGE: You assist as secretary for Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ) and ΚΛΕΙΣ ΑΛΗΘΕΙΑΣ αρ. 1 (A.A.S.R.). Always use Masonic ∴ notation. Style: contemporary Greek Tektonic — NOT archaic. Closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος. Lodge email: st.akropolis.84@gmail.com. Speech order: 18 levels (Μαθηταί → Μέγας Διδάσκαλος).

PERSONAL: Financial adviser, nurse, gym coach. Help with savings plans, retirement modelling, workout programmes, health monitoring.

When documents are provided, analyse them thoroughly before responding.
Never mix lodge content with business sessions. Respond in Greek unless asked otherwise."""

    system = system_prompt_private if is_private else system_prompt_business
    api_key = get_api_key() or st.session_state.get("api_key_input", "")

    # ── Upload key counter — incremented after send to reset the uploader ──
    if "upload_key_counter" not in st.session_state:
        st.session_state.upload_key_counter = 0

    # ── Document upload panel ──────────────────────────────────────────────
    st.markdown("""
    <style>
    .upload-hint { 
        font-size: 12px; color: #7A6A5A; 
        margin: -8px 0 8px; padding: 6px 10px;
        background: #FBF8F4; border-radius: 6px; 
        border-left: 3px solid #C9A96E;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.expander(
        "📎 Attach documents to next message",
        expanded=st.session_state.get("upload_panel_open", False)
    ):
        st.markdown(
            '<div class="upload-hint">'
            'Supported: <b>PDF</b> (text extracted), <b>images</b> (PNG/JPG/WEBP — analysed visually), '
            '<b>TXT / CSV</b>. Files attach to your <em>next</em> message only.'
            '</div>',
            unsafe_allow_html=True,
        )
        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            type=["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv"],
            accept_multiple_files=True,
            key=f"hal_upload_{st.session_state.upload_key_counter}",
            label_visibility="collapsed",
        )
        if uploaded_files:
            for uf in uploaded_files:
                size_str = f"{round(uf.size/1024, 1)} KB" if uf.size < 1024*1024 else f"{round(uf.size/1024/1024, 1)} MB"
                icon = "🖼️" if (uf.type or "").startswith("image/") else "📄"
                st.caption(f"{icon} **{uf.name}** · {size_str} · ready to attach")
        else:
            uploaded_files = []

    st.markdown("")

    # ── Chat history display ───────────────────────────────────────────────
    if not st.session_state.chat_history:
        st.info("HAL is ready. Type a message below — or attach documents above and ask HAL to analyse them.")
    else:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg.get("display", msg.get("content", "")))
                    for att in msg.get("attachments", []):
                        icon = "🖼️" if any(
                            att.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                        ) else "📄"
                        st.caption(f"{icon} {att}")
            else:
                st.chat_message("assistant").write(msg["content"])

    # ── Quick actions (only when chat is empty) ────────────────────────────
    if not st.session_state.chat_history:
        st.markdown("**Quick actions:**")
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
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": q,
                        "display": q,
                        "attachments": [],
                    })
                    st.rerun()

    # ── Chat input ─────────────────────────────────────────────────────────
    user_input = st.chat_input("Message HAL... (attach documents above to include them)")
    if user_input:
        # Build API content blocks (text + any uploaded files)
        api_content, attachment_names = _build_api_content(user_input, uploaded_files)

        # History entry — display text separate from api_content
        history_entry = {
            "role": "user",
            "display": user_input,
            "content": user_input,          # plain text fallback
            "attachments": attachment_names,
        }
        if attachment_names:
            history_entry["api_content"] = api_content  # rich content for API

        st.session_state.chat_history.append(history_entry)

        # Reset uploader for next message
        if attachment_names:
            st.session_state.upload_key_counter += 1
            st.session_state.upload_panel_open = False

        if not api_key:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "⚠️ No API key found. Add Claude_API_Key to your Streamlit secrets.",
            })
        else:
            with st.spinner("HAL is thinking..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)

                    # Build messages — use api_content when present, else plain string
                    messages = []
                    for m in st.session_state.chat_history:
                        if m["role"] == "user":
                            messages.append({
                                "role": "user",
                                "content": m.get("api_content") or m.get("content", ""),
                            })
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": m["content"],
                            })

                    # Use more tokens when documents are attached
                    max_tok = 4000 if attachment_names else 2000

                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=max_tok,
                        system=system,
                        messages=messages,
                    )
                    reply = response.content[0].text
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"⚠️ Error: {str(e)}",
                    })
        st.rerun()

    # ── Clear button ───────────────────────────────────────────────────────
    if st.session_state.chat_history:
        if st.button("🗑 Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.upload_key_counter += 1   # reset uploader too
            st.rerun()


def _render_avatar(state: str = "idle"):
    """Render HAL's animated face in the given state."""
    import streamlit.components.v1 as components
    state_labels = {
        "idle": "standby",
        "listening": "listening",
        "thinking": "processing",
        "speaking": "speaking",
    }
    html = _HAL_AVATAR_HTML.format(
        init_state=state,
        state_label=state_labels.get(state, "standby"),
    )
    components.html(html, height=320, scrolling=False)


def render_voice_chat():
    """HAL Voice — properly wired with streamlit-mic-recorder."""
    import anthropic
    import json
    import base64
    import streamlit.components.v1 as components

    try:
        from streamlit_mic_recorder import mic_recorder
        MIC_OK = True
    except ImportError:
        MIC_OK = False

    is_private = st.session_state.mode == "private"
    mode_label = "Private · Lodge & Personal" if is_private else "Business · Ashlar Insurance"
    st.markdown(f"## 🎙️ HAL Voice — {mode_label}")
    st.caption("Speak to HAL · HAL speaks back · Greek & English")

    api_key = get_api_key() or st.session_state.get("api_key_input", "")

    # ── Keys & settings ───────────────────────────────────────────────────
    el_key      = st.secrets.get("ELEVENLABS_API_KEY", "")
    openai_key  = st.secrets.get("OPENAI_API_KEY", "")
    el_voice    = "onwK4e9ZLuTAKqWW03F9"
    el_lang     = "el"
    lang_code   = "el-GR"
    stt_choice  = "ElevenLabs Scribe"

    with st.expander("⚙️ Voice settings", expanded=not bool(el_key)):
        scol1, scol2 = st.columns(2)
        with scol1:
            st.markdown("**ElevenLabs** (TTS + Scribe STT)")
            if not el_key:
                el_key = st.text_input(
                    "ElevenLabs API key", type="password", key="el_key_input",
                    help="Add ELEVENLABS_API_KEY to Streamlit secrets.",
                )
                st.caption("Enable: Text to Speech ✅  Speech to Text ✅")
            else:
                st.success("✅ ElevenLabs key loaded")
            el_voice = st.text_input(
                "Voice ID", value="onwK4e9ZLuTAKqWW03F9",
                help="Default: Daniel (multilingual). Find more at elevenlabs.io/voice-lab",
                key="el_voice_id",
            )
        with scol2:
            st.markdown("**Speech-to-text engine**")
            stt_options = []
            if el_key:
                stt_options.append("ElevenLabs Scribe")
            if openai_key:
                stt_options.append("OpenAI Whisper")
            if not stt_options:
                stt_options = ["ElevenLabs Scribe"]
            stt_choice = st.radio("STT engine", stt_options, key="stt_engine",
                help="Whisper is excellent for Greek. Needs OPENAI_API_KEY in secrets.")
            if not openai_key and len(stt_options) == 1:
                openai_key = st.text_input(
                    "OpenAI API key (for Whisper)", type="password", key="openai_key_input",
                    help="Add OPENAI_API_KEY to Streamlit secrets to enable Whisper.",
                )
            lang_sel  = st.selectbox("Language", ["el — Greek", "en — English", "auto"], index=0, key="voice_lang")
            el_lang   = lang_sel.split("—")[0].strip()
            lang_code = "el-GR" if el_lang == "el" else ("en-US" if el_lang == "en" else "el-GR")

    use_el      = bool(el_key)
    use_whisper = stt_choice == "OpenAI Whisper" and bool(openai_key)

    # ── System prompts ─────────────────────────────────────────────────────
    system_business = """You are HAL — the AI voice assistant for Pantelis Kourbelas, Ashlar Insurance, Athens.
VOICE MODE: Keep replies to 2-4 sentences only — they will be spoken aloud.
Specialise in international health insurance: Groupama, Generali, Ethniki, Morgan Price, NOW Health, Bupa Global.
Respond in the language spoken to you. Conversational tone — no bullet points, no markdown."""

    system_private = """You are HAL — private voice assistant for Pantelis Kourbelas.
VOICE MODE: Keep replies to 2-4 sentences only — they will be spoken aloud.
Lodge: Στ∴ ΑΚΡΟΠΟΛΙΣ 84. Personal: finance, health, gym.
Respond in Greek unless spoken to in English. Conversational — no bullet points."""

    system = system_private if is_private else system_business

    # ── Session state ──────────────────────────────────────────────────────
    for _k, _v in [("voice_history", []), ("voice_last_reply", ""), ("avatar_state", "idle")]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # ── Layout: avatar left, conversation right ────────────────────────────
    col_av, col_main = st.columns([1, 2], gap="medium")

    with col_av:
        _render_avatar(st.session_state.avatar_state)

    with col_main:
        chat_box = st.container(height=260)
        with chat_box:
            if not st.session_state.voice_history:
                st.info("🎙️ Use the mic below — HAL will respond in voice.")
            else:
                for msg in st.session_state.voice_history[-12:]:
                    st.chat_message("user" if msg["role"] == "user" else "assistant").write(msg["content"])

    st.divider()

    # ── Mic recorder (proper Streamlit component — returns bytes to Python) ──
    user_text = None

    if MIC_OK:
        st.markdown("**🎙️ Record your message**")
        audio = mic_recorder(
            start_prompt="🔴 Click to speak",
            stop_prompt="⏹️ Click to stop",
            just_once=True,
            use_container_width=True,
            key="hal_mic",
        )
        if audio and audio.get("bytes"):
            # Guard: only process each recording once (prevent rerun loops)
            audio_id = str(audio.get("id", id(audio["bytes"])))
            if audio_id != st.session_state.get("_last_audio_id", ""):
                st.session_state._last_audio_id = audio_id
                if use_whisper:
                    with st.spinner("Transcribing with OpenAI Whisper…"):
                        transcript = _whisper_transcribe(audio["bytes"], openai_key, el_lang)
                    if transcript and not transcript.startswith("[Whisper error"):
                        st.info(f"Heard: *{transcript}*")
                        user_text = transcript
                    else:
                        st.error(f"Whisper transcription failed: {transcript}")
                elif use_el:
                    with st.spinner("Transcribing with ElevenLabs Scribe…"):
                        transcript = _elevenlabs_stt(audio["bytes"], el_key, el_lang)
                    if transcript and not transcript.startswith("[ElevenLabs STT error"):
                        st.info(f"Heard: *{transcript}*")
                        user_text = transcript
                    else:
                        st.error(f"Transcription failed: {transcript}")
                        st.caption("Check that Speech to Text → Access is enabled in your ElevenLabs API key.")
                else:
                    st.warning("Add ELEVENLABS_API_KEY or OPENAI_API_KEY to Streamlit secrets to transcribe.")
    else:
        st.warning(
            "Install `streamlit-mic-recorder` to enable the mic button. "
            "Add it to requirements.txt and redeploy."
        )

    # ── Text / type fallback (always available) ────────────────────────────
    col_t, col_s = st.columns([5, 1])
    with col_t:
        typed = st.text_input(
            "type", label_visibility="collapsed",
            placeholder="Or type your message here…",
            key="voice_type_input",
        )
    with col_s:
        if st.button("Send", type="primary", use_container_width=True, key="voice_send_btn"):
            if typed.strip():
                user_text = typed.strip()

    # ── Audio file upload fallback ─────────────────────────────────────────
    with st.expander("📁 Upload audio file instead", expanded=False):
        af = st.file_uploader(
            "WAV / MP3 / WEBM / M4A / OGG",
            type=["wav", "mp3", "webm", "m4a", "ogg"],
            key="voice_audio_upload",
        )
        if af and st.button("Transcribe & Send", key="transcribe_file_btn"):
            if use_el:
                with st.spinner("Transcribing with ElevenLabs Scribe…"):
                    t2 = _elevenlabs_stt(af.read(), el_key, el_lang)
                if t2 and not t2.startswith("[ElevenLabs STT error"):
                    st.info(f"Heard: *{t2}*")
                    user_text = t2
                else:
                    st.error(t2)
            else:
                st.warning("Add ELEVENLABS_API_KEY first.")

    # ── Reset button — always visible when avatar is stuck ──────────────────
    if st.session_state.get("avatar_state") in ("thinking", "speaking"):
        if st.button("🔄 Reset HAL", key="voice_reset", help="Click if HAL appears frozen"):
            st.session_state.avatar_state = "idle"
            st.session_state._voice_processing = False
            st.rerun()

    # ── Process → Claude → TTS ─────────────────────────────────────────────
    if user_text and api_key and not st.session_state.get("_voice_processing"):
        st.session_state._voice_processing = True
        st.session_state.voice_history.append({"role": "user", "content": user_text})
        st.session_state.avatar_state = "thinking"

        with st.spinner("HAL is thinking…"):
            try:
                client_ai = anthropic.Anthropic(api_key=api_key)
                history_trimmed = st.session_state.voice_history[-10:]
                messages = [{"role": m["role"], "content": m["content"]}
                            for m in history_trimmed]
                response = client_ai.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=400,
                    system=system,
                    messages=messages,
                    timeout=30,
                )
                reply = response.content[0].text
                st.session_state.voice_history.append({"role": "assistant", "content": reply})
                st.session_state.voice_last_reply = reply
                st.session_state.avatar_state = "speaking"
                st.session_state._voice_processing = False

                if use_el:
                    tts_bytes = _elevenlabs_tts(reply, el_key, el_voice)
                    if tts_bytes:
                        st.audio(tts_bytes, format="audio/mp3", autoplay=True)
                    else:
                        st.warning("ElevenLabs TTS failed — using browser synthesis.")
                        components.html(
                            _TTS_PLAY_HTML.format(
                                text_json=json.dumps(reply),
                                lang_json=json.dumps(lang_code),
                            ),
                            height=0,
                        )
                else:
                    components.html(
                        _TTS_PLAY_HTML.format(
                            text_json=json.dumps(reply),
                            lang_json=json.dumps(lang_code),
                        ),
                        height=0,
                    )

            except Exception as e:
                st.session_state.avatar_state = "idle"
                st.session_state._voice_processing = False
                st.error(f"HAL error: {e}")

        st.rerun()

    elif user_text and not api_key:
        st.error("No Claude API key — add Claude_API_Key to Streamlit secrets.")

    if st.session_state.avatar_state == "speaking" and not user_text:
        st.session_state.avatar_state = "idle"

        st.session_state.avatar_state = "idle"

    # ── Controls ──────────────────────────────────────────────────────────
    if st.session_state.voice_last_reply:
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 Download last reply",
                st.session_state.voice_last_reply,
                file_name="hal_reply.txt",
                use_container_width=True,
            )
        with c2:
            if st.button("🗑 Clear conversation", use_container_width=True, key="clear_voice"):
                st.session_state.voice_history    = []
                st.session_state.voice_last_reply = ""
                st.session_state.avatar_state     = "idle"
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
    elif module == "voice_chat": render_voice_chat()
    elif module == "quotes":    render_quotes()
    elif module == "documents": render_documents()
    elif module == "comms":     render_comms()
    elif module == "commissions": render_commissions()
    elif module == "market":    render_market()
    elif module == "clients":   render_clients()
    elif module == "apps":      render_apps()
    elif module == "pets":      render_pets()
    else: render_business_home()

elif mode == "private" and st.session_state.private_unlocked:
    if module == "home":        render_private_home()
    elif module == "hal_chat":  render_hal_chat()
    elif module == "voice_chat": render_voice_chat()
    elif module == "lodge":     render_lodge()
    elif module == "minutes":   render_placeholder("Minutes & Documents", "📋")
    elif module == "attendance": render_placeholder("Attendance Tracker", "👥")
    elif module == "events":    render_placeholder("Events & Gala", "📅")
    elif module == "finance":   render_finance()
    elif module == "health":    render_health()
    elif module == "settings_private": render_placeholder("Private Settings", "🔑")
    else: render_private_home()
