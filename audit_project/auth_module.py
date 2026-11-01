import hashlib
import streamlit as st

USER_DB = {
    "auditor": {
        "password_hash": hashlib.sha256("audit123".encode()).hexdigest(),
        "role": "Auditor",
        "name": "Senior Auditor Lead",
        "dept": "Internal Audit & Risk Assurance"
    },
    "director": {
        "password_hash": hashlib.sha256("director123".encode()).hexdigest(),
        "role": "Director",
        "name": "Board of Directors",
        "dept": "Executive Audit Committee"
    }
}


def verify_password(password: str, hashed: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == hashed


def render_login_ui():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["user_role"] = None
        st.session_state["user_name"] = None
        st.session_state["user_dept"] = None

    if not st.session_state["authenticated"]:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #EAE0CC 0%, #DFD1B8 100%);
                    border: 1px solid #C4B08B; border-top: 4px solid #8B5A2B;
                    border-radius: 10px; padding: 22px 28px; margin-bottom: 18px;
                    box-shadow: 0 4px 12px rgba(92, 64, 35, 0.08); text-align: center;">
            <div style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: #7A5C3E; font-weight: 700;">
                ENTERPRISE RESOURCE PLANNING &amp; CAATs FORENSIC SUITE
            </div>
            <h2 style="margin: 6px 0 4px 0; color: #2B2520; font-weight: 800;">
                🔐 AuditLens AI Core — Portal Login
            </h2>
            <div style="font-size: 13px; color: #5C4D3C;">
                PT Suryamicrosystem • Financial Audit, ACL/CAATs Analytics &amp; Multi-Backend Assurance
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                username = st.text_input("Username ERP").strip().lower()
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("LOGIN", use_container_width=True, type="primary")

                if submit:
                    user_info = USER_DB.get(username)
                    if user_info and verify_password(password, user_info["password_hash"]):
                        st.session_state["authenticated"] = True
                        st.session_state["user_role"] = user_info["role"]
                        st.session_state["user_name"] = user_info["name"]
                        st.session_state["user_dept"] = user_info.get("dept", "Audit Division")
                        st.rerun()
                    else:
                        st.error("Username atau password salah.")
        st.stop()


def render_user_sidebar(show_logout: bool = False):
    role = st.session_state.get("user_role", "-")
    name = st.session_state.get("user_name", "-")
    dept = st.session_state.get("user_dept", "Audit Division")
    badge_bg = "#8B5A2B" if role == "Auditor" else "#4A5D6E"

    st.sidebar.markdown(f"""
    <div style="background-color: #DFD2BA; border: 1px solid #C2AE8B; border-left: 5px solid {badge_bg};
                border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;">
        <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; color: #6B5740; font-weight: 700;">
             SESSION IDENTITY
        </div>
        <div style="font-size: 15px; font-weight: 800; color: #2B2520; margin-top: 2px;">{name}</div>
        <div style="font-size: 12px; color: #5A4B3B; margin-bottom: 6px;">{dept}</div>
        <span style="background-color: {badge_bg}; color: #FFF8EE; padding: 2px 8px; border-radius: 4px;
                     font-size: 11px; font-weight: 700; letter-spacing: 0.6px;">
            ROLE: {role.upper()}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if show_logout:
        render_logout_sidebar()


def render_logout_sidebar():
    st.sidebar.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 LOGOUT", key="btn_erp_logout_bottom", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_role"] = None
        st.session_state["user_name"] = None
        st.session_state["user_dept"] = None
        st.session_state.pop("active_erp_module", None)
        st.rerun()
