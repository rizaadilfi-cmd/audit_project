import streamlit as st

def render_onboarding_guide():
    """
    Menampilkan wizard panduan interaktif pengguna pertama kali.
    Dapat dilewati (skip) atau ditutup permanen via Session State.
    """
    if "show_onboarding" not in st.session_state:
        st.session_state["show_onboarding"] = True
    if "onboarding_step" not in st.session_state:
        st.session_state["onboarding_step"] = 1

    if not st.session_state["show_onboarding"]:
        return

    steps_content = [
        {
            "title": "👋 Selamat Datang di Audit Engine System",
            "desc": "Aplikasi ini dirancang untuk mendeteksi anomali keuangan, mengeksekusi 3-Way Matching, menghitung CKPN PSAK 71, serta menyusun Laporan Audit (5C Framework) secara otomatis.",
            "icon": "🛡️"
        },
        {
            "title": "🔑 1. Autentikasi Multi-User & Peran",
            "desc": "Sistem memisahkan mode akses: **Auditor Mode** (akses penuh ke pengujian & database) dan **Director Mode** (akses eksekutif read-only untuk presentasi komite audit).",
            "icon": "👥"
        },
        {
            "title": "🤖 2. OCR & LLM 5C Extractor (Gemini AI)",
            "desc": "Unggah berkas transaksi (Excel, PDF, Word, atau Gambar Scan). Gunakan fitur Gemini AI untuk mengubah teks catatan audit mentah menjadi struktur 5C (Condition, Criteria, Cause, Effect, Recommendation) secara otomatis.",
            "icon": "🧠"
        },
        {
            "title": "⚡ 3. Automated Rule Engine & PSAK 71",
            "desc": "Jalankan 3-Way Matching (PO vs RR vs Invoice), pemindaian jurnal di luar jam kerja/SoD, dan kalkulasi otomatis matriks aging piutang (CKPN PSAK 71 / IFRS 9).",
            "icon": "📈"
        },
        {
            "title": "🚀 4. Deliverable Exporter & Alerting",
            "desc": "Ekspor Laporan Opini PDF, Slide Presentasi Direksi (PPTX), Excel 2 Sheet dengan Donut Chart Native, dan kirimkan laporan via Email SMTP atau WhatsApp via n8n Webhook.",
            "icon": "📤"
        }
    ]

    current_step = st.session_state["onboarding_step"]
    content = steps_content[current_step - 1]

    with st.container():
        st.info(f"### {content['icon']} Panduan Fitur Sistem — Langkah {current_step} dari {len(steps_content)}: {content['title']}\n\n{content['desc']}")
        
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if current_step > 1:
                if st.button("⬅️ Sebelumnya", key="btn_prev_step"):
                    st.session_state["onboarding_step"] -= 1
                    st.rerun()
        with col2:
            if current_step < len(steps_content):
                if st.button("Selanjutnya ➡️", key="btn_next_step"):
                    st.session_state["onboarding_step"] += 1
                    st.rerun()
            else:
                if st.button("Selesai Panduan 🎉", key="btn_finish_step"):
                    st.session_state["show_onboarding"] = False
                    st.rerun()
        with col3:
            if st.button("⏩ Lewati Panduan (Skip)", key="btn_skip_step"):
                st.session_state["show_onboarding"] = False
                st.rerun()
        st.divider()