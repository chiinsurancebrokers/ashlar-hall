"""
HAL — Heuristically Programmed Algorithmic Layer
Pantelis Kourbelas | Ashlar Insurance
Main Dashboard Entry Point
"""

import streamlit as st
import hashlib
import os

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
    st.caption("Active cases · Policy status · Renewal dates")
    st.info("📌 Connect to Google Sheets or upload a client CSV to begin tracking. Use the HAL Assistant to look up client cases by name.")

    st.markdown("**Known active cases (from HAL knowledge base):**")
    clients_data = [
        ("Konstantina Alexopoulou", "Bupa Global", "BI-6000-0113-6189", "Claim CL260306821932 — Formal complaint filed"),
        ("Katia Totikidou + Alexia", "Generali / Morgan Price", "—", "Comparison pending — waiting for decision"),
        ("Christos Iatropoulos", "Groupama + Bupa", "M000106069/1", "Bupa claim filled — awaiting processing"),
    ]
    for name, insurer, policy, status in clients_data:
        with st.expander(f"**{name}** — {insurer}"):
            st.markdown(f"**Policy ref:** {policy}  \n**Status:** {status}")


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
