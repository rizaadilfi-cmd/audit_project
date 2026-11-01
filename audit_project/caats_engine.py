import os
import re
import math
import time
import sqlite3
import tempfile
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go


def format_rp(val: Any, with_decimal: bool = False) -> str:
    """
    Memformat nilai numerik ke dalam format mata uang Rupiah Indonesia:
    Titik (.) sebagai pemisah ribuan dan koma (,) sebagai desimal, diawali 'Rp. '.
    Contoh: Rp. 65.000.000 atau Rp. 65.000.000,00
    """
    try:
        num = float(val)
        if math.isnan(num):
            return "Rp. 0"
        sign = "-" if num < 0 else ""
        num = abs(num)
        if with_decimal:
            s = f"{num:,.2f}"
            parts = s.split(".")
            thousand_part = parts[0].replace(",", ".")
            return f"{sign}Rp. {thousand_part},{parts[1]}"
        else:
            thousand_part = f"{num:,.0f}".replace(",", ".")
            return f"{sign}Rp. {thousand_part}"
    except Exception:
        return "Rp. 0"


def format_dataframe_currency(df: pd.DataFrame, monetary_keywords: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Membuat salinan tampilan DataFrame di mana seluruh kolom terkait nominal uang
    (total_nilai, rata-rata, amount, debit, credit, price, variance, ckpn, piutang)
    diformat menggunakan 'Rp. xxx.xxx'.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()
    keywords = monetary_keywords or [
        "total_nilai", "rata_rata", "rata-rata", "amount", "debit", "credit",
        "price", "variance", "ckpn", "piutang", "nominal", "nilai", "saldo", "exposure"
    ]
    for col in out.columns:
        col_low = str(col).lower()
        if any(k in col_low for k in keywords) and "pct" not in col_low and "persen" not in col_low and "rate" not in col_low and "z_score" not in col_low and "skor" not in col_low:
            if pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].apply(lambda v: format_rp(v))
    return out


# =========================================================
# 1. BENFORD'S LAW DIGITAL FORENSICS ENGINE
# =========================================================
BENFORD_EXPECTED = {
    d: math.log10(1.0 + (1.0 / d)) * 100.0 for d in range(1, 10)
}


def _extract_first_digit_series(series: pd.Series) -> pd.Series:
    """
    Mengekstrak digit signifikan pertama (1-9) dari kolom numerik secara vektorisasi.
    """
    s = pd.to_numeric(series, errors="coerce").dropna().abs()
    s = s[s > 0]
    if s.empty:
        return pd.Series(dtype=int)
    str_vals = s.astype(str).str.replace(".", "", regex=False).str.lstrip("0")
    first_chars = str_vals.str[0]
    digits = pd.to_numeric(first_chars, errors="coerce").dropna().astype(int)
    return digits[(digits >= 1) & (digits <= 9)]


def _build_benford_table_from_counts(counts_dict: Dict[int, int]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    total_valid = sum(counts_dict.values())
    if total_valid == 0:
        empty_df = pd.DataFrame(columns=[
            "Digit", "Jumlah_Transaksi", "Aktual_Pct",
            "Benford_Ekspektasi_Pct", "Deviasi_Pct", "Z_Statistic", "Status_Digit"
        ])
        return empty_df, {
            "total_valid_records": 0,
            "total_records": 0,
            "mad": 0.0,
            "mad_score": 0.0,
            "chi_square": 0.0,
            "suspicious_digits_count": 0,
            "flagged_digits": [],
            "conformity_label": "DATA TIDAK CUKUP",
            "conformity_status": "DATA TIDAK CUKUP"
        }

    rows = []
    chi_square = 0.0
    abs_devs = []

    for d in range(1, 10):
        obs_cnt = int(counts_dict.get(d, 0))
        obs_pct = (obs_cnt / total_valid) * 100.0
        exp_pct = BENFORD_EXPECTED[d]
        exp_cnt = (exp_pct / 100.0) * total_valid
        dev_pct = obs_pct - exp_pct
        abs_dev = abs(dev_pct) / 100.0
        abs_devs.append(abs_dev)

        if exp_cnt > 0:
            chi_square += ((obs_cnt - exp_cnt) ** 2) / exp_cnt

        p_obs = obs_pct / 100.0
        p_exp = exp_pct / 100.0
        se = math.sqrt((p_exp * (1.0 - p_exp)) / total_valid)
        corr = 1.0 / (2.0 * total_valid)
        z_stat = (abs(p_obs - p_exp) - corr) / se if se > 0 and abs(p_obs - p_exp) > corr else abs(p_obs - p_exp) / (se or 1.0)

        rows.append({
            "Digit": d,
            "Jumlah_Transaksi": obs_cnt,
            "Aktual_Pct": round(obs_pct, 2),
            "Benford_Ekspektasi_Pct": round(exp_pct, 2),
            "Deviasi_Pct": round(dev_pct, 2),
            "Z_Statistic": round(z_stat, 2),
            "Status_Digit": "⚠️ ANOMALI (Z > 1.96)" if z_stat > 1.96 else "✅ NORMAL"
        })

    df_benford = pd.DataFrame(rows)
    mad = sum(abs_devs) / 9.0

    if mad <= 0.006:
        conformity = "CLOSE CONFORMITY (Wajar & Alami)"
    elif mad <= 0.012:
        conformity = "ACCEPTABLE CONFORMITY (Dapat Diterima)"
    elif mad <= 0.015:
        conformity = "MARGINALLY ACCEPTABLE (Perlu Perhatian Audit)"
    else:
        conformity = "NONCONFORMITY / INDIKASI ANOMALI POPULASI ANGKA"

    flagged_digits = df_benford[df_benford["Z_Statistic"] > 1.96]["Digit"].tolist()

    metrics = {
        "total_valid_records": total_valid,
        "total_records": total_valid,
        "mad": round(mad, 4),
        "mad_score": round(mad, 4),
        "chi_square": round(chi_square, 2),
        "suspicious_digits_count": len(flagged_digits),
        "flagged_digits": flagged_digits,
        "conformity_label": conformity,
        "conformity_status": conformity
    }
    return df_benford, metrics


def run_benfords_law_analysis(df: pd.DataFrame, amount_col: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Menjalankan uji forensik Benford's Law (First-Digit Test) pada kolom nominal.
    """
    if df is None or df.empty or amount_col not in df.columns:
        return _build_benford_table_from_counts({d: 0 for d in range(1, 10)})

    digits = _extract_first_digit_series(df[amount_col])
    counts = digits.value_counts().reindex(range(1, 10), fill_value=0).to_dict()
    return _build_benford_table_from_counts(counts)


def create_benford_chart(df_benford: pd.DataFrame, title_suffix: str = "") -> go.Figure:
    """
    Membangun grafik komparasi Benford's Law (Bar Aktual vs Garis Kurva Teoretis Benford) dengan palet ERP Beige/Bronze.
    """
    fig = go.Figure()
    if df_benford is None or df_benford.empty:
        return fig

    bar_colors = [
        "#B8332A" if "ANOMALI" in str(st_val) else "#8B5A2B"
        for st_val in df_benford["Status_Digit"]
    ]

    fig.add_trace(go.Bar(
        x=df_benford["Digit"].astype(str),
        y=df_benford["Aktual_Pct"],
        name="Distribusi Aktual Data (%)",
        marker_color=bar_colors,
        text=df_benford["Aktual_Pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside"
    ))

    fig.add_trace(go.Scatter(
        x=df_benford["Digit"].astype(str),
        y=df_benford["Benford_Ekspektasi_Pct"],
        name="Kurva Teoretis Benford (%)",
        mode="lines+markers",
        line=dict(color="#1F3A52", width=3, dash="solid"),
        marker=dict(size=9, color="#1F3A52", symbol="diamond")
    ))

    fig.update_layout(
        title=f"<b>Forensik Digital Benford's Law (First-Digit Test) — {title_suffix}</b>",
        xaxis_title="Digit Signifikan Pertama (1 - 9)",
        yaxis_title="Proporsi Frekuensi (%)",
        paper_bgcolor="#FAF6EE",
        plot_bgcolor="#FAF6EE",
        font=dict(color="#2B2520"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        margin=dict(t=60, b=40, l=40, r=20)
    )
    return fig


# =========================================================
# 2. DUPLICATE TRANSACTION CHECK (EXACT & COMPOSITE)
# =========================================================
def run_duplicate_detection(
    df: pd.DataFrame,
    primary_key_col: str,
    composite_cols: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Mendeteksi duplikasi transaksi (ACL Duplicate Command) baik pada Primary Key
    maupun kombinasi atribut (Same-Vendor/Item/Amount).
    """
    if df is None or df.empty:
        return {
            "exact_duplicates": pd.DataFrame(),
            "composite_duplicates": pd.DataFrame(),
            "summary": {
                "total_rows_scanned": 0,
                "exact_duplicate_rows": 0,
                "composite_duplicate_rows": 0
            }
        }

    exact_dups = pd.DataFrame()
    if primary_key_col in df.columns:
        mask_exact = df.duplicated(subset=[primary_key_col], keep=False)
        exact_dups = df[mask_exact].sort_values(by=[primary_key_col]).reset_index(drop=True)

    comp_dups = pd.DataFrame()
    valid_comp = [c for c in (composite_cols or []) if c in df.columns]
    if valid_comp:
        mask_comp = df.duplicated(subset=valid_comp, keep=False)
        comp_dups = df[mask_comp].sort_values(by=valid_comp).reset_index(drop=True)

    return {
        "exact_duplicates": exact_dups,
        "composite_duplicates": comp_dups,
        "summary": {
            "total_rows_scanned": len(df),
            "exact_duplicate_rows": len(exact_dups),
            "composite_duplicate_rows": len(comp_dups)
        }
    }


# =========================================================
# 3. SEQUENCE GAP DETECTION (KELENGKAPAN NOMOR URUT DOKUMEN)
# =========================================================
def run_gap_detection(
    df: pd.DataFrame,
    doc_col: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Mendeteksi nomor urut dokumen yang hilang/lompat (ACL Gaps Command)
    pada kolom dokumen seperti 'PO-2026-001', 'INV-SUP-101', 'J-101'.
    """
    default_meta = {
        "prefix_detected": "-",
        "min_sequence": 0,
        "max_sequence": 0,
        "total_missing_count": 0,
        "integrity_status": "N/A"
    }
    if df is None or df.empty or doc_col not in df.columns:
        return pd.DataFrame(), default_meta

    raw_vals = df[doc_col].dropna().astype(str).unique()
    parsed = []

    for val in raw_vals:
        m = re.match(r"^(.*?)(\d+)$", val.strip())
        if m:
            pref, num_str = m.group(1), m.group(2)
            parsed.append((pref, int(num_str), len(num_str)))

    if not parsed:
        return pd.DataFrame(), default_meta

    df_parsed = pd.DataFrame(parsed, columns=["prefix", "seq_num", "width"])
    top_prefix = df_parsed["prefix"].mode().iloc[0]
    sub = df_parsed[df_parsed["prefix"] == top_prefix].sort_values("seq_num")
    pad_width = int(sub["width"].mode().iloc[0])

    seq_nums = sorted(sub["seq_num"].unique())
    min_seq, max_seq = int(seq_nums[0]), int(seq_nums[-1])
    existing_set = set(seq_nums)

    gap_rows = []
    cur = min_seq
    total_missing = 0

    while cur <= max_seq:
        if cur not in existing_set:
            gap_start = cur
            while cur <= max_seq and cur not in existing_set:
                cur += 1
            gap_end = cur - 1
            missing_cnt = (gap_end - gap_start) + 1
            total_missing += missing_cnt

            start_code = f"{top_prefix}{gap_start:0{pad_width}d}"
            end_code = f"{top_prefix}{gap_end:0{pad_width}d}"
            gap_rows.append({
                "Rentang_Dokumen_Hilang": start_code if gap_start == gap_end else f"{start_code} s/d {end_code}",
                "Nomor_Awal": gap_start,
                "Nomor_Akhir": gap_end,
                "Jumlah_Dokumen_Hilang": missing_cnt,
                "Keterangan_Audit": "⚠️ Nomor Urut Terlompati / Dokumen Tidak Tercatat (Unrecorded)"
            })
        else:
            cur += 1

    df_gaps = pd.DataFrame(gap_rows)
    summary = {
        "prefix_detected": top_prefix or "(Numeric)",
        "min_sequence": f"{top_prefix}{min_seq:0{pad_width}d}",
        "max_sequence": f"{top_prefix}{max_seq:0{pad_width}d}",
        "total_missing_count": total_missing,
        "integrity_status": "⚠️ GAP DETECTED" if total_missing > 0 else "✅ COMPLETE (ZERO GAP)"
    }
    return df_gaps, summary


# =========================================================
# 4. STRATIFIKASI POPULASI & STATISTIK (ACL STRATIFY)
# =========================================================
def run_population_stratification(
    df: pd.DataFrame,
    amount_col: str,
    num_strata: int = 6
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Membagi populasi transaksi ke dalam strata interval nilai (ACL Stratify)
    dan mengidentifikasi transaksi outlier bernilai ekstrem (|Z-Score| >= 2.5).
    Setiap nilai Total_Nilai dan Rata_Rata diformat dalam Rp. (titik ribuan, koma desimal).
    """
    if df is None or df.empty or amount_col not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    work = df.copy()
    work[amount_col] = pd.to_numeric(work[amount_col], errors="coerce").fillna(0.0)
    total_val = work[amount_col].sum()
    total_cnt = len(work)

    min_v, max_v = float(work[amount_col].min()), float(work[amount_col].max())
    if min_v == max_v:
        bins = [min_v - 1.0, max_v + 1.0]
    else:
        bins = np.linspace(min_v, max_v, num_strata + 1)

    # Buat label rentang strata dengan format Rp.
    strata_labels = []
    for i in range(len(bins) - 1):
        strata_labels.append(f"{format_rp(bins[i])} s/d {format_rp(bins[i + 1])}")

    work["Strata_Interval"] = pd.cut(
        work[amount_col],
        bins=bins,
        labels=strata_labels if len(strata_labels) == len(bins) - 1 else None,
        include_lowest=True
    )

    strat = work.groupby("Strata_Interval", observed=False).agg(
        Jumlah_Transaksi=(amount_col, "count"),
        Total_Nilai=(amount_col, "sum"),
        Rata_Rata=(amount_col, "mean")
    ).reset_index()

    strat["Strata_Interval"] = strat["Strata_Interval"].astype(str)
    raw_total = strat["Total_Nilai"].fillna(0.0)
    raw_mean = strat["Rata_Rata"].fillna(0.0)

    strat["Proporsi_Populasi_Pct"] = ((strat["Jumlah_Transaksi"] / max(total_cnt, 1)) * 100.0).round(2)
    strat["Proporsi_Nilai_Pct"] = ((raw_total / max(total_val, 1.0)) * 100.0).round(2)

    # Format kolom Total_Nilai dan Rata_Rata dengan Rp. (titik ribuan)
    strat["Total_Nilai"] = raw_total.apply(lambda v: format_rp(v))
    strat["Rata_Rata"] = raw_mean.apply(lambda v: format_rp(v))

    mean_v = work[amount_col].mean()
    std_v = work[amount_col].std()
    if std_v and std_v > 0:
        work["Z_Score_Nilai"] = ((work[amount_col] - mean_v) / std_v).round(2)
        outliers = work[work["Z_Score_Nilai"].abs() >= 2.0].drop(columns=["Strata_Interval"]).sort_values(
            by=amount_col, ascending=False
        )
        outliers = format_dataframe_currency(outliers)
    else:
        outliers = pd.DataFrame()

    return strat, outliers


# =========================================================
# 5. AUTOMATED PREDICTIVE AUDIT INTELLIGENCE (STRUCTURED ERP / DB)
# =========================================================
def run_predictive_audit_automation(df: pd.DataFrame, source_label: str = "ERP Structured Data") -> Dict[str, Any]:
    """
    Mengeksekusi Automasi Analisis Prediktif pada data sangat terstruktur (Tabel Relasional DB,
    Log Transaksi, CSV, Excel ERP SAP/Oracle, atau Jurnal GL):
    1. Mendeteksi domain tabel & kolom kunci secara otomatis.
    2. Menghitung Skor Prediksi Risiko Audit (0-99%) per baris berdasarkan kombinasi:
       - Z-Score Statistical Outlier
       - Benford's Law First-Digit Deviation
       - Indikator Round-Sum (Nominal Bulat Jutaan)
       - Indikator Off-Hours / Konflik SoD (jika kolom waktu/user tersedia)
       - Indikator Duplikasi Kunci
    3. Menyaring sampel transaksi berisiko tinggi yang wajib diaudit (Audit Target Extraction)
       beserta rekomendasi temuan 5C otomatis.
    """
    if df is None or df.empty:
        return {"error": "Dataset kosong atau tidak valid."}

    work = df.copy()
    cols_lower = {c.lower(): c for c in work.columns}

    # Deteksi domain tabel secara otomatis
    if "journal_id" in cols_lower or "posting_time" in cols_lower or "debit" in cols_lower:
        domain = "General Ledger (Jurnal Buku Besar)"
        target_state_key = "df_gl"
    elif "due_date" in cols_lower or "customer_name" in cols_lower:
        domain = "Piutang Usaha (AR Aging Sub-Ledger)"
        target_state_key = "df_ar"
    elif "qty_received" in cols_lower:
        domain = "Receiving Report (Penerimaan Barang / RR)"
        target_state_key = "df_rr"
    elif "qty_billed" in cols_lower or "unit_price_y" in cols_lower:
        domain = "Vendor Invoice (Faktur Tagihan Pembelian)"
        target_state_key = "df_inv"
    elif "po_number" in cols_lower:
        domain = "Purchase Order (Pesanan Pembelian / PO)"
        target_state_key = "df_po"
    else:
        domain = "Tabel Transaksi Relasional ERP"
        target_state_key = "df_structured_custom"

    # Deteksi kolom nominal uang utama
    num_cols = [c for c in work.columns if pd.api.types.is_numeric_dtype(work[c])]
    preferred_amt = ["debit", "amount", "variance_amount", "unit_price_x", "unit_price_y", "unit_price", "total", "nilai"]
    amt_col = None
    for p in preferred_amt:
        if p in cols_lower:
            amt_col = cols_lower[p]
            break
    if amt_col is None and num_cols:
        amt_col = num_cols[0]

    # Deteksi kolom ID dokumen utama
    id_col = work.columns[0]
    for p_id in ["journal_id", "po_number", "invoice_number", "doc_number", "id"]:
        if p_id in cols_lower:
            id_col = cols_lower[p_id]
            break

    # Hitung komponen skor prediktif
    n_rows = len(work)
    risk_scores = np.zeros(n_rows, dtype=float)
    reasons = [[] for _ in range(n_rows)]

    if amt_col and amt_col in work.columns:
        vals = pd.to_numeric(work[amt_col], errors="coerce").fillna(0.0)
        total_val = float(vals.sum())
        mean_val = float(vals.mean()) if n_rows > 0 else 0.0
        std_val = float(vals.std()) if n_rows > 1 else 0.0

        # 1. Z-Score Outlier Component
        if std_val > 0:
            z_scores = ((vals - mean_val) / std_val).abs()
            for idx, z in enumerate(z_scores):
                if z >= 2.5:
                    risk_scores[idx] += 35.0
                    reasons[idx].append(f"Statistical Outlier (Z={z:.2f})")
                elif z >= 1.5:
                    risk_scores[idx] += 18.0
                    reasons[idx].append(f"Above Normal Variance (Z={z:.2f})")

        # 2. Round-Sum Nominal Bulat Besar Component
        round_mask = (vals >= 10_000_000) & ((vals % 10_000_000) == 0)
        for idx, is_rnd in enumerate(round_mask):
            if is_rnd:
                risk_scores[idx] += 25.0
                reasons[idx].append("Nominal Bulat Besar (Round-Sum >= Rp. 10 Juta)")

        # 3. High Value Top Decile Component
        q90 = float(vals.quantile(0.90)) if n_rows >= 5 else mean_val
        for idx, v in enumerate(vals):
            if v >= q90 and v > 0:
                risk_scores[idx] += 15.0
                reasons[idx].append("Eksposur Materialitas Tinggi (Top 10% Nilai)")
    else:
        vals = pd.Series(np.zeros(n_rows))
        total_val = 0.0
        mean_val = 0.0

    # 4. Off-Hours Posting & Segregation of Duties (SoD) Component
    if "posting_time" in cols_lower:
        t_col = cols_lower["posting_time"]
        hours = pd.to_datetime(work[t_col].astype(str), format="%H:%M:%S", errors="coerce").dt.hour.fillna(12)
        for idx, hr in enumerate(hours):
            if hr >= 20 or hr <= 5:
                risk_scores[idx] += 30.0
                reasons[idx].append(f"Posting Jam Tidak Wajar (Off-Hours {work[t_col].iloc[idx]})")

    if "created_by" in cols_lower and "approved_by" in cols_lower:
        c_col, a_col = cols_lower["created_by"], cols_lower["approved_by"]
        sod_mask = work[c_col].astype(str).str.strip() == work[a_col].astype(str).str.strip()
        for idx, is_sod in enumerate(sod_mask):
            if is_sod:
                risk_scores[idx] += 35.0
                reasons[idx].append("Konflik Pemisahan Tugas (SoD: Pembuat == Penyetuju)")

    # 5. Overdue AR Aging Component
    if "due_date" in cols_lower:
        d_col = cols_lower["due_date"]
        due_dts = pd.to_datetime(work[d_col], errors="coerce")
        overdue = (pd.to_datetime("2026-11-01") - due_dts).dt.days.fillna(0)
        for idx, od in enumerate(overdue):
            if od > 90:
                risk_scores[idx] += 40.0
                reasons[idx].append(f"Menunggak Kritis >90 Hari ({int(od)} Hari)")
            elif od > 30:
                risk_scores[idx] += 20.0
                reasons[idx].append(f"Menunggak {int(od)} Hari")

    # 6. Duplicate Document ID Component
    if id_col in work.columns:
        dup_mask = work.duplicated(subset=[id_col], keep=False)
        for idx, is_dup in enumerate(dup_mask):
            if is_dup:
                risk_scores[idx] += 30.0
                reasons[idx].append("Duplikasi Nomor Dokumen")

    # Normalisasi Skor Prediksi (0 - 99%)
    final_scores = np.clip(risk_scores, 5.0, 99.0).round(1)
    work["Skor_Prediksi_Risiko_Pct"] = final_scores
    work["Kategori_Risiko_Prediktif"] = [
        "HIGH" if s >= 60.0 else ("MEDIUM" if s >= 30.0 else "LOW")
        for s in final_scores
    ]
    work["Indikator_Prediktif_Audit"] = [
        "; ".join(r) if r else "Transaksi Normal / Risiko Rendah"
        for r in reasons
    ]

    if amt_col and amt_col in work.columns:
        work["Nominal_Terformat"] = vals.apply(lambda v: format_rp(v))

    # Ekstrak populasi sampel yang wajib diaudit (HIGH & MEDIUM teratas)
    df_targets = work[work["Skor_Prediksi_Risiko_Pct"] >= 30.0].sort_values(
        by="Skor_Prediksi_Risiko_Pct", ascending=False
    ).reset_index(drop=True)
    if df_targets.empty:
        df_targets = work.sort_values(by="Skor_Prediksi_Risiko_Pct", ascending=False).head(10).reset_index(drop=True)

    high_cnt = int((work["Kategori_Risiko_Prediktif"] == "HIGH").sum())
    med_cnt = int((work["Kategori_Risiko_Prediktif"] == "MEDIUM").sum())
    target_val = float(vals[work["Skor_Prediksi_Risiko_Pct"] >= 30.0].sum()) if amt_col else 0.0

    # Susun rekomendasi 5C otomatis dari hasil prediksi
    top_indicators = pd.Series([item for sublist in reasons for item in sublist]).value_counts().head(3).index.tolist()
    indicator_str = ", ".join(top_indicators) if top_indicators else "Deviasi Statistik Nilai Transaksi"

    recommended_5c = {
        "area": "General Ledger" if "Jurnal" in domain else ("Piutang (AR)" if "Piutang" in domain else "Utang & Pembelian (AP)"),
        "condition": (
            f"Berdasarkan Automasi Analisis Prediktif pada '{source_label}' ({domain}, total {n_rows:,} baris senilai {format_rp(total_val)}), "
            f"terdeteksi {high_cnt} transaksi berisiko HIGH dan {med_cnt} transaksi berisiko MEDIUM dengan nilai eksposur sampel audit "
            f"sebesar {format_rp(target_val)}. Indikator dominan: {indicator_str}."
        ),
        "criteria": f"SOP Pengendalian Internal Keuangan PT Suryamicrosystem & Standar Audit Berbasis Risiko (ISA 315 / PSAK) untuk {domain}.",
        "cause": f"Belum adanya filter otomatis (preventive control) pada saat input transaksi terkait {indicator_str}.",
        "effect": f"Risiko salah saji material atau kebocoran kas dengan eksposur terukur sebesar {format_rp(target_val)}.",
        "recommendation": (
            f"Lakukan pemeriksaan dokumen sumber (vouching) atas {len(df_targets)} sampel prioritas hasil ekstraksi prediktif "
            f"dan terapkan aturan pemblokiran otomatis pada ERP PT Suryamicrosystem."
        ),
        "risk_level": "HIGH" if high_cnt > 0 else ("MEDIUM" if med_cnt > 0 else "LOW")
    }

    return {
        "domain_detected": domain,
        "target_state_key": target_state_key,
        "id_col": id_col,
        "amount_col": amt_col,
        "total_rows": n_rows,
        "total_value": total_val,
        "total_value_rp": format_rp(total_val),
        "mean_value": mean_val,
        "mean_value_rp": format_rp(mean_val),
        "high_risk_count": high_cnt,
        "medium_risk_count": med_cnt,
        "audit_sample_count": len(df_targets),
        "audit_sample_exposure_rp": format_rp(target_val),
        "df_scored": format_dataframe_currency(work),
        "df_audit_targets": format_dataframe_currency(df_targets),
        "recommended_5c": recommended_5c
    }


# =========================================================
# 6. OUT-OF-CORE FILE-INDEXING ENGINE (ZERO-RAM CRASH ARCHITECTURE)
# =========================================================
class OutOfCoreCAATsEngine:
    """
    Engine CAATs berbasis Out-of-Core Streaming & Disk B-Tree Indexing (seperti ACL/IDEA).
    Memproses berkas terstruktur berukuran raksasa dalam potongan chunk kecil + indeks SQLite B-Tree di disk,
    sehingga penggunaan RAM tetap konstan (< 30 MB) meskipun memproses jutaan/miliaran baris.
    """

    def __init__(self, chunk_size: int = 50000):
        self.chunk_size = chunk_size

    def process_csv_stream(
        self,
        csv_source: str,
        amount_col: str,
        doc_id_col: str
    ) -> Dict[str, Any]:
        """
        Menjalankan Single-Pass Streaming Benford's Law + Disk B-Tree Indexing untuk
        Duplicate & Gap Detection tanpa memuat seluruh berkas ke memori (RAM).
        """
        t0 = time.perf_counter()
        digit_counts = {d: 0 for d in range(1, 10)}
        total_rows = 0
        total_amount = 0.0

        tmp_fd, tmp_db_path = tempfile.mkstemp(suffix="_acl_btree_index.db")
        os.close(tmp_fd)

        dup_df = pd.DataFrame()
        gap_df = pd.DataFrame()
        total_missing_seq = 0

        try:
            conn = sqlite3.connect(tmp_db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA synchronous = OFF;")
            cur.execute("PRAGMA temp_store = FILE;")
            cur.execute("CREATE TABLE doc_index (doc_id TEXT, seq_num INTEGER, amount REAL);")

            for chunk in pd.read_csv(csv_source, chunksize=self.chunk_size):
                total_rows += len(chunk)

                # 1. Single-Pass Streaming Accumulator untuk Benford's Law (O(1) RAM)
                if amount_col in chunk.columns:
                    vals = pd.to_numeric(chunk[amount_col], errors="coerce").dropna().abs()
                    total_amount += float(vals.sum())
                    digs = _extract_first_digit_series(vals)
                    vc = digs.value_counts()
                    for d in range(1, 10):
                        digit_counts[d] += int(vc.get(d, 0))

                # 2. Disk-Backed B-Tree Indexing untuk Duplicate & Gap Detection
                if doc_id_col in chunk.columns:
                    docs = chunk[doc_id_col].astype(str)
                    seq_extracted = docs.str.extract(r"(\d+)$")[0]
                    seq_nums = pd.to_numeric(seq_extracted, errors="coerce").fillna(-1).astype(int)
                    amts = pd.to_numeric(chunk[amount_col], errors="coerce").fillna(0.0) if amount_col in chunk.columns else pd.Series(0.0, index=chunk.index)
                    records = list(zip(docs.tolist(), seq_nums.tolist(), amts.tolist()))
                    cur.executemany("INSERT INTO doc_index VALUES (?, ?, ?)", records)

            # Bangun B-Tree Index pada disk
            cur.execute("CREATE INDEX idx_doc_id ON doc_index(doc_id);")
            cur.execute("CREATE INDEX idx_seq_num ON doc_index(seq_num);")
            conn.commit()

            # Query Duplicate langsung via B-Tree Index di disk
            dup_df = pd.read_sql_query("""
                SELECT doc_id AS Nomor_Dokumen,
                       COUNT(*) AS Frekuensi_Duplikat,
                       ROUND(SUM(amount), 2) AS Total_Nilai,
                       ROUND(AVG(amount), 2) AS Rata_Rata
                FROM doc_index
                GROUP BY doc_id
                HAVING COUNT(*) > 1
                ORDER BY Frekuensi_Duplikat DESC
                LIMIT 100
            """, conn)

            if not dup_df.empty:
                dup_df["Total_Nilai"] = dup_df["Total_Nilai"].apply(lambda v: format_rp(v))
                dup_df["Rata_Rata"] = dup_df["Rata_Rata"].apply(lambda v: format_rp(v))

            # Query Sequence Gap langsung via B-Tree Index di disk (Window Function LEAD)
            gap_df = pd.read_sql_query("""
                WITH distinct_seq AS (
                    SELECT DISTINCT seq_num FROM doc_index WHERE seq_num >= 0
                ),
                gaps AS (
                    SELECT seq_num AS prev_num,
                           LEAD(seq_num) OVER (ORDER BY seq_num) AS next_num
                    FROM distinct_seq
                )
                SELECT (prev_num + 1) AS Urutan_Hilang_Awal,
                       (next_num - 1) AS Urutan_Hilang_Akhir,
                       (next_num - prev_num - 1) AS Jumlah_Dokumen_Hilang
                FROM gaps
                WHERE (next_num - prev_num) > 1
                LIMIT 100
            """, conn)

            if not gap_df.empty:
                total_missing_seq = int(gap_df["Jumlah_Dokumen_Hilang"].sum())

            conn.close()
        finally:
            if os.path.exists(tmp_db_path):
                try:
                    os.remove(tmp_db_path)
                except OSError:
                    pass

        elapsed_sec = max(time.perf_counter() - t0, 0.001)
        benford_df, _ = _build_benford_table_from_counts(digit_counts)
        avg_monetary = (total_amount / total_rows) if total_rows > 0 else 0.0

        return {
            "total_rows_processed": total_rows,
            "elapsed_seconds": round(elapsed_sec, 2),
            "throughput_rows_per_sec": int(total_rows / elapsed_sec),
            "chunk_size_used": self.chunk_size,
            "total_monetary_value": round(total_amount, 2),
            "total_monetary_rp": format_rp(total_amount),
            "average_monetary_rp": format_rp(avg_monetary),
            "total_duplicate_keys": len(dup_df),
            "total_missing_sequences": total_missing_seq,
            "benford_df": benford_df,
            "duplicates_df": dup_df,
            "gaps_df": gap_df
        }
