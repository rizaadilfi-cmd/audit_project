import io
import os
import sqlite3
import tempfile
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from auth_module import render_login_ui, render_user_sidebar, render_logout_sidebar
from onboarding_module import render_onboarding_guide
from config_secrets import get_llm_config, get_n8n_webhook_url, get_smtp_config
from audit_engine import run_3way_matching, scan_journal_anomalies, extract_unstructured_file
from psak71_engine import calculate_psak71_ckpn
from llm_5c_extractor import extract_5c_from_text, summarize_uploaded_file_for_5c
from sankey_module import create_sankey_3way_matching
from excel_exporter_v2 import generate_full_audit_excel
from pptx_generator import generate_audit_pptx
from report_generator import generate_management_letter_pdf_bytes
from n8n_notifier import send_n8n_high_risk_alert
from email_sender import send_audit_report_email
from caats_engine import (
    format_rp,
    format_dataframe_currency,
    run_benfords_law_analysis,
    create_benford_chart,
    run_duplicate_detection,
    run_gap_detection,
    run_population_stratification,
    run_predictive_audit_automation,
    OutOfCoreCAATsEngine
)
from db_connector import MultiBackendDBConnector, POSTGRES_SUPABASE_DDL

# ---------------------------------------------------------
# KONFIGURASI HALAMAN UTAMA STREAMLIT (ERP WIDE MODE)
# ---------------------------------------------------------
st.set_page_config(
    page_title="AuditLens ERP & CAATs Core — PT Suryamicrosystem",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "audit_system.db"
CLIENT_NAME = "PT Suryamicrosystem"
PROJECT_NAME = "Audit Keuangan TA 2026"
DEFAULT_OPINION = "WDP (Wajar Dengan Pengecualian)"


# ---------------------------------------------------------
# POPUP MODAL DIALOG UNTUK SKEMA DDL SQL SUPABASE / POSTGRESQL
# ---------------------------------------------------------
if hasattr(st, "dialog"):
    @st.dialog("📜 Skema DDL SQL — Inisialisasi Tabel Supabase & PostgreSQL", width="large")
    def show_ddl_sql_popup():
        st.markdown(
            "Salin dan jalankan skrip **DDL SQL** berikut pada **Supabase SQL Editor** atau "
            "**pgAdmin / psql** untuk menyiapkan skema tabel relasional `projects` dan `audit_findings` "
            "beserta indeks B-Tree-nya:"
        )
        st.code(POSTGRES_SUPABASE_DDL, language="sql")
        st.info(
            "💡 Setelah DDL dieksekusi di Supabase/PostgreSQL, setiap temuan audit yang disimpan dari "
            "Modul 1, Modul 2, maupun Modul 3 akan otomatis tersinkronisasi secara real-time."
        )
else:
    def show_ddl_sql_popup():
        st.code(POSTGRES_SUPABASE_DDL, language="sql")


# ---------------------------------------------------------
# ENTERPRISE ERP DOMINANT BEIGE THEME CSS
# ---------------------------------------------------------
def inject_erp_beige_theme():
    st.markdown("""
    <style>
        /* Global App Background - Warm Sand Beige */
        .stApp {
            background-color: #F7F3EA;
            color: #2B2520;
        }
        /* Sidebar - Rich Warm Beige */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #EAE0CC 0%, #DFD2B8 100%);
            border-right: 2px solid #C8B79B;
        }
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] label {
            color: #2B2520 !important;
        }
        /* Top ERP Command Ribbon */
        .erp-top-ribbon {
            background: linear-gradient(90deg, #3A2A1D 0%, #5C4028 55%, #7A5432 100%);
            color: #F7F3EA;
            padding: 12px 20px;
            border-radius: 8px;
            border-bottom: 3px solid #C5A059;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 14px;
            box-shadow: 0 3px 10px rgba(58, 42, 29, 0.15);
        }
        .erp-ribbon-title {
            font-size: 1.18rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: #FAF6EE;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .erp-ribbon-badges {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        .erp-pill {
            background: rgba(247, 243, 234, 0.14);
            border: 1px solid #C5A059;
            color: #FAF6EE;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.74rem;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        .erp-pill-active {
            background: #C5A059;
            color: #231A12;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.74rem;
            font-weight: 800;
        }
        /* ERP Sub-header Bar */
        .erp-module-bar {
            background: linear-gradient(90deg, #EFE7D6 0%, #E5D8C0 100%);
            border: 1px solid #C8B79B;
            border-left: 5px solid #8B5A2B;
            padding: 10px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .erp-module-bar-title {
            font-weight: 800;
            color: #3A2A1D;
            font-size: 0.96rem;
        }
        .erp-module-bar-meta {
            font-size: 0.78rem;
            color: #6E5A44;
            font-weight: 600;
        }
        /* Modern Interactive Sidebar Navigation Cards */
        .nav-header-box {
            background: linear-gradient(90deg, #5C4028 0%, #8B5A2B 100%);
            color: #FAF6EE;
            padding: 7px 12px;
            border-radius: 6px;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 8px;
            border-left: 4px solid #C5A059;
        }
        section[data-testid="stSidebar"] .stButton > button {
            text-align: left !important;
            justify-content: flex-start !important;
            border-radius: 7px !important;
            padding: 10px 14px !important;
            font-size: 0.85rem !important;
            transition: all 0.18s ease-in-out !important;
            margin-bottom: 4px !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #8B5A2B 0%, #5C3A1B 100%) !important;
            color: #FAF6EE !important;
            border: 1px solid #C5A059 !important;
            border-left: 5px solid #C5A059 !important;
            box-shadow: 0 3px 8px rgba(58, 42, 29, 0.22) !important;
            font-weight: 800 !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
            background: rgba(250, 246, 238, 0.78) !important;
            color: #3A2A1D !important;
            border: 1px solid #C8B79B !important;
            border-left: 4px solid #8B5A2B !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
            background: #EFE4CE !important;
            border-left: 5px solid #5C3A1B !important;
            transform: translateX(2px);
        }
        /* Metric Cards - ERP Beige Panel Style */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #FAF6EE 0%, #F1E9D8 100%);
            border: 1px solid #D2C3AA;
            border-top: 3px solid #8B5A2B;
            border-radius: 8px;
            padding: 12px 16px;
            box-shadow: 0 2px 6px rgba(92, 64, 40, 0.07);
        }
        div[data-testid="stMetricLabel"] {
            font-weight: 700 !important;
            color: #6B5640 !important;
            text-transform: uppercase;
            font-size: 0.74rem !important;
            letter-spacing: 0.4px;
        }
        div[data-testid="stMetricValue"] {
            color: #2B2520 !important;
            font-weight: 800 !important;
        }
        /* Tabs Styling */
        button[data-baseweb="tab"] {
            background-color: #EAE0CC !important;
            border: 1px solid #C8B79B !important;
            border-bottom: none !important;
            border-radius: 6px 6px 0 0 !important;
            margin-right: 4px !important;
            padding: 8px 16px !important;
            color: #4A3728 !important;
            font-weight: 700 !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #8B5A2B !important;
            color: #FAF6EE !important;
            border-color: #6E451F !important;
        }
        /* Primary & Secondary Buttons in Main Area */
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {
            background: linear-gradient(90deg, #8B5A2B 0%, #6E451F 100%) !important;
            color: #FAF6EE !important;
            border: 1px solid #5A3717 !important;
            font-weight: 700 !important;
        }
        .stDownloadButton > button {
            background-color: #EFE7D6 !important;
            color: #3A2A1D !important;
            border: 1px solid #B8A382 !important;
            font-weight: 700 !important;
        }
        .stDownloadButton > button:hover {
            background-color: #8B5A2B !important;
            color: #FAF6EE !important;
            border-color: #6E451F !important;
        }
        /* Expanders & Containers */
        details[data-testid="stExpander"] {
            background-color: #FAF6EE;
            border: 1px solid #D2C3AA;
            border-radius: 7px;
        }
        .erp-info-panel {
            background-color: #FAF6EE;
            border: 1px solid #D2C3AA;
            border-left: 4px solid #8B5A2B;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 0.86rem;
            color: #3A2A1D;
        }
        .erp-card-box {
            background: linear-gradient(145deg, #FAF6EE 0%, #F2E9D8 100%);
            border: 1px solid #D2C3AA;
            border-top: 3px solid #8B5A2B;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
        }
        .erp-lock-panel {
            background: linear-gradient(135deg, #F5EBD6 0%, #EADBC0 100%);
            border: 1px solid #C5A059;
            border-left: 5px solid #8B5A2B;
            padding: 14px 18px;
            border-radius: 7px;
            color: #3A2A1D;
            font-size: 0.88rem;
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# INISIALISASI DATABASE & DATA BAWAAN
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if os.path.exists("schema.sql"):
        with open("schema.sql", "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
    else:
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_name TEXT,
            audit_period TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER DEFAULT 1,
            area TEXT NOT NULL,
            condition TEXT NOT NULL,
            criteria TEXT NOT NULL,
            cause TEXT NOT NULL,
            effect TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            risk_level TEXT CHECK(risk_level IN ('HIGH', 'MEDIUM', 'LOW')),
            management_response TEXT DEFAULT '-',
            pic TEXT DEFAULT '-',
            target_date TEXT DEFAULT '-',
            status TEXT DEFAULT 'OPEN'
        );
        """)

    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO projects (project_name, client_name, audit_period) VALUES (?, ?, ?)",
            (PROJECT_NAME, CLIENT_NAME, "2026")
        )

    cursor.execute("SELECT COUNT(*) FROM audit_findings")
    if cursor.fetchone()[0] == 0:
        initial_findings = [
            (
                1,
                "Kas & Bank",
                "Pengeluaran petty cash sebesar Rp. 65.000.000 dilakukan tanpa otorisasi Direktur Keuangan.",
                "SOP-FIN-004 Batas maksimal transaksi petty cash adalah Rp. 5.000.000.",
                "Pemegang kas menghindari proses approval berjenjang untuk percepatan operasional.",
                "Potensi penyalahgunaan dana kas kecil dan risiko ketidakpatuhan pengendalian internal.",
                "Batasi limit petty cash maks. Rp. 5.000.000 dan wajibkan dual verification e-banking.",
                "HIGH",
                "Manajemen setuju dan memperbarui SOP Petty Cash.",
                "Spv. Finance",
                "15 Nov 2026",
                "IN_PROGRESS"
            ),
            (
                1,
                "Piutang (AR)",
                "Aging AR > 90 hari meningkat signifikan tanpa pencatatan cadangan kerugian piutang (CKPN).",
                "PSAK 71 / IFRS 9 mewajibkan pembentukan Expected Credit Loss (ECL) atas piutang tertunggak.",
                "Evaluasi kolektibilitas pelanggan belum diintegrasikan secara berkala pada penutupan buku bulanan.",
                "Nilai piutang bersih pada neraca berpotensi overstated (lebih saji).",
                "Lakukan penagihan intensif dan bentuk CKPN sesuai matriks ECL PSAK 71.",
                "MEDIUM",
                "Tim Credit Control akan menerbitkan Surat Tagihan ke-3.",
                "Mgr. AR",
                "30 Nov 2026",
                "OPEN"
            ),
            (
                1,
                "Beban Operasional",
                "Klaim biaya transportasi operasional tidak melampirkan bukti kuitansi resmi.",
                "SOP-GA-012 mengharuskan lampiran bukti pembayaran resmi untuk setiap reimbursement.",
                "Verifikasi dokumen fisik oleh staf admin kurang ketelitian sebelum pengajuan pencairan.",
                "Risiko pembebanan biaya tidak valid dan koreksi fiskal PPh/PPN.",
                "Terapkan penggunaan voucher korporat e-hailing resmi PT Suryamicrosystem.",
                "LOW",
                "Akan disosialisasikan ke seluruh departemen.",
                "HR & GA",
                "10 Nov 2026",
                "CLOSED"
            )
        ]
        cursor.executemany("""
            INSERT INTO audit_findings (
                project_id, area, condition, criteria, cause, effect,
                recommendation, risk_level, management_response, pic, target_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_findings)

    conn.commit()
    conn.close()


def refresh_audit_engines():
    """
    Menghitung ulang seluruh hasil 3-Way Matching dan Scan Anomali Jurnal
    setiap kali data diunggah atau diperbarui agar semua modul saling terhubung otomatis.
    """
    if "df_po" in st.session_state and "df_rr" in st.session_state and "df_inv" in st.session_state:
        st.session_state["res_matching"] = run_3way_matching(
            st.session_state["df_po"], st.session_state["df_rr"], st.session_state["df_inv"]
        )
    if "df_gl" in st.session_state:
        st.session_state["res_anomalies"] = scan_journal_anomalies(st.session_state["df_gl"])


def ensure_default_datasets():
    """
    Memuat dataset sampel (dari sample_audit_150_rows.xlsx jika ada) ke dalam session_state
    agar seluruh modul (Predictive Audit, 3-Way Matching, PSAK 71, CAATs, Sankey) langsung siap.
    """
    if "datasets_loaded" in st.session_state:
        return

    excel_150 = "sample_audit_150_rows.xlsx"
    if os.path.exists(excel_150):
        try:
            st.session_state["df_po"] = pd.read_excel(excel_150, sheet_name="PO_Data")
            st.session_state["df_rr"] = pd.read_excel(excel_150, sheet_name="RR_Data")
            st.session_state["df_inv"] = pd.read_excel(excel_150, sheet_name="Invoice_Data")
            st.session_state["df_gl"] = pd.read_excel(excel_150, sheet_name="GL_Data")
            st.session_state["df_ar"] = pd.read_excel(excel_150, sheet_name="AR_Aging_Data")
            refresh_audit_engines()
            st.session_state["datasets_loaded"] = True
            return
        except Exception:
            pass

    st.session_state["df_po"] = pd.DataFrame({
        'po_number': ['PO-2026-001', 'PO-2026-002', 'PO-2026-003'],
        'item_code': ['RAW-MAT-01', 'RAW-MAT-02', 'PACK-BOX-01'],
        'qty': [100, 50, 500],
        'unit_price_x': [150000, 200000, 12000]
    })
    st.session_state["df_rr"] = pd.DataFrame({
        'po_number': ['PO-2026-001', 'PO-2026-002', 'PO-2026-003'],
        'item_code': ['RAW-MAT-01', 'RAW-MAT-02', 'PACK-BOX-01'],
        'qty_received': [100, 40, 500]
    })
    st.session_state["df_inv"] = pd.DataFrame({
        'po_number': ['PO-2026-001', 'PO-2026-002', 'PO-2026-003'],
        'item_code': ['RAW-MAT-01', 'RAW-MAT-02', 'PACK-BOX-01'],
        'qty_billed': [100, 50, 500],
        'unit_price_y': [150000, 200000, 15000]
    })
    st.session_state["df_gl"] = pd.DataFrame({
        'journal_id': ['J-101', 'J-102', 'J-103'],
        'posting_date': ['2026-10-01', '2026-10-02', '2026-10-03'],
        'posting_time': ['14:20:00', '23:15:00', '02:10:00'],
        'account_code': ['5001-HPP', '6002-MISC', '5001-HPP'],
        'debit': [1500000, 50000000, 10000000],
        'credit': [0, 0, 0],
        'created_by': ['Fin_StaffA', 'Fin_StaffB', 'Fin_StaffC'],
        'approved_by': ['Fin_SpvX', 'Fin_StaffB', 'Fin_StaffC']
    })
    st.session_state["df_ar"] = pd.DataFrame({
        'invoice_number': ['INV-AR-001', 'INV-AR-002', 'INV-AR-003', 'INV-AR-004', 'INV-AR-005'],
        'customer_name': ['PT Client Alfa', 'PT Client Beta', 'CV Client Gamma', 'PT Client Delta', 'PT Client Eka'],
        'due_date': ['2026-11-01', '2026-10-15', '2026-09-20', '2026-08-10', '2026-05-01'],
        'amount': [85000000, 45000000, 30000000, 25000000, 15000000]
    })
    refresh_audit_engines()
    st.session_state["datasets_loaded"] = True


inject_erp_beige_theme()
init_db()
ensure_default_datasets()

# ---------------------------------------------------------
# AUTENTIKASI PENGGUNA & PROFIL SIDEBAR (TANPA LOGOUT DI ATAS)
# ---------------------------------------------------------
render_login_ui()
render_user_sidebar(show_logout=False)

# ---------------------------------------------------------
# INTERACTIVE ONBOARDING GUIDE (5 STEP TOUR)
# ---------------------------------------------------------
render_onboarding_guide()

# ---------------------------------------------------------
# STATE KONFIGURASI SISTEM (AI ENGINE, DB BACKEND, WEBHOOK)
# ---------------------------------------------------------
user_role = st.session_state.get("user_role")
llm_cfg = get_llm_config()

if "ai_engine_settings" not in st.session_state:
    init_prov = llm_cfg.get("provider", "gemini")
    st.session_state["ai_engine_settings"] = {
        "provider_label": "Gemini (Google)" if init_prov == "gemini" else "Claude (Anthropic)",
        "provider_code": init_prov,
        "gemini_api_key": llm_cfg.get("gemini_api_key", ""),
        "anthropic_api_key": llm_cfg.get("anthropic_api_key", ""),
        "n8n_webhook_url": get_n8n_webhook_url()
    }

if "db_backend_config" not in st.session_state:
    st.session_state["db_backend_config"] = {
        "backend_type": "sqlite",
        "sqlite_path": DB_NAME,
        "pg_dsn": "",
        "pg_host": "db.project-ref.supabase.co",
        "pg_port": 5432,
        "pg_database": "postgres",
        "pg_user": "postgres",
        "pg_password": "",
        "pg_sslmode": "require",
        "supabase_url": "",
        "supabase_key": ""
    }

ai_settings = st.session_state["ai_engine_settings"]
selected_provider = ai_settings["provider_label"]
provider_code = ai_settings["provider_code"]
user_api_key = ai_settings["anthropic_api_key"] if provider_code == "claude" else ai_settings["gemini_api_key"]
n8n_webhook_url = ai_settings["n8n_webhook_url"]

# ---------------------------------------------------------
# REVISI 04: INTERACTIVE MODERN ERP MODULE NAVIGATOR
# & MODUL "⚙️ PENGATURAN" + TOMBOL LOGOUT DI PALING BAWAH
# ---------------------------------------------------------
MODULE_DEFINITIONS = [
    {
        "id": "1. LLM 5C Extractor & Ingestion",
        "icon": "📦",
        "label": "1. AI 5C & Data Gateway",
        "desc": "Structured ERP, Multimodal & Out-of-Core"
    },
    {
        "id": "2. PSAK 71 & ACL/CAATs Engine",
        "icon": "📊",
        "label": "2. PSAK 71 & ACL/CAATs",
        "desc": "AR Aging, 3-Way Match, Benford, Gaps"
    },
    {
        "id": "3. Audit Workbench (5C & Multi-DB)",
        "icon": "📝",
        "label": "3. Audit Workbench (5C)",
        "desc": "Kertas Kerja 5C, Action Plan & Follow-Up"
    },
    {
        "id": "4. Client Executive Dashboard & Reports",
        "icon": "🏛️",
        "label": "4. Executive Dashboard",
        "desc": "KPI Direksi, Sankey Diagram & Deliverables"
    },
    {
        "id": "5. Pengaturan",
        "icon": "⚙️",
        "label": "5. Pengaturan Sistem",
        "desc": "AI Engine Configuration & Multi-Backend DB"
    }
]

if user_role == "Auditor":
    allowed_modules = MODULE_DEFINITIONS
else:
    allowed_modules = [m for m in MODULE_DEFINITIONS if m["id"] == "4. Client Executive Dashboard & Reports"]

allowed_ids = [m["id"] for m in allowed_modules]
if "active_erp_module" not in st.session_state or st.session_state["active_erp_module"] not in allowed_ids:
    st.session_state["active_erp_module"] = allowed_ids[0]

st.sidebar.markdown('<div class="nav-header-box">🧭 MODULE NAVIGATOR</div>', unsafe_allow_html=True)

for mod_item in allowed_modules:
    is_active = (st.session_state["active_erp_module"] == mod_item["id"])
    btn_text = f"{mod_item['icon']} {mod_item['label']}"
    if st.sidebar.button(
        btn_text,
        key=f"nav_btn_{mod_item['id']}",
        type="primary" if is_active else "secondary",
        use_container_width=True,
        help=mod_item["desc"]
    ):
        st.session_state["active_erp_module"] = mod_item["id"]
        st.rerun()

# Indikator ringkas modul aktif pada sidebar
active_mod_obj = next((m for m in allowed_modules if m["id"] == st.session_state["active_erp_module"]), allowed_modules[0])
st.sidebar.caption(f"📍 **Aktif:** {active_mod_obj['desc']}")

# Render Tombol LOGOUT di bagian PALING BAWAH Sidebar (Revisi 04)
render_logout_sidebar()

menu = st.session_state["active_erp_module"]

# Inisialisasi konektor aktif
active_db_connector = MultiBackendDBConnector(st.session_state["db_backend_config"])
active_backend_name = st.session_state["db_backend_config"].get("backend_type", "sqlite").upper()

# ---------------------------------------------------------
# REVISI 01: TOP ERP COMMAND HEADER RIBBON
# (Hide technical badges from ROLE: DIRECTOR)
# ---------------------------------------------------------
total_rows_loaded = (
    len(st.session_state.get("df_po", []))
    + len(st.session_state.get("df_rr", []))
    + len(st.session_state.get("df_inv", []))
    + len(st.session_state.get("df_gl", []))
    + len(st.session_state.get("df_ar", []))
)

if user_role == "Auditor":
    ribbon_badges_html = (
        f'<span class="erp-pill">MODUL: GRC-AUDIT-2026</span>'
        f'<span class="erp-pill">DB ENGINE: {active_backend_name}</span>'
        f'<span class="erp-pill">IN-MEMORY BUFFER: {total_rows_loaded:,} ROWS</span>'
        f'<span class="erp-pill">CAATs ENGINE: ACL OUT-OF-CORE READY</span>'
        f'<span class="erp-pill-active">ROLE: {str(user_role).upper()}</span>'
    )
else:
    # REVISI 01: Hide MODUL, DB ENGINE, IN-MEMORY BUFFER, CAATs ENGINE dari ROLE: DIRECTOR
    ribbon_badges_html = f'<span class="erp-pill-active">ROLE: {str(user_role).upper()}</span>'

st.markdown(f"""
<div class="erp-top-ribbon">
    <div class="erp-ribbon-title">
        <span>🏛️ AUDITLENS ENTERPRISE ERP & CAATs CORE</span>
        <span style="font-weight:400; font-size:0.88rem; color:#DFD1B8;">| {CLIENT_NAME}</span>
    </div>
    <div class="erp-ribbon-badges">
        {ribbon_badges_html}
    </div>
</div>
""", unsafe_allow_html=True)

if user_role != "Auditor":
    st.markdown("""
    <div class="erp-info-panel">
        <b>👁️ Mode Akses Eksekutif (Read-Only Director View):</b> Anda masuk sebagai <b>Board of Directors</b>.
        Tampilan dikalibrasi khusus untuk pemantauan KPI Eksekutif, Visualisasi Alur Dana Sankey 3-Way Matching, dan Distribusi Risiko.
        Konfigurasi Sistem, CAATs Workbench, dan Ekspor Deliverable Resmi dikelola secara eksklusif oleh <b>Internal/External Auditor</b>.
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# MODUL 1: AI 5C EXTRACTOR, MULTIMODAL OCR & DATA GATEWAY
# (Termasuk Opsi 1 Sangat Terstruktur + Prediktif, Opsi 2 Central Sub-Ledger,
#  Ekstraksi AI 5C Multimodal, & Out-of-Core Zero-RAM Engine)
# =========================================================
if menu == "1. LLM 5C Extractor & Ingestion":
    st.markdown("""
    <div class="erp-module-bar">
        <span class="erp-module-bar-title">📦 MODUL 01 // AI 5C EXTRACTOR, MULTIMODAL OCR &amp; MULTI-BACKEND DATA GATEWAY</span>
        <span class="erp-module-bar-meta">TCODE: AL_INGEST_5C | ENTITAS: PT SURAMICROSYSTEM</span>
    </div>
    """, unsafe_allow_html=True)

    tab_opt1, tab_opt2, tab_ai, tab_ooc = st.tabs([
        "1️⃣ Opsi 1: Input Data Sangat Terstruktur & Automasi Prediktif",
        "2️⃣ Opsi 2: Central Data Ingestion (ERP Sub-Ledger & Multimodal Input)",
        "🤖 Ekstraksi Otomatis 5C (Teks, Excel/CSV, PDF, DOCX & Gambar)",
        "🚀 Out-of-Core Zero-RAM Engine (Miliaran Baris / >200MB)"
    ])

    # ---------------------------------------------------------
    # REVISI 03 - OPSI 1: INPUT DATA SANGAT TERSTRUKTUR & AUTOMASI PREDIKTIF
    # ---------------------------------------------------------
    with tab_opt1:
        st.subheader("1️⃣ Opsi 1: Input Data Sangat Terstruktur & Automasi Analisis Prediktif Audit")
        st.markdown("""
        <div class="erp-info-panel">
            <b>Fokus Input Data Sangat Terstruktur:</b> Basis data relasional (SQLite / PostgreSQL / Supabase), log transaksi,
            file teks terformat (CSV / TSV / TXT), buku besar (<i>General Ledger</i>), atau ekstraksi tabel langsung dari sistem <b>ERP (SAP / Oracle / Odoo)</b>.<br>
            Begitu data dimasukkan, sistem secara otomatis menjalankan <b>Automasi Analisis Prediktif (Predictive Audit Scoring)</b> untuk menyeleksi dan mengambil populasi transaksi berisiko tinggi yang dibutuhkan untuk audit.
        </div>
        """, unsafe_allow_html=True)

        src_col1, src_col2 = st.columns([1, 1])
        with src_col1:
            structured_mode = st.radio(
                "Pilih Saluran Input Data Sangat Terstruktur",
                options=[
                    "📁 Unggah File Terstruktur ERP (Excel / CSV / Log Transaksi)",
                    "🔌 Tarik Langsung dari Sistem Terhubung ERP / Basis Data Relasional"
                ],
                key="rad_structured_mode"
            )

        df_structured_in = pd.DataFrame()
        source_name_label = ""

        if "Unggah File" in structured_mode:
            with src_col2:
                struct_file = st.file_uploader(
                    "Unggah Berkas Tabel Terstruktur (.xlsx, .xls, .csv, .txt, .log)",
                    type=["xlsx", "xls", "csv", "txt", "log"],
                    key="up_structured_opt1"
                )
            if struct_file is not None:
                source_name_label = struct_file.name
                fname_low = struct_file.name.lower()
                try:
                    if fname_low.endswith((".csv", ".txt", ".log")):
                        df_structured_in = pd.read_csv(struct_file, sep=None, engine="python")
                    else:
                        xls = pd.ExcelFile(struct_file)
                        chosen_sheet = st.selectbox("Pilih Sheet Tabel ERP", xls.sheet_names, key="sel_sheet_opt1")
                        df_structured_in = pd.read_excel(struct_file, sheet_name=chosen_sheet)
                        source_name_label = f"{struct_file.name} [{chosen_sheet}]"
                except Exception as e:
                    st.error(f"Gagal membaca berkas terstruktur: {e}")
        else:
            with src_col2:
                erp_Preset = st.selectbox(
                    "Pilih Tabel Relasional / Stream Sistem ERP Terhubung",
                    options=[
                        "ERP SAP BSEG/BKPF — General Ledger Journal Stream (Active Session)",
                        "ERP Procurement EKKO/EKPO — Purchase Order & Invoice Stream",
                        "ERP Finance BSID — Accounts Receivable (AR Aging) Stream",
                        "ERP Logistics MKPF — Receiving Report (RR) Log Stream",
                        "SQL Query Kustom ke Basis Data Relasional Aktif"
                    ],
                    key="sel_erp_stream_opt1"
                )
            if "General Ledger" in erp_Preset:
                df_structured_in = st.session_state.get("df_gl", pd.DataFrame()).copy()
                source_name_label = "SAP_GL_Journal_Stream"
            elif "Purchase Order" in erp_Preset:
                df_structured_in = st.session_state.get("df_po", pd.DataFrame()).copy()
                source_name_label = "SAP_PO_Procurement_Stream"
            elif "Accounts Receivable" in erp_Preset:
                df_structured_in = st.session_state.get("df_ar", pd.DataFrame()).copy()
                source_name_label = "SAP_AR_SubLedger_Stream"
            elif "Receiving Report" in erp_Preset:
                df_structured_in = st.session_state.get("df_rr", pd.DataFrame()).copy()
                source_name_label = "SAP_RR_Logistics_Stream"
            else:
                custom_sql = st.text_input(
                    "Masukkan Query SQL Relasional",
                    value="SELECT * FROM audit_findings ORDER BY id DESC"
                )
                if st.button("⚡ Tarik Data SQL & Jalankan Analisis Prediktif", type="primary"):
                    try:
                        conn = sqlite3.connect(DB_NAME)
                        df_structured_in = pd.read_sql_query(custom_sql, conn)
                        conn.close()
                        source_name_label = "Relational_DB_SQL_Query"
                    except Exception as e:
                        st.error(f"Eksekusi SQL gagal: {e}")

        if not df_structured_in.empty:
            pred_res = run_predictive_audit_automation(df_structured_in, source_label=source_name_label or "ERP Stream")
            st.session_state["last_predictive_result"] = pred_res

            # Sinkronkan otomatis ke state modul terkait apabila domain cocok
            t_key = pred_res.get("target_state_key")
            if t_key in ("df_gl", "df_po", "df_rr", "df_inv", "df_ar"):
                st.session_state[t_key] = df_structured_in
                refresh_audit_engines()

        if "last_predictive_result" in st.session_state:
            pr = st.session_state["last_predictive_result"]
            if "error" not in pr:
                st.markdown("##### 🤖 Hasil Automasi Analisis Prediktif & Ekstraksi Sampel Audit")
                pm1, pm2, pm3, pm4, pm5 = st.columns(5)
                pm1.metric("Domain Terdeteksi", pr["domain_detected"].split("(")[0].strip())
                pm2.metric("Total Populasi Data", f"{pr['total_rows']:,} Baris")
                pm3.metric("Total Nilai Populasi", pr["total_value_rp"])
                pm4.metric("Rata-Rata per Transaksi", pr["mean_value_rp"])
                pm5.metric(
                    "Sampel Wajib Audit (High/Med)",
                    f"{pr['audit_sample_count']} Transaksi",
                    delta=f"Eksposur: {pr['audit_sample_exposure_rp']}",
                    delta_color="inverse"
                )

                p_tab1, p_tab2 = st.tabs([
                    f"🎯 Data Prioritas Hasil Seleksi Prediktif ({pr['audit_sample_count']} Baris Wajib Audit)",
                    f"📋 Populasi Lengkap Terformat ({pr['total_rows']:,} Baris)"
                ])
                with p_tab1:
                    st.caption(
                        "Daftar transaksi di bawah ini telah diseleksi otomatis oleh algoritma prediktif berdasarkan "
                        "Z-Score Outlier, Round-Sum, Off-Hours Posting, Konflik SoD, dan Duplikasi untuk langsung diaudit:"
                    )
                    st.dataframe(pr["df_audit_targets"], use_container_width=True)
                with p_tab2:
                    st.dataframe(pr["df_scored"], use_container_width=True)

                act_c1, act_c2 = st.columns(2)
                with act_c1:
                    if st.button("🤖 Kirim Temuan Prediktif ke Form 5C & AI Extractor", type="primary", use_container_width=True):
                        st.session_state["last_extracted_5c"] = pr["recommended_5c"]
                        st.success("Draf Temuan 5C dari Analisis Prediktif berhasil dimuat ke AI Extractor & Audit Workbench (Modul 3)!")
                with act_c2:
                    if st.button("💾 Simpan Langsung Temuan Prediktif ke Database Audit", use_container_width=True):
                        ok, msg = active_db_connector.insert_finding({
                            **pr["recommended_5c"],
                            "management_response": "Sedang diverifikasi oleh tim audit bersama pemilik proses.",
                            "pic": "Mgr. Finance & Accounting",
                            "target_date": "30 Nov 2026",
                            "status": "OPEN"
                        })
                        if ok:
                            st.success(msg)

    # ---------------------------------------------------------
    # REVISI 03 - OPSI 2: CENTRAL DATA INGESTION (SUB-LEDGER & MULTIMODAL)
    # ---------------------------------------------------------
    with tab_opt2:
        st.subheader("2️⃣ Opsi 2: Central Data Ingestion (ERP Sub-Ledger & Multimodal Input)")
        st.markdown(
            "Unggah masing-masing sub-ledger spesifik (**PO, Receiving Report, Vendor Invoice, General Ledger, AR Aging**) "
            "atau dokumen bukti pendukung dalam format **Excel, CSV, PDF Scan, Word (DOCX), maupun Gambar (PNG/JPG)**."
        )

        col_u1, col_u2 = st.columns(2)
        with col_u1:
            po_file = st.file_uploader("Upload PO / Sub-Ledger Data", type=['xlsx', 'csv', 'pdf', 'docx', 'png', 'jpg'], key="up_po")
            rr_file = st.file_uploader("Upload Receiving Report (RR) Data", type=['xlsx', 'csv', 'pdf', 'docx', 'png', 'jpg'], key="up_rr")
            ar_file = st.file_uploader("Upload AR Aging Data", type=['xlsx', 'csv', 'pdf', 'docx', 'png', 'jpg'], key="up_ar")
        with col_u2:
            inv_file = st.file_uploader("Upload Vendor Invoice Data", type=['xlsx', 'csv', 'pdf', 'docx', 'png', 'jpg'], key="up_inv")
            gl_file = st.file_uploader("Upload General Ledger (GL) Data", type=['xlsx', 'csv', 'pdf', 'docx', 'png', 'jpg'], key="up_gl")

        any_subledger_updated = False
        for label, f_obj, state_key in [
            ("PO", po_file, "df_po"),
            ("Receiving Report", rr_file, "df_rr"),
            ("Invoice", inv_file, "df_inv"),
            ("General Ledger", gl_file, "df_gl"),
            ("AR Aging", ar_file, "df_ar"),
        ]:
            if f_obj is not None:
                df_ext, raw_txt = extract_unstructured_file(f_obj)
                if not df_ext.empty:
                    st.session_state[state_key] = df_ext
                    any_subledger_updated = True
                    st.success(f"Data {label} berhasil dimuat: {len(df_ext):,} baris.")
                    st.dataframe(format_dataframe_currency(df_ext.head(5)), use_container_width=True)
                elif raw_txt:
                    st.info(f"Ekstraksi teks/OCR dari berkas {label}:")
                    st.text_area(f"Hasil OCR/Teks ({label})", raw_txt[:1500], height=140)

        if any_subledger_updated:
            refresh_audit_engines()

    # ---------------------------------------------------------
    # REVISI 01: EKSTRAKSI OTOMATIS 5C MENDUKUNG DATA (.xlsx/CSV/.docx/.pdf) & GAMBAR
    # ---------------------------------------------------------
    with tab_ai:
        st.subheader("🤖 Ekstraksi Otomatis 5C dari Catatan Audit Mentah, Dokumen (.xlsx/CSV/.docx/.pdf) & Gambar")
        st.markdown("""
        <div class="erp-info-panel">
            <b>Multimodal AI 5C Extractor:</b> Anda dapat memasukkan catatan teks mentah <b>dan/atau</b> melampirkan berkas
            kertas kerja (<code>.xlsx</code>, <code>.xls</code>, <code>.csv</code>, <code>.docx</code>, <code>.pdf</code>) maupun foto bukti fisik/kuitansi
            (<code>.png</code>, <code>.jpg</code>, <code>.jpeg</code>). AI Engine akan membedah isi tabel/dokumen/gambar dan menyusun struktur <b>5C</b> secara otomatis.
        </div>
        """, unsafe_allow_html=True)

        ai_col1, ai_col2 = st.columns([3, 2])
        with ai_col1:
            default_note = (
                "Ditemukan pengeluaran kas kecil (petty cash) sebesar Rp. 65.000.000 pada PT Suryamicrosystem "
                "untuk pembayaran vendor logistik tanpa otorisasi Direktur Keuangan, melanggar batas SOP Rp. 5.000.000."
            )
            raw_note = st.text_area(
                "Input Catatan Audit Mentah / Konteks Pemeriksaan",
                value=default_note,
                height=145
            )
        with ai_col2:
            ai_attachment = st.file_uploader(
                "Lampirkan Data / Dokumen / Gambar Bukti Audit (Opsional)",
                type=["xlsx", "xls", "csv", "docx", "pdf", "png", "jpg", "jpeg"],
                key="up_ai_5c_multimodal"
            )
            if ai_attachment is not None:
                att_name = ai_attachment.name.lower()
                if att_name.endswith((".png", ".jpg", ".jpeg")):
                    st.image(ai_attachment, caption=f"Pratinjau Bukti Gambar: {ai_attachment.name}", use_container_width=True)
                else:
                    summary_preview, df_att_prev, _, _ = summarize_uploaded_file_for_5c(ai_attachment)
                    st.caption(f"📎 Lampiran Terbaca: **{ai_attachment.name}**")
                    if not df_att_prev.empty:
                        st.dataframe(format_dataframe_currency(df_att_prev.head(3)), use_container_width=True)

        if st.button("⚡ Ekstrak Struktur 5C dengan AI Engine", type="primary"):
            with st.spinner(f"Menganalisis catatan & lampiran audit menggunakan {selected_provider}..."):
                res = extract_5c_from_text(
                    raw_text=raw_note,
                    provider=provider_code,
                    api_key=user_api_key,
                    uploaded_file=ai_attachment
                )
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state["last_extracted_5c"] = res
                    st.success(f"Ekstraksi 5C Berhasil via {selected_provider}!")
                    st.json(res)

        if "last_extracted_5c" in st.session_state:
            ext = st.session_state["last_extracted_5c"]
            if st.button("💾 Simpan Hasil Ekstraksi AI ke Database Temuan (Multi-Backend Sync)"):
                ok, msg = active_db_connector.insert_finding({
                    "area": ext.get("area", "Umum"),
                    "condition": ext.get("condition", "-"),
                    "criteria": ext.get("criteria", "-"),
                    "cause": ext.get("cause", "-"),
                    "effect": ext.get("effect", "-"),
                    "recommendation": ext.get("recommendation", "-"),
                    "risk_level": str(ext.get("risk_level", "MEDIUM")).upper(),
                    "management_response": "-",
                    "pic": "-",
                    "target_date": "-",
                    "status": "OPEN"
                })
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)

    # ---------------------------------------------------------
    # REVISI 02: OUT-OF-CORE ZERO-RAM ENGINE DIPINDAH KE MODUL 1
    # & KAPASITAS UPLOAD >200MB (10 GB + DIRECT DISK STREAMING)
    # ---------------------------------------------------------
    with tab_ooc:
        st.subheader("🚀 Out-of-Core Zero-RAM File-Indexing Engine (Arsitektur ACL / CAATs Miliaran Baris)")
        st.markdown("""
        <div class="erp-info-panel">
            <b>Arsitektur Pemrosesan File Raksasa Tanpa Batas 200 MB (Hingga 10 GB Upload &amp; Unlimited Local Disk Path Stream):</b><br>
            <ol style="margin-bottom:0;">
                <li><b>Single-Pass Streaming Accumulator (O(1) Constant Memory):</b> Berkas CSV/Log ERP diproses secara mengalir per blok (<i>chunked file pointer</i>). Statistik <b>Benford's Law</b>, <b>Total Nilai (Rp.)</b>, dan <b>Rata-Rata (Rp.)</b> dihitung secara <i>online</i> tanpa menumpuk data di RAM.</li>
                <li><b>Disk-Backed B-Tree File Indexing (SQLite WAL Scratch Engine):</b> Pengujian <b>Duplicate Check</b> dan <b>Sequence Gap Detection</b> pada jutaan/miliaran baris dieksekusi langsung melalui indeks B-Tree pada disk.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

        ooc_col1, ooc_col2 = st.columns(2)
        with ooc_col1:
            st.markdown("##### 📁 Opsi A: Unggah File Dump ERP Raksasa (Kapasitas hingga 10 GB / Direct Path)")
            massive_csv = st.file_uploader(
                "Unggah Massive ERP Dump (.csv / .txt / .log — Batas Server Diperbesar ke 10 GB)",
                type=["csv", "txt", "log"],
                key="up_massive_csv"
            )
            local_huge_path = st.text_input(
                "Atau Masukkan Path Lokal/Server Langsung (Untuk File >10 GB - 100 GB+ Tanpa Lewat Browser)",
                placeholder="Contoh: D:\\ERP_Dumps\\SAP_BSEG_2026_50GB.csv",
                key="txt_local_huge_path"
            )
            ooc_chunk = st.select_slider(
                "Ukuran Batch Streaming (Rows per Chunk)",
                options=[10000, 25000, 50000, 100000],
                value=50000
            )

        with ooc_col2:
            st.markdown("##### ⚡ Opsi B: Simulasi & Benchmark Generator Big Data ERP")
            sim_rows = st.selectbox(
                "Jumlah Baris Simulasi Populasi ERP (Zero-RAM Benchmark)",
                options=[100_000, 250_000, 500_000],
                format_func=lambda x: f"{x:,} Baris Transaksi Jurnal/Invoice"
            )
            run_sim_btn = st.button("🚀 Jalankan Benchmark Out-of-Core Engine", type="primary", use_container_width=True)

        target_csv_path = None
        if massive_csv is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_f:
                # Tulis secara bertahap (chunked) ke file sementara agar hemat RAM
                while True:
                    buf = massive_csv.read(16 * 1024 * 1024)
                    if not buf:
                        break
                    tmp_f.write(buf)
                massive_csv.seek(0)
                target_csv_path = tmp_f.name
        elif local_huge_path and os.path.exists(local_huge_path.strip()):
            target_csv_path = local_huge_path.strip()

        if target_csv_path is not None:
            sample_head = pd.read_csv(target_csv_path, nrows=5)
            c_ooc1, c_ooc2 = st.columns(2)
            ooc_amt_col = c_ooc1.selectbox("Kolom Nilai Transaksi (Nominal)", list(sample_head.columns), key="ooc_amt")
            ooc_doc_col = c_ooc2.selectbox("Kolom Nomor Dokumen", list(sample_head.columns), key="ooc_doc")

            if st.button("⚡ Eksekusi Out-of-Core Streaming pada Berkas Ini", type="primary"):
                engine = OutOfCoreCAATsEngine(chunk_size=ooc_chunk)
                with st.spinner("Memproses aliran file secara Out-of-Core (Zero-RAM Indexing)..."):
                    res_ooc = engine.process_csv_stream(target_csv_path, amount_col=ooc_amt_col, doc_id_col=ooc_doc_col)
                st.session_state["last_ooc_result"] = res_ooc

        if run_sim_btn:
            with st.spinner(f"Menulis file populasi ERP {sim_rows:,} baris ke disk & menjalankan Out-of-Core B-Tree Indexing..."):
                tmp_sim_path = os.path.join(tempfile.gettempdir(), "erp_massive_simulation.csv")
                rng = np.random.default_rng(42)
                batch_sz = 100_000
                written = 0
                with open(tmp_sim_path, "w", encoding="utf-8") as f_out:
                    f_out.write("doc_number,account_code,amount\n")
                    while written < sim_rows:
                        cur = min(batch_sz, sim_rows - written)
                        seq = np.arange(written + 1, written + cur + 1)
                        if written == 0 and cur >= 500:
                            seq[100] = seq[99]
                            seq[250] = seq[249]
                            seq[400] = sim_rows + 5
                        amounts = np.round(rng.lognormal(mean=14.5, sigma=1.4, size=cur), 2)
                        chunk_df = pd.DataFrame({
                            "doc_number": [f"SAP-GJ-{s:08d}" for s in seq],
                            "account_code": rng.choice(["1101-CASH", "2101-AP", "4101-REV", "5101-COGS", "6102-OPEX"], size=cur),
                            "amount": amounts
                        })
                        chunk_df.to_csv(f_out, header=False, index=False)
                        written += cur

                engine = OutOfCoreCAATsEngine(chunk_size=ooc_chunk)
                res_ooc = engine.process_csv_stream(tmp_sim_path, amount_col="amount", doc_id_col="doc_number")
                st.session_state["last_ooc_result"] = res_ooc

        if "last_ooc_result" in st.session_state:
            ro = st.session_state["last_ooc_result"]
            st.success(
                f"✅ Out-of-Core Streaming Selesai! Memproses **{ro['total_rows_processed']:,} baris** "
                f"dalam **{ro['elapsed_seconds']} detik** "
                f"(Kecepatan: **{ro['throughput_rows_per_sec']:,} baris/detik**) "
                f"dengan ukuran Chunk **{ro['chunk_size_used']:,} baris** (Zero RAM Overload)."
            )
            om1, om2, om3, om4, om5 = st.columns(5)
            om1.metric("Total Populasi Dipindai", f"{ro['total_rows_processed']:,} Baris")
            om2.metric("Total Nilai Moneter", ro.get("total_monetary_rp", format_rp(ro["total_monetary_value"])))
            om3.metric("Rata-Rata Nilai Transaksi", ro.get("average_monetary_rp", format_rp(ro["total_monetary_value"] / max(ro["total_rows_processed"], 1))))
            om4.metric("Duplikat Terdeteksi (B-Tree)", f"{ro['total_duplicate_keys']} Nomor")
            om5.metric("Sequence Gap Terdeteksi", f"{ro['total_missing_sequences']} Dokumen")

            ooc_t1, ooc_t2, ooc_t3 = st.tabs([
                "📈 Distribusi Benford Streaming",
                "🔁 Hasil Duplikat Disk B-Tree",
                "🕳️ Hasil Sequence Gap Disk B-Tree"
            ])
            with ooc_t1:
                st.plotly_chart(
                    create_benford_chart(ro["benford_df"], title_suffix=f"Out-of-Core ({ro['total_rows_processed']:,} Rows)"),
                    use_container_width=True
                )
            with ooc_t2:
                if not ro["duplicates_df"].empty:
                    st.dataframe(ro["duplicates_df"], use_container_width=True)
                else:
                    st.info("Tidak ada duplikasi kunci dokumen.")
            with ooc_t3:
                if not ro["gaps_df"].empty:
                    st.dataframe(ro["gaps_df"], use_container_width=True)
                else:
                    st.info("Tidak ada sequence gap.")


# =========================================================
# MODUL 2: PSAK 71 AR AGING & TRADITIONAL ACL / CAATs ENGINE
# =========================================================
elif menu == "2. PSAK 71 & ACL/CAATs Engine":
    st.markdown("""
    <div class="erp-module-bar">
        <span class="erp-module-bar-title">📊 MODUL 02 // PSAK 71 ECL, 3-WAY MATCHING &amp; ACL / CAATs TRADITIONAL ANALYTICS ENGINE</span>
        <span class="erp-module-bar-meta">TCODE: AL_CAATS_PSAK71 | ENGINE: DETERMINISTIC FULL-POPULATION TESTING</span>
    </div>
    """, unsafe_allow_html=True)

    tab_psak, tab_matching, tab_caats = st.tabs([
        "📊 Evaluasi AR Aging & CKPN PSAK 71",
        "⚡ 3-Way Matching & Anomali Jurnal (GL)",
        "🔍 ACL / CAATs Tradisional (Benford, Duplicate, Gap, Stratify)"
    ])

    with tab_psak:
        st.subheader("📊 Evaluasi Umur Piutang (AR Aging) & CKPN PSAK 71")
        df_ar_input = st.session_state.get("df_ar")
        snapshot_dt = st.date_input("Tanggal Cut-Off / Snapshot Evaluasi", value=pd.to_datetime("2026-11-01"))

        df_detail, df_summary = calculate_psak71_ckpn(df_ar_input, snapshot_date=str(snapshot_dt))

        total_ar_val = float(df_summary["total_piutang"].sum())
        total_ckpn_val = float(df_summary["total_ckpn"].sum())
        total_inv_cnt = int(df_summary["jumlah_inv"].sum())
        avg_ar_val = total_ar_val / max(total_inv_cnt, 1)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Eksposur Piutang (AR)", format_rp(total_ar_val))
        k2.metric("Rata-Rata Nilai per Invoice", format_rp(avg_ar_val))
        k3.metric("Total CKPN Wajib Dibentuk (ECL)", format_rp(total_ckpn_val))
        k4.metric("Total Faktur Dianalisis", f"{total_inv_cnt} Invoice")

        st.markdown("##### Ringkasan Matriks Cadangan Kerugian Penurunan Nilai (CKPN) PSAK 71")
        df_summary_disp = df_summary.copy()
        df_summary_disp["rata_rata_piutang"] = (
            df_summary_disp["total_piutang"] / df_summary_disp["jumlah_inv"].replace(0, np.nan)
        ).fillna(0.0).apply(lambda v: format_rp(v))
        df_summary_disp["total_piutang"] = df_summary_disp["total_piutang"].apply(lambda v: format_rp(v))
        df_summary_disp["total_ckpn"] = df_summary_disp["total_ckpn"].apply(lambda v: format_rp(v))
        df_summary_disp["ecl_rate"] = (df_summary_disp["ecl_rate"] * 100.0).round(2).astype(str) + "%"
        st.dataframe(df_summary_disp, use_container_width=True)

        with st.expander("Lihat Rincian Per Faktur Piutang (AR Detail Terformat Rp.)"):
            st.dataframe(format_dataframe_currency(df_detail), use_container_width=True)

        if st.button("📌 Eskalasi Hasil CKPN PSAK 71 ke Kertas Kerja 5C (Modul 3)", key="btn_esc_psak"):
            st.session_state["last_extracted_5c"] = {
                "area": "Piutang (AR)",
                "condition": (
                    f"Hasil perhitungan ulang AR Aging per {snapshot_dt} terhadap {total_inv_cnt} faktur dengan total piutang "
                    f"{format_rp(total_ar_val)} (rata-rata {format_rp(avg_ar_val)}/faktur) menunjukkan kewajiban pembentukan CKPN PSAK 71 "
                    f"sebesar {format_rp(total_ckpn_val)}."
                ),
                "criteria": "PSAK 71 (Instrumen Keuangan) mewajibkan pengukuran penyisihan kerugian kredit ekspektasian (Expected Credit Loss).",
                "cause": "Manajemen belum memperbarui tarif pencadangan kolektibilitas pada penutupan buku periode berjalan.",
                "effect": f"Saldo piutang bersih berpotensi overstated sebesar {format_rp(total_ckpn_val)}.",
                "recommendation": f"Bukukan jurnal penyesuaian beban CKPN sebesar {format_rp(total_ckpn_val)} dan perketat penagihan piutang >90 hari.",
                "risk_level": "HIGH" if total_ckpn_val >= 50_000_000 else "MEDIUM"
            }
            st.success("Temuan PSAK 71 telah dimuat ke Kertas Kerja 5C! Silakan buka Modul 3 untuk menyimpan.")

    with tab_matching:
        st.subheader("⚡ Eksekusi Engine Automated Audit Rules (3-Way Matching & GL Anomalies)")
        if st.button("Jalankan Pengujian Audit Otomatis", type="primary"):
            refresh_audit_engines()
            st.success("Pemindaian 3-Way Matching & Anomali Jurnal Selesai!")

        res_matching = st.session_state.get("res_matching", pd.DataFrame())
        res_anomalies = st.session_state.get("res_anomalies", pd.DataFrame())

        sub_t1, sub_t2 = st.tabs(["Hasil 3-Way Matching (PO vs RR vs Inv)", "Hasil Anomali Jurnal & SoD"])
        with sub_t1:
            if not res_matching.empty:
                mismatches_only = res_matching[res_matching["match_status"] != "MATCHED"]
                tot_var = float(res_matching["variance_amount"].sum())
                avg_var = float(mismatches_only["variance_amount"].mean()) if not mismatches_only.empty else 0.0
                st.markdown(
                    f"**Total PO Diuji:** `{len(res_matching)}` baris | "
                    f"**Mismatch Terdeteksi:** `{len(mismatches_only)}` baris | "
                    f"**Total Varians:** `{format_rp(tot_var)}` | "
                    f"**Rata-Rata Varians per Mismatch:** `{format_rp(avg_var)}`"
                )
                st.dataframe(format_dataframe_currency(res_matching), use_container_width=True)

                if st.button("📌 Eskalasi Selisih 3-Way Matching ke Kertas Kerja 5C (Modul 3)", key="btn_esc_3way"):
                    st.session_state["last_extracted_5c"] = {
                        "area": "Utang & Pembelian (AP)",
                        "condition": (
                            f"Pengujian 3-Way Matching atas {len(res_matching)} PO menemukan {len(mismatches_only)} transaksi "
                            f"tidak cocok (QTY_MISMATCH / PRICE_MISMATCH) dengan total selisih {format_rp(tot_var)} "
                            f"(rata-rata varians {format_rp(avg_var)} per transaksi)."
                        ),
                        "criteria": "SOP Pengadaan & Pembayaran Vendor PT Suryamicrosystem (Wajib 3-Way Match PO = RR = Invoice).",
                        "cause": "Pembayaran tagihan vendor diproses sebelum verifikasi kelengkapan Receiving Report (RR) dan kesesuaian harga PO.",
                        "effect": f"Potensi kelebihan bayar (overpayment) dan kerugian kas sebesar {format_rp(tot_var)}.",
                        "recommendation": "Tahan pembayaran atas faktur yang berstatus mismatch dan terbitkan Debit Note kepada vendor terkait.",
                        "risk_level": "HIGH"
                    }
                    st.success("Temuan 3-Way Matching berhasil dimuat ke Kertas Kerja 5C (Modul 3)!")
            else:
                st.info("Belum ada data 3-Way Matching.")
        with sub_t2:
            if not res_anomalies.empty:
                tot_anom_debit = float(pd.to_numeric(res_anomalies["debit"], errors="coerce").sum())
                avg_anom_debit = float(pd.to_numeric(res_anomalies["debit"], errors="coerce").mean())
                st.markdown(
                    f"**Terdeteksi `{len(res_anomalies)}` Jurnal Berisiko Tinggi** | "
                    f"**Total Nilai Jurnal Anomali:** `{format_rp(tot_anom_debit)}` | "
                    f"**Rata-Rata per Jurnal:** `{format_rp(avg_anom_debit)}`"
                )
                st.dataframe(format_dataframe_currency(res_anomalies), use_container_width=True)

                if st.button("📌 Eskalasi Anomali Jurnal GL ke Kertas Kerja 5C (Modul 3)", key="btn_esc_gl"):
                    st.session_state["last_extracted_5c"] = {
                        "area": "General Ledger",
                        "condition": (
                            f"Pemindaian General Ledger menemukan {len(res_anomalies)} jurnal anomali (Off-Hours Posting, "
                            f"Nominal Bulat Besar, dan Konflik SoD) dengan total nilai {format_rp(tot_anom_debit)}."
                        ),
                        "criteria": "Kebijakan Pengendalian Internal Akuntansi & Segregation of Duties (SoD) PT Suryamicrosystem.",
                        "cause": "Akses super-user memungkinkan staf yang sama membuat sekaligus menyetujui jurnal di luar jam kerja.",
                        "effect": f"Risiko management override of controls dan manipulasi jurnal senilai {format_rp(tot_anom_debit)}.",
                        "recommendation": "Cabut hak self-approval pada modul GL dan wajibkan otorisasi berjenjang untuk jurnal manual.",
                        "risk_level": "HIGH"
                    }
                    st.success("Temuan Anomali Jurnal berhasil dimuat ke Kertas Kerja 5C (Modul 3)!")
            else:
                st.info("Tidak ditemukan anomali jurnal pada dataset saat ini.")

    with tab_caats:
        st.subheader("🔍 Modul Akuisisi Kapabilitas ACL / IDEA (CAATs Tradisional)")
        st.markdown("""
        <div class="erp-info-panel">
            <b>Fungsi Deterministik CAATs (Computer-Assisted Audit Techniques):</b>
            Mengeksekusi pengujian populasi penuh (<i>100% Full Population Testing</i>) layaknya perangkat lunak <b>ACL Analytics / CaseWare IDEA</b>
            pada dataset terstruktur ERP: <b>Benford's Law First-Digit Test</b>, <b>Duplicate Key Detection</b>,
            <b>Document Sequence Gap Detection</b>, dan <b>Numeric Stratification &amp; Outlier Profiling (Format Rp.)</b>.
        </div>
        """, unsafe_allow_html=True)

        dataset_map = {
            "General Ledger (GL_Data)": st.session_state.get("df_gl", pd.DataFrame()),
            "Purchase Orders (PO_Data)": st.session_state.get("df_po", pd.DataFrame()),
            "Receiving Reports (RR_Data - Mengandung Gap!)": st.session_state.get("df_rr", pd.DataFrame()),
            "Vendor Invoices (Invoice_Data)": st.session_state.get("df_inv", pd.DataFrame()),
            "AR Aging Sub-Ledger (AR_Aging_Data)": st.session_state.get("df_ar", pd.DataFrame()),
        }

        c_sel1, c_sel2, c_sel3 = st.columns(3)
        with c_sel1:
            chosen_ds_name = st.selectbox("Pilih Tabel Populasi ERP", list(dataset_map.keys()))
            df_caats = dataset_map[chosen_ds_name]
        with c_sel2:
            num_cols = [c for c in df_caats.columns if pd.api.types.is_numeric_dtype(df_caats[c])]
            if not num_cols:
                num_cols = list(df_caats.columns)
            chosen_num_col = st.selectbox("Kolom Nilai Moneter / Angka (Benford & Stratify)", num_cols)
        with c_sel3:
            str_cols = list(df_caats.columns)
            chosen_id_col = st.selectbox("Kolom Nomor Dokumen (Duplicate & Sequence Gap)", str_cols, index=0)

        caats_sub1, caats_sub2, caats_sub3, caats_sub4 = st.tabs([
            "1️⃣ Benford's Law (First-Digit)",
            "2️⃣ Duplicate Check (Ganda)",
            "3️⃣ Gap Detection (Loncatan Nomor)",
            "4️⃣ Stratification & Outlier (Rp.)"
        ])

        with caats_sub1:
            df_benford, benford_meta = run_benfords_law_analysis(df_caats, chosen_num_col)
            b_m1, b_m2, b_m3, b_m4 = st.columns(4)
            b_m1.metric("Populasi Angka Valid", f"{benford_meta['total_valid_records']:,} Baris")
            b_m2.metric("Mean Absolute Deviation (MAD)", f"{benford_meta['mad']:.4f}")
            b_m3.metric("Chi-Square Statistic", f"{benford_meta['chi_square']:.2f}")
            b_m4.metric("Digit Mencurigakan (|Z| > 1.96)", f"{benford_meta['suspicious_digits_count']} Digit")

            st.info(f"**Kesimpulan Konformitas Benford's Law:** `{benford_meta['conformity_label']}`")
            st.plotly_chart(create_benford_chart(df_benford, title_suffix=f"{chosen_ds_name} [{chosen_num_col}]"), use_container_width=True)
            st.dataframe(df_benford, use_container_width=True)

        with caats_sub2:
            composite_candidates = [c for c in df_caats.columns if c != chosen_id_col][:2]
            dup_res = run_duplicate_detection(
                df_caats,
                primary_key_col=chosen_id_col,
                composite_cols=composite_candidates if composite_candidates else None
            )
            d_m1, d_m2, d_m3 = st.columns(3)
            d_m1.metric("Total Baris Diperiksa", f"{dup_res['summary']['total_rows_scanned']:,}")
            d_m2.metric("Duplikasi Nomor Dokumen Eksak", f"{dup_res['summary']['exact_duplicate_rows']:,} Baris")
            d_m3.metric(
                f"Duplikasi Atribut ({', '.join(composite_candidates)})",
                f"{dup_res['summary']['composite_duplicate_rows']:,} Baris"
            )
            if not dup_res["exact_duplicates"].empty:
                st.warning("Ditemukan duplikasi nomor dokumen eksak:")
                st.dataframe(format_dataframe_currency(dup_res["exact_duplicates"]), use_container_width=True)
            else:
                st.success(f"Tidak ditemukan duplikasi eksak pada kolom `{chosen_id_col}`.")

            if not dup_res["composite_duplicates"].empty:
                with st.expander("Lihat Transaksi dengan Kombinasi Atribut/Nilai Kembar (Potensi Double Billing)"):
                    st.dataframe(format_dataframe_currency(dup_res["composite_duplicates"]), use_container_width=True)

        with caats_sub3:
            gap_df, gap_meta = run_gap_detection(df_caats, chosen_id_col)
            g_m1, g_m2, g_m3, g_m4 = st.columns(4)
            g_m1.metric("Prefix Dokumen", gap_meta["prefix_detected"])
            g_m2.metric("Rentang Nomor Urut", f"{gap_meta['min_sequence']} s/d {gap_meta['max_sequence']}")
            g_m3.metric("Total Dokumen Hilang (Gap)", f"{gap_meta['total_missing_count']} Dokumen")
            g_m4.metric("Integritas Urutan", gap_meta["integrity_status"])

            if not gap_df.empty:
                st.error(
                    f"⚠️ Terdeteksi **{gap_meta['total_missing_count']}** nomor dokumen yang hilang/melompat "
                    f"pada `{chosen_id_col}`!"
                )
                st.dataframe(gap_df, use_container_width=True)
            else:
                st.success(f"✅ Urutan dokumen pada kolom `{chosen_id_col}` lengkap dan berkesinambungan (Zero Sequence Gap).")

        with caats_sub4:
            df_strat, df_outliers = run_population_stratification(df_caats, chosen_num_col, num_strata=6)
            raw_series = pd.to_numeric(df_caats[chosen_num_col], errors="coerce").dropna()
            st_c1, st_c2, st_c3 = st.columns(3)
            st_c1.metric("Total Nilai Populasi", format_rp(raw_series.sum() if not raw_series.empty else 0))
            st_c2.metric("Rata-Rata Nilai Populasi", format_rp(raw_series.mean() if not raw_series.empty else 0))
            st_c3.metric("Nilai Maksimum Transaksi", format_rp(raw_series.max() if not raw_series.empty else 0))

            st.markdown("##### 📊 Tabel Stratifikasi Nilai Populasi (ACL `STRATIFY` — Total_Nilai & Rata_Rata dalam Rp.)")
            st.dataframe(df_strat, use_container_width=True)
            st.markdown("##### 🚨 Transaksi Outlier Ekstrem (|Z-Score| >= 2.0)")
            if not df_outliers.empty:
                st.dataframe(df_outliers, use_container_width=True)
            else:
                st.info("Tidak ada nilai ekstrem di luar 2.0 standar deviasi pada kolom ini.")


# =========================================================
# MODUL 3: AUDIT WORKBENCH (5C MANAGEMENT & FOLLOW-UP)
# =========================================================
elif menu == "3. Audit Workbench (5C & Multi-DB)":
    st.markdown(f"""
    <div class="erp-module-bar">
        <span class="erp-module-bar-title">📝 MODUL 03 // AUDIT WORKBENCH (5C WORKING PAPERS, ACTION PLAN &amp; FOLLOW-UP)</span>
        <span class="erp-module-bar-meta">TCODE: AL_WB_5C | ACTIVE BACKEND: {active_backend_name}</span>
    </div>
    """, unsafe_allow_html=True)

    pre = st.session_state.get("last_extracted_5c", {})

    wb_tab1, wb_tab2 = st.tabs([
        "➕ Registrasi & Simpan Kertas Kerja Temuan 5C",
        "📋 Register Temuan Audit & Pemutakhiran Status Tindak Lanjut"
    ])

    with wb_tab1:
        with st.form("f_5c"):
            st.markdown("##### ➕ Formulir Kertas Kerja Temuan Audit (Standar 5C)")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                area_options = ["Kas & Bank", "Utang & Pembelian (AP)", "Piutang (AR)", "Beban Operasional", "General Ledger"]
                default_area = pre.get("area", "Kas & Bank")
                if default_area not in area_options:
                    area_options.insert(0, default_area)
                area = st.selectbox("Area / Akun Audit", area_options)
            with col_f2:
                risk_options = ["HIGH", "MEDIUM", "LOW"]
                default_risk = str(pre.get("risk_level", "HIGH")).upper()
                risk_idx = risk_options.index(default_risk) if default_risk in risk_options else 0
                risk = st.selectbox("Risk Level", risk_options, index=risk_idx)
            with col_f3:
                status_val = st.selectbox("Status Tindak Lanjut", ["OPEN", "IN_PROGRESS", "CLOSED"])

            cond = st.text_area("Condition (Kondisi Aktual Lapangan)", value=pre.get("condition", ""))
            crit = st.text_area("Criteria (Standar SOP / Regulasi)", value=pre.get("criteria", "SOP Pengendalian Internal PT Suryamicrosystem"))
            cause = st.text_area("Cause (Akar Masalah)", value=pre.get("cause", ""))
            effect = st.text_area("Effect (Dampak / Potensi Kerugian dalam Rp.)", value=pre.get("effect", ""))
            rec = st.text_area("Recommendation (Rekomendasi Solusi Auditor)", value=pre.get("recommendation", ""))

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                mgmt_resp = st.text_input("Tanggapan Manajemen", value="Manajemen berkomitmen menindaklanjuti rekomendasi.")
            with col_m2:
                pic_val = st.text_input("PIC Penanggung Jawab", value="Mgr. Finance & Accounting")
            with col_m3:
                target_dt = st.text_input("Target Penyelesaian", value="30 Nov 2026")

            if st.form_submit_button("💾 Simpan Temuan ke Database Aktif", type="primary"):
                ok, msg = active_db_connector.insert_finding({
                    "project_id": 1,
                    "area": area,
                    "condition": cond or "-",
                    "criteria": crit or "-",
                    "cause": cause or "-",
                    "effect": effect or "-",
                    "recommendation": rec or "-",
                    "risk_level": risk,
                    "management_response": mgmt_resp,
                    "pic": pic_val,
                    "target_date": target_dt,
                    "status": status_val
                })
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)

                if risk == "HIGH" and n8n_webhook_url:
                    sent = send_n8n_high_risk_alert(n8n_webhook_url, {
                        "area": area,
                        "risk_level": risk,
                        "condition": cond,
                        "effect": effect,
                        "recommendation": rec
                    })
                    if sent:
                        st.toast("📲 Notifikasi WhatsApp High-Risk berhasil dikirim via n8n Webhook!")
                    else:
                        st.warning("Temuan disimpan, namun pengiriman webhook n8n gagal/tidak merespons 200 OK.")

    with wb_tab2:
        findings_rows = active_db_connector.fetch_findings()
        df_findings = pd.DataFrame(findings_rows)

        if not df_findings.empty:
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                filter_risk = st.multiselect("Filter Level Risiko", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM", "LOW"])
            with f_col2:
                filter_status = st.multiselect("Filter Status", ["OPEN", "IN_PROGRESS", "CLOSED"], default=["OPEN", "IN_PROGRESS", "CLOSED"])

            df_filtered = df_findings[
                df_findings["risk_level"].isin(filter_risk) & df_findings["status"].isin(filter_status)
            ]
            display_cols = [c for c in ["id", "area", "risk_level", "condition", "recommendation", "management_response", "pic", "target_date", "status"] if c in df_filtered.columns]
            st.dataframe(df_filtered[display_cols], use_container_width=True)

            st.markdown("##### 🔄 Pemutakhiran Status Tindak Lanjut Audit (Follow-Up Monitoring)")
            u_c1, u_c2, u_c3, u_c4 = st.columns([1, 1, 2, 1])
            with u_c1:
                sel_id = st.selectbox("Pilih ID Temuan", df_findings["id"].tolist(), key="sel_upd_id")
            with u_c2:
                new_st = st.selectbox("Status Baru", ["OPEN", "IN_PROGRESS", "CLOSED"], key="sel_upd_st")
            with u_c3:
                new_resp = st.text_input("Catatan Tindak Lanjut Manajemen (Opsional)", key="txt_upd_resp")
            with u_c4:
                st.markdown("<div style='margin-top:26px;'></div>", unsafe_allow_html=True)
                if st.button("✅ Update Status", use_container_width=True):
                    ok_u, msg_u = active_db_connector.update_finding_status(sel_id, new_st, new_resp)
                    if ok_u:
                        st.success(msg_u)
                        st.rerun()
        else:
            st.info("Belum ada data temuan pada database.")


# =========================================================
# MODUL 4: CLIENT EXECUTIVE DASHBOARD & DELIVERABLE REPORTS
# =========================================================
elif menu == "4. Client Executive Dashboard & Reports":
    st.markdown(f"""
    <div class="erp-module-bar">
        <span class="erp-module-bar-title">🏛️ MODUL 04 // EXECUTIVE BOARD DASHBOARD &amp; OFFICIAL AUDIT DELIVERABLES — {CLIENT_NAME.upper()}</span>
        <span class="erp-module-bar-meta">TCODE: AL_EXEC_BOARD | ACCESS LEVEL: {str(user_role).upper()}</span>
    </div>
    """, unsafe_allow_html=True)

    findings = active_db_connector.fetch_findings()

    res_matching = st.session_state.get("res_matching", pd.DataFrame())
    if not res_matching.empty:
        total_po_val = float((res_matching["qty"] * res_matching["po_price"]).sum())
        total_var_val = float(res_matching["variance_amount"].sum())
        avg_po_val = float((res_matching["qty"] * res_matching["po_price"]).mean())
        matched_ratio = float((res_matching["match_status"] == "MATCHED").mean() * 100)
        mismatch_df = res_matching[res_matching["match_status"] != "MATCHED"].reset_index(drop=True)
    else:
        total_po_val = 12400000000.0
        total_var_val = 425000000.0
        avg_po_val = 82666666.0
        matched_ratio = 94.2
        mismatch_df = pd.DataFrame()

    # KPI Executive Cards dengan Format Rp. (Titik Ribuan)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Transaksi Diaudit", format_rp(total_po_val), delta=f"Rata-rata: {format_rp(avg_po_val)}/PO", delta_color="off")
    m2.metric("Total Potensi Temuan (Varians)", format_rp(total_var_val), delta="-3.4%", delta_color="inverse")
    m3.metric("Tingkat Verifikasi Valid", f"{matched_ratio:.1f}%", delta="1.2%")
    m4.metric("Status Opini Audit Usulan", DEFAULT_OPINION)

    # Visualisasi Utama: Plotly Sankey Diagram 3-Way Matching
    st.plotly_chart(create_sankey_3way_matching(res_matching), use_container_width=True)

    # Grafik Distribusi Risiko & Area Temuan (Dengan Tema Warna Beige ERP)
    if findings:
        df_f = pd.DataFrame(findings)
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            risk_counts = df_f["risk_level"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0).reset_index()
            risk_counts.columns = ["Risk Level", "Count"]
            fig_risk = px.pie(
                risk_counts, names="Risk Level", values="Count", color="Risk Level",
                color_discrete_map={"HIGH": "#B8332A", "MEDIUM": "#C87D20", "LOW": "#4A7C59"},
                hole=0.45,
                title="<b>Distribusi Temuan Berdasarkan Level Risiko</b>"
            )
            fig_risk.update_layout(
                paper_bgcolor="#FAF6EE",
                plot_bgcolor="#FAF6EE",
                font=dict(color="#2B2520")
            )
            st.plotly_chart(fig_risk, use_container_width=True)

        with c_chart2:
            area_counts = df_f["area"].value_counts().reset_index()
            area_counts.columns = ["Area", "Jumlah Temuan"]
            fig_area = px.bar(
                area_counts, x="Area", y="Jumlah Temuan", color="Area",
                color_discrete_sequence=["#8B5A2B", "#A67B5B", "#C5A059", "#6E4720", "#B89972"],
                title="<b>Jumlah Temuan per Area Audit</b>"
            )
            fig_area.update_layout(
                paper_bgcolor="#FAF6EE",
                plot_bgcolor="#FAF6EE",
                font=dict(color="#2B2520")
            )
            st.plotly_chart(fig_area, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------
    # UNDUH DOKUMEN DELIVERABLE RESMI (EXECUTIVE EXPORT):
    # HANYA UNTUK USER "AUDITOR" (Strict RBAC Enforcement)
    # ---------------------------------------------------------
    if user_role == "Auditor":
        st.markdown("#### 📥 Unduh Dokumen Deliverable Resmi (Executive Export)")
        st.caption("Otorisasi Ekspor Penuh: Hanya tersedia bagi peran **Auditor** untuk menghasilkan dan mendistribusikan dokumen resmi.")

        excel_bytes = generate_full_audit_excel(findings, mismatch_df)
        pptx_bytes = generate_audit_pptx(
            project_name=PROJECT_NAME,
            client_name=CLIENT_NAME,
            opinion=DEFAULT_OPINION,
            findings=findings
        )
        pdf_bytes = generate_management_letter_pdf_bytes(
            project_name=PROJECT_NAME,
            client_name=CLIENT_NAME,
            opinion=DEFAULT_OPINION,
            findings_list=findings
        )

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                label="📥 Unduh Excel V2 (Donut Chart)",
                data=excel_bytes,
                file_name="Audit_Report_PT_Suryamicrosystem_2026.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with dl2:
            st.download_button(
                label="📊 Unduh Slide PPTX",
                data=pptx_bytes,
                file_name="Presentasi_Direksi_PT_Suryamicrosystem_2026.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True
            )
        with dl3:
            st.download_button(
                label="📄 Unduh Management Letter (PDF)",
                data=pdf_bytes,
                file_name="Management_Letter_PT_Suryamicrosystem_2026.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with st.expander("📧 Kirim Laporan Audit Excel via Email SMTP"):
            smtp_cfg = get_smtp_config()
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                to_email = st.text_input("Email Penerima (Direksi / Komite Audit)", placeholder="direksi@suryamicrosystem.co.id")
                smtp_user = st.text_input("Email Pengirim (SMTP)", value=smtp_cfg.get("sender_email", ""))
            with e_col2:
                smtp_host = st.text_input("SMTP Server", value=smtp_cfg.get("server", "smtp.gmail.com"))
                smtp_pass = st.text_input("App Password SMTP", value=smtp_cfg.get("sender_password", ""), type="password")

            if st.button("📨 Kirim Laporan via Email"):
                if not to_email or not smtp_user or not smtp_pass:
                    st.warning("Mohon lengkapi alamat email penerima, email pengirim, dan App Password SMTP.")
                else:
                    ok = send_audit_report_email(
                        to_email=to_email,
                        subject=f"Laporan Hasil Audit Keuangan 2026 — {CLIENT_NAME}",
                        body_text=f"<p>Yth. Jajaran Direksi <b>{CLIENT_NAME}</b>,</p><p>Terlampir Matriks Temuan Audit & Action Plan Tahun 2026.</p>",
                        excel_bytes=excel_bytes,
                        filename="Audit_Report_PT_Suryamicrosystem_2026.xlsx",
                        smtp_server=smtp_host,
                        smtp_port=smtp_cfg.get("port", 587),
                        sender_email=smtp_user,
                        sender_password=smtp_pass
                    )
                    if ok:
                        st.success(f"Laporan berhasil dikirim ke {to_email}!")
                    else:
                        st.error("Gagal mengirim email. Periksa kembali konfigurasi SMTP.")
    else:
        st.markdown("""
        <div class="erp-lock-panel">
            <b>🔒 Kebijakan Tata Kelola Dokumen (Role-Based Access Control):</b><br>
            Bagian <b>Unduh Dokumen Deliverable Resmi (Executive Export)</b> dan pengiriman distribusi SMTP dikunci khusus untuk otorisasi <b>Auditor</b>.
            Sebagai <b>Director</b>, Anda dapat meninjau metrik eksekutif dan visualisasi interaktif secara langsung pada layar ini.
        </div>
        """, unsafe_allow_html=True)


# =========================================================
# MODUL 5: ⚙️ PENGATURAN (AI ENGINE & MULTI-BACKEND DB)
# (Revisi 02 & 04: Gabungan AI Engine + Multi-Backend DB + Popup DDL SQL)
# =========================================================
elif menu == "5. Pengaturan" and user_role == "Auditor":
    st.markdown("""
    <div class="erp-module-bar">
        <span class="erp-module-bar-title">⚙️ MODUL 05 // PENGATURAN SISTEM (AI ENGINE CONFIGURATION &amp; MULTI-BACKEND DATABASE HUB)</span>
        <span class="erp-module-bar-meta">TCODE: AL_SYS_CONFIG | OTORISASI: AUDITOR ONLY</span>
    </div>
    """, unsafe_allow_html=True)

    cfg_col1, cfg_col2 = st.columns(2)

    # 1. AI ENGINE CONFIGURATION & N8N WEBHOOK
    with cfg_col1:
        st.markdown("""
        <div class="erp-card-box">
            <h4 style="margin-top:0; color:#3A2A1D;">🤖 AI Engine Configuration &amp; Webhook</h4>
            <p style="font-size:0.84rem; color:#5C4D3C;">
                Konfigurasi provider Large Language Model (Google Gemini / Anthropic Claude) untuk ekstraksi otomatis 5C
                beserta endpoint notifikasi real-time WhatsApp via n8n.
            </p>
        </div>
        """, unsafe_allow_html=True)

        sel_prov_ui = st.selectbox(
            "Pilih AI Provider 5C",
            options=["Gemini (Google)", "Claude (Anthropic)"],
            index=0 if ai_settings["provider_code"] == "gemini" else 1
        )
        ai_settings["provider_label"] = sel_prov_ui
        ai_settings["provider_code"] = "claude" if "Claude" in sel_prov_ui else "gemini"

        if ai_settings["provider_code"] == "claude":
            ai_settings["anthropic_api_key"] = st.text_input(
                "Anthropic API Key (Claude 3.5 Sonnet)",
                value=ai_settings.get("anthropic_api_key", ""),
                type="password"
            )
        else:
            ai_settings["gemini_api_key"] = st.text_input(
                "Google Gemini API Key (Gemini 2.5 Flash)",
                value=ai_settings.get("gemini_api_key", ""),
                type="password"
            )

        ai_settings["n8n_webhook_url"] = st.text_input(
            "n8n WhatsApp Webhook URL (Alert Temuan HIGH Risk)",
            value=ai_settings.get("n8n_webhook_url", ""),
            placeholder="https://n8n.domain.com/webhook/..."
        )

        if st.button("💾 Simpan Konfigurasi AI & Webhook", type="primary", use_container_width=True):
            st.success(f"Konfigurasi AI Engine ({ai_settings['provider_label']}) & Webhook berhasil diperbarui!")

    # 2. MULTI-BACKEND DB ENGINE & POPUP SKEMA DDL SQL
    with cfg_col2:
        st.markdown("""
        <div class="erp-card-box">
            <h4 style="margin-top:0; color:#3A2A1D;">🗄️ Multi-Backend DB Engine (SQLite / Supabase / PostgreSQL)</h4>
            <p style="font-size:0.84rem; color:#5C4D3C;">
                Hubungkan AuditLens dengan basis data lokal SQLite, <b>Supabase Cloud</b> (PostgREST / Pooler),
                atau <b>PostgreSQL Enterprise</b> (Data Warehouse ERP SAP/Oracle).
            </p>
        </div>
        """, unsafe_allow_html=True)

        db_cfg = st.session_state["db_backend_config"]
        backend_label = st.selectbox(
            "Target Database Engine Aktif",
            options=[
                "SQLite Local (Default ERP)",
                "Supabase Cloud (PostgreSQL / REST)",
                "PostgreSQL External (SAP/Oracle DW)"
            ],
            index={"sqlite": 0, "supabase": 1, "postgresql": 2}.get(db_cfg.get("backend_type", "sqlite"), 0)
        )

        if "Supabase" in backend_label:
            db_cfg["backend_type"] = "supabase"
            db_cfg["supabase_url"] = st.text_input(
                "Supabase Project URL",
                value=db_cfg.get("supabase_url", ""),
                placeholder="https://xyzcompany.supabase.co"
            )
            db_cfg["supabase_key"] = st.text_input(
                "Supabase Service / Anon API Key",
                value=db_cfg.get("supabase_key", ""),
                type="password"
            )
            db_cfg["pg_dsn"] = st.text_input(
                "Supabase Connection URI (Opsional Supavisor Pooler)",
                value=db_cfg.get("pg_dsn", ""),
                placeholder="postgresql://postgres:[PASS]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres",
                type="password"
            )
        elif "PostgreSQL" in backend_label:
            db_cfg["backend_type"] = "postgresql"
            db_cfg["pg_dsn"] = st.text_input(
                "PostgreSQL Connection URI (DSN)",
                value=db_cfg.get("pg_dsn", ""),
                placeholder="postgresql://user:pass@host:5432/audit_db",
                type="password"
            )
            with st.expander("Parameter Host / Port Manual PostgreSQL"):
                db_cfg["pg_host"] = st.text_input("PG Host", value=db_cfg.get("pg_host", "localhost"))
                db_cfg["pg_port"] = st.number_input("PG Port", value=int(db_cfg.get("pg_port", 5432)), step=1)
                db_cfg["pg_database"] = st.text_input("PG Database", value=db_cfg.get("pg_database", "postgres"))
                db_cfg["pg_user"] = st.text_input("PG User", value=db_cfg.get("pg_user", "postgres"))
                db_cfg["pg_password"] = st.text_input("PG Password", value=db_cfg.get("pg_password", ""), type="password")
        else:
            db_cfg["backend_type"] = "sqlite"

        btn_db1, btn_db2 = st.columns(2)
        with btn_db1:
            if st.button("🔌 Test Koneksi Backend DB", type="primary", use_container_width=True):
                connector = MultiBackendDBConnector(db_cfg)
                hc = connector.test_connection()
                if hc["status"] == "CONNECTED":
                    st.success(f"{hc['engine']} ({hc['latency_ms']} ms): {hc['message']}")
                else:
                    st.info(f"{hc['engine']}: {hc['message']}")
        with btn_db2:
            # REVISI 02: Skema DDL SQL dibuat Popup Modal, tidak langsung terlihat memenuhi layar
            if st.button("📜 Popup Skema DDL SQL", use_container_width=True):
                show_ddl_sql_popup()

    st.markdown("---")
    st.markdown("##### 📊 Telemetri & Status Sinkronisasi Multi-Backend Database")
    hc_now = active_db_connector.test_connection()
    findings_cnt = len(active_db_connector.fetch_findings())
    tm1, tm2, tm3, tm4 = st.columns(4)
    tm1.metric("Engine Database Aktif", hc_now["engine"])
    tm2.metric("Status Koneksi", hc_now["status"], delta=f"{hc_now['latency_ms']} ms")
    tm3.metric("Total Temuan Tersimpan", f"{findings_cnt} Temuan")
    tm4.metric("Kapasitas Maks. Upload Stream", "10.240 MB (10 GB)")
