import pandas as pd
import numpy as np


def calculate_psak71_ckpn(df_ar: pd.DataFrame, snapshot_date: str = "2026-11-01") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Menghitung Umur Piutang (AR Aging) dan Cadangan Kerugian Penurunan Nilai (CKPN)
    berdasarkan matriks Expected Credit Loss (ECL) PSAK 71 / IFRS 9.
    """
    labels = ['Current', '1-30 Hari', '31-60 Hari', '61-90 Hari', '>90 Hari']
    ecl_rates = [0.005, 0.02, 0.05, 0.15, 0.50]
    rate_map = dict(zip(labels, ecl_rates))

    if df_ar.empty:
        empty_summary = pd.DataFrame({
            'aging_bucket': labels,
            'total_piutang': [0.0] * len(labels),
            'ecl_rate': ecl_rates,
            'total_ckpn': [0.0] * len(labels),
            'jumlah_inv': [0] * len(labels)
        })
        return df_ar.copy(), empty_summary

    df = df_ar.copy()
    df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    snapshot = pd.to_datetime(snapshot_date)

    df['overdue_days'] = (snapshot - df['due_date']).dt.days.fillna(0).clip(lower=0).astype(int)

    conditions = [
        (df['overdue_days'] == 0),
        (df['overdue_days'] >= 1) & (df['overdue_days'] <= 30),
        (df['overdue_days'] >= 31) & (df['overdue_days'] <= 60),
        (df['overdue_days'] >= 61) & (df['overdue_days'] <= 90),
        (df['overdue_days'] > 90)
    ]

    df['aging_bucket'] = np.select(conditions, labels, default='Current')
    df['ecl_rate'] = np.select(conditions, ecl_rates, default=0.005)
    df['ckpn_required'] = df['amount'] * df['ecl_rate']

    summary = df.groupby('aging_bucket').agg(
        total_piutang=('amount', 'sum'),
        total_ckpn=('ckpn_required', 'sum'),
        jumlah_inv=('invoice_number', 'count')
    ).reindex(labels).reset_index()

    summary['total_piutang'] = summary['total_piutang'].fillna(0.0)
    summary['total_ckpn'] = summary['total_ckpn'].fillna(0.0)
    summary['jumlah_inv'] = summary['jumlah_inv'].fillna(0).astype(int)
    summary['ecl_rate'] = summary['aging_bucket'].map(rate_map)

    # Susun urutan kolom secara rapi
    summary = summary[['aging_bucket', 'total_piutang', 'ecl_rate', 'total_ckpn', 'jumlah_inv']]

    return df, summary
