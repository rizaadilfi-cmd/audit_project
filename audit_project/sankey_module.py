import plotly.graph_objects as go
import pandas as pd


def create_sankey_3way_matching(df_matching: pd.DataFrame) -> go.Figure:
    """
    Membangun visualisasi Sankey Diagram interaktif untuk alur rekonsiliasi dana
    3-Way Matching (PO ➔ RR ➔ Invoice).
    """
    nodes = [
        "1. Total Nilai PO Diterbitkan",
        "2. Barang Diterima Sesuai (RR)",
        "3. Selisih Kuantitas (Missing RR)",
        "4. Tagihan Invoice Matched (Valid)",
        "5. Anomali Harga Invoice (Variance)",
        "6. Potensi Kerugian/Discrepancy"
    ]

    if df_matching is not None and not df_matching.empty and 'match_status' in df_matching.columns:
        df = df_matching.copy()
        po_val = (df['qty'] * df['po_price']).sum()
        matched_df = df[df['match_status'] == 'MATCHED']
        qty_mismatch_df = df[df['match_status'] == 'QTY_MISMATCH']
        price_mismatch_df = df[df['match_status'] == 'PRICE_MISMATCH']

        val_matched = float((matched_df['qty'] * matched_df['po_price']).sum())
        val_qty_var = float(qty_mismatch_df['variance_amount'].sum())
        val_price_var = float(price_mismatch_df['variance_amount'].sum())

        # Pastikan nilai positif minimal agar alur Sankey tetap proporsional & terlihat
        val_rr_ok = max(val_matched + val_price_var, 1.0)
        val_qty_var = max(val_qty_var, 1.0)
        val_matched = max(val_matched, 1.0)
        val_price_var = max(val_price_var, 1.0)
        values = [val_rr_ok, val_qty_var, val_matched, val_price_var, val_qty_var, val_price_var]
    else:
        values = [90000000, 10000000, 85000000, 5000000, 10000000, 5000000]

    fig = go.Figure(data=[go.Sankey(
        valueformat=",.0f",
        valuesuffix=" Rp",
        node=dict(
            pad=20,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=nodes,
            color=["#1A365D", "#2B6CB0", "#E53E3E", "#38A169", "#DD6B20", "#C53030"]
        ),
        link=dict(
            source=[0, 0, 1, 1, 2, 4],
            target=[1, 2, 3, 4, 5, 5],
            value=values,
            color=[
                "rgba(43,108,176,0.4)",
                "rgba(229,62,62,0.4)",
                "rgba(56,161,105,0.4)",
                "rgba(221,107,32,0.4)",
                "rgba(197,48,48,0.5)",
                "rgba(197,48,48,0.5)"
            ]
        )
    )])
    fig.update_layout(
        title_text="<b>Alur Rekonsiliasi Dana 3-Way Matching (PO ➔ RR ➔ Invoice) — PT Suryamicrosystem</b>",
        height=420,
        paper_bgcolor="#FAF6EE",
        plot_bgcolor="#FAF6EE",
        font=dict(color="#2B2520", family="Segoe UI, sans-serif")
    )
    return fig
