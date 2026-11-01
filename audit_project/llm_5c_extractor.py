import base64
import io
import json
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from PIL import Image
from config_secrets import get_llm_config
from audit_engine import extract_unstructured_file

# Import SDK Gemini & Claude (dengan graceful fallback)
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import anthropic
except ImportError:
    anthropic = None


def format_idr(val: Any) -> str:
    """
    Memformat angka nominal menjadi format Rupiah standar Indonesia (contoh: Rp. 65.000.000).
    """
    try:
        num = float(val)
        formatted = f"{num:,.0f}".replace(",", ".")
        return f"Rp. {formatted}"
    except Exception:
        return "Rp. 0"


def summarize_uploaded_file_for_5c(uploaded_file) -> Tuple[str, pd.DataFrame, Optional[bytes], str]:
    """
    Mengekstrak konteks audit dari berkas multimodal (.xlsx, .csv, .pdf, .docx, .png, .jpg)
    untuk diumpankan ke AI 5C Extractor.
    Mengembalikan: (ringkasan_teks_audit, dataframe_jika_ada, bytes_gambar_jika_ada, mime_type)
    """
    if uploaded_file is None:
        return "", pd.DataFrame(), None, ""

    fname = getattr(uploaded_file, "name", "dokumen_audit")
    fname_lower = fname.lower()
    raw_bytes = uploaded_file.getvalue()
    uploaded_file.seek(0)

    # 1. Gambar Bukti Audit (.png, .jpg, .jpeg)
    if fname_lower.endswith((".png", ".jpg", ".jpeg")):
        mime = "image/png" if fname_lower.endswith(".png") else "image/jpeg"
        df_ext, ocr_txt = extract_unstructured_file(uploaded_file)
        uploaded_file.seek(0)
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            w, h = img.size
            img_meta = f"Bukti Gambar Fisik/Kuitansi/Invoice '{fname}' (Resolusi {w}x{h} px, {len(raw_bytes)//1024} KB)."
        except Exception:
            img_meta = f"Bukti Gambar Fisik '{fname}' ({len(raw_bytes)//1024} KB)."

        if ocr_txt and "belum terpasang" not in ocr_txt.lower() and "gagal" not in ocr_txt.lower():
            summary_txt = f"{img_meta}\nHasil Pemindaian Teks OCR:\n{ocr_txt.strip()}"
        else:
            summary_txt = (
                f"{img_meta}\nDokumen bukti transaksi visual diunggah untuk pemeriksaan keabsahan otorisasi, "
                f"kuitansi pembayaran, atau fisik barang pada PT Suryamicrosystem."
            )
        return summary_txt, df_ext, raw_bytes, mime

    # 2. Berkas Tabel & Dokumen (.xlsx, .xls, .csv, .pdf, .docx)
    df_ext, doc_txt = extract_unstructured_file(uploaded_file)
    uploaded_file.seek(0)

    parts = [f"Sumber Berkas Lampiran Audit: '{fname}'"]
    if not df_ext.empty:
        parts.append(f"Total Baris Data: {len(df_ext):,} baris | Kolom: {', '.join(map(str, df_ext.columns[:10]))}")
        num_cols = [c for c in df_ext.columns if pd.api.types.is_numeric_dtype(df_ext[c])]
        for nc in num_cols[:4]:
            s = pd.to_numeric(df_ext[nc], errors="coerce").dropna()
            if not s.empty:
                parts.append(
                    f"- Statistik Kolom '{nc}': Total = {format_idr(s.sum())}, "
                    f"Rata-rata = {format_idr(s.mean())}, Maksimum = {format_idr(s.max())}"
                )
        sample_str = df_ext.head(5).to_string(index=False)
        parts.append(f"Sampel 5 Baris Pertama:\n{sample_str}")

    if doc_txt:
        parts.append(f"Isi Teks Dokumen:\n{doc_txt[:2000]}")

    return "\n".join(parts), df_ext, None, ""


def _heuristic_5c_fallback(raw_text: str, note: str = "") -> Dict[str, Any]:
    """
    Fallback ekstraksi 5C berbasis aturan cerdas apabila API Key belum dikonfigurasi
    atau kuota API sedang tidak tersedia, sehingga alur kerja audit tetap berjalan.
    """
    text_lower = (raw_text or "").lower()
    if any(k in text_lower for k in ["kas", "petty cash", "bank", "tunai"]):
        area = "Kas & Bank"
    elif any(k in text_lower for k in ["piutang", "ar", "aging", "ckpn", "tagihan pelanggan", "due_date"]):
        area = "Piutang (AR)"
    elif any(k in text_lower for k in ["po", "purchasing", "vendor", "invoice", "pembelian", "utang", "qty_received", "unit_price"]):
        area = "Utang & Pembelian (AP)"
    elif any(k in text_lower for k in ["journal", "jurnal", "gl", "debit", "credit", "posting_time"]):
        area = "General Ledger"
    else:
        area = "Beban Operasional"

    if any(k in text_lower for k in ["tanpa otorisasi", "fraud", "fiktif", "juta", "miliar", "selisih", "high", "rp."]):
        risk_level = "HIGH"
    elif any(k in text_lower for k in ["terlambat", "aging", "belum", "kurang", "medium"]):
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    clean_cond = raw_text.strip() if raw_text and raw_text.strip() else "Ditemukan penyimpangan pencatatan transaksi pada pemeriksaan sampel dokumen."
    if len(clean_cond) > 650:
        clean_cond = clean_cond[:650] + "..."

    result = {
        "area": area,
        "condition": clean_cond,
        "criteria": f"SOP Pengendalian Internal Keuangan PT Suryamicrosystem & Standar Akuntansi Keuangan (PSAK) terkait {area}.",
        "cause": "Kurangnya verifikasi berjenjang (dual-authorization) serta lemahnya rekonsiliasi otomatis antara dokumen sumber dan pencatatan sistem ERP.",
        "effect": "Potensi salah saji material pada laporan keuangan serta risiko kebocoran kas/kerugian finansial pada PT Suryamicrosystem.",
        "recommendation": f"Perketat otorisasi berjenjang pada modul {area}, terapkan validasi otomatis 3-Way Matching/CAATs, dan tindak lanjuti selisih bersama PIC terkait.",
        "risk_level": risk_level,
    }
    if note:
        result["info_mode"] = note
    return result


def extract_5c_with_claude(
    raw_text: str,
    api_key: str,
    model_name: str = "claude-3-5-sonnet-20241022",
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/png"
) -> Dict[str, Any]:
    """
    Mengekstraksi format 5C (Condition, Criteria, Cause, Effect, Recommendation)
    menggunakan Anthropic Claude API (mendukung teks dan gambar multimodal).
    """
    clean_key = (api_key or "").strip()
    if not clean_key or "your_anthropic_key_here" in clean_key:
        return _heuristic_5c_fallback(
            raw_text,
            note="Mode Simulasi AI Aktif (ANTHROPIC_API_KEY belum diisi dengan key aktif)."
        )
    if not anthropic:
        return _heuristic_5c_fallback(
            raw_text,
            note="Mode Simulasi AI Aktif (SDK anthropic tidak ditemukan)."
        )

    client = anthropic.Anthropic(api_key=clean_key)

    system_prompt = (
        "Anda adalah Senior Financial Auditor & Controller pada PT Suryamicrosystem.\n"
        "Tugas Anda adalah membedah catatan/dokumen/bukti audit mentah dan mengekstraksi temuan menjadi struktur JSON 5C resmi:\n"
        "- area: Nama akun/area keuangan\n"
        "- condition: Fakta/kondisi nyata di lapangan (gunakan format Rp. dengan titik ribuan untuk nominal uang)\n"
        "- criteria: SOP/Regulasi yang dilanggar\n"
        "- cause: Akar penyebab masalah\n"
        "- effect: Dampak/risiko kerugian finansial atau operasional\n"
        "- recommendation: Solusi taktis perbaikan\n"
        "- risk_level: 'HIGH', 'MEDIUM', atau 'LOW'\n\n"
        "Tanggapi HANYA dengan format JSON valid tanpa format markdown atau penjelasan ekstra."
    )

    user_content = []
    if image_bytes:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_mime or "image/png",
                "data": b64_img
            }
        })
    user_content.append({
        "type": "text",
        "text": f'Catatan & Konteks Bukti Audit Mentah:\n"""\n{raw_text}\n"""'
    })

    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=1000,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        content_text = response.content[0].text.strip()
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        elif content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        return json.loads(content_text.strip())
    except Exception as e:
        return {"error": f"Gagal ekstraksi via Claude: {str(e)}"}


def extract_5c_with_gemini(
    raw_text: str,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/png"
) -> Dict[str, Any]:
    """
    Mengekstraksi format 5C menggunakan Google Gemini API (mendukung teks dan gambar multimodal).
    """
    clean_key = (api_key or "").strip()
    if not clean_key or "your_gemini_api_key_here" in clean_key:
        return _heuristic_5c_fallback(
            raw_text,
            note="Mode Simulasi AI Aktif (GEMINI_API_KEY belum diisi dengan key aktif)."
        )
    if not genai:
        return _heuristic_5c_fallback(
            raw_text,
            note="Mode Simulasi AI Aktif (SDK google-genai tidak ditemukan)."
        )

    client = genai.Client(api_key=clean_key)
    prompt = (
        "Anda adalah Senior Financial Auditor pada PT Suryamicrosystem. "
        "Ekstrak bukti/catatan audit berikut menjadi JSON 5C (gunakan format Rp. dengan titik ribuan untuk nominal uang):\n"
        "{\n"
        '  "area": "Nama Area",\n'
        '  "condition": "Fakta lapangan",\n'
        '  "criteria": "SOP/Regulasi",\n'
        '  "cause": "Akar masalah",\n'
        '  "effect": "Dampak kerugian",\n'
        '  "recommendation": "Rekomendasi",\n'
        '  "risk_level": "HIGH / MEDIUM / LOW"\n'
        "}\n"
        f"Konteks & Teks Audit Mentah:\n{raw_text}"
    )
    try:
        contents_payload = [prompt]
        if image_bytes and types is not None:
            contents_payload.append(
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime or "image/png")
            )
        response = client.models.generate_content(
            model=model_name,
            contents=contents_payload,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": f"Gagal ekstraksi via Gemini: {str(e)}"}


def extract_5c_from_text(
    raw_text: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    uploaded_file: Any = None
) -> Dict[str, Any]:
    """
    Fungsi Router Utama: Mengekstraksi 5C secara otomatis berdasarkan provider pilihan (Claude / Gemini).
    Mendukung input catatan teks mentah MAUPUN lampiran berkas (.xlsx, .csv, .docx, .pdf) dan gambar (.png, .jpg).
    """
    file_summary, _, img_bytes, img_mime = summarize_uploaded_file_for_5c(uploaded_file)

    combined_text = (raw_text or "").strip()
    if file_summary:
        combined_text = f"{combined_text}\n\n[EKSTRAKSI BERKAS/GAMBAR LAMPIRAN AUDIT]:\n{file_summary}".strip()

    if not combined_text:
        return {"error": "Catatan audit mentah atau berkas lampiran tidak boleh kosong."}

    llm_cfg = get_llm_config()

    if provider and provider.lower() not in ("claude", "gemini"):
        if api_key is None:
            api_key = provider
            provider = "gemini"

    selected_provider = (provider or llm_cfg.get("provider", "gemini")).lower()

    if selected_provider == "claude":
        key = api_key if api_key is not None else llm_cfg.get("anthropic_api_key", "")
        return extract_5c_with_claude(
            combined_text,
            key,
            llm_cfg.get("claude_model", "claude-3-5-sonnet-20241022"),
            image_bytes=img_bytes,
            image_mime=img_mime
        )
    elif selected_provider == "gemini":
        key = api_key if api_key is not None else llm_cfg.get("gemini_api_key", "")
        return extract_5c_with_gemini(
            combined_text,
            key,
            llm_cfg.get("gemini_model", "gemini-2.5-flash"),
            image_bytes=img_bytes,
            image_mime=img_mime
        )
    else:
        return {"error": f"Provider '{selected_provider}' tidak dikenal. Pilih 'claude' atau 'gemini'."}
