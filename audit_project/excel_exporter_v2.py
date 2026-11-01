import xlsxwriter
import io
import pandas as pd


def generate_full_audit_excel(findings_data: list, mismatch_df: pd.DataFrame) -> bytes:
    """
    Menghasilkan berkas Excel 2-Sheet:
    - Sheet 1: Action Plan Matrix + Native Donut Chart Distribusi Risiko
    - Sheet 2: 3-Way Matching Mismatches
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1A365D'})
    sub_fmt = workbook.add_format({'italic': True, 'font_size': 10, 'font_color': '#4A5568'})
    header_fmt = workbook.add_format({
        'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#1A365D',
        'align': 'center', 'valign': 'vcenter', 'border': 1
    })
    cell_fmt = workbook.add_format({'border': 1, 'valign': 'top', 'font_size': 9.5, 'text_wrap': True})
    center_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'top', 'font_size': 9.5})
    num_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'right', 'valign': 'top', 'font_size': 9.5})

    high_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'bold': True, 'align': 'center', 'valign': 'top', 'border': 1})
    med_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500', 'bold': True, 'align': 'center', 'valign': 'top', 'border': 1})
    low_fmt = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'bold': True, 'align': 'center', 'valign': 'top', 'border': 1})

    # ---------------------------------------------------------
    # Sheet 1: Action Plan Matrix
    # ---------------------------------------------------------
    ws1 = workbook.add_worksheet('Action Plan Matrix')
    ws1.write('A1', 'MATRIKS TEMUAN AUDIT & ACTION PLAN — PT SURYAMICROSYSTEM', title_fmt)
    ws1.write('A2', 'AuditLens AI Core — Automated Financial Audit Deliverable', sub_fmt)

    headers1 = [
        'No', 'Area / Akun', 'Detail Temuan (Condition)', 'Level Risiko',
        'Rekomendasi Auditor', 'Tanggapan Manajemen', 'PIC', 'Target Waktu', 'Status'
    ]
    for col, h in enumerate(headers1):
        ws1.write(3, col, h, header_fmt)

    for idx, row in enumerate(findings_data, 4):
        risk = str(row.get('risk_level', 'LOW')).upper()
        r_fmt = high_fmt if risk == 'HIGH' else (med_fmt if risk == 'MEDIUM' else low_fmt)

        ws1.write(idx, 0, idx - 3, center_fmt)
        ws1.write(idx, 1, row.get('area', ''), cell_fmt)
        ws1.write(idx, 2, row.get('condition', ''), cell_fmt)
        ws1.write(idx, 3, risk, r_fmt)
        ws1.write(idx, 4, row.get('recommendation', ''), cell_fmt)
        ws1.write(idx, 5, row.get('management_response', '-'), cell_fmt)
        ws1.write(idx, 6, row.get('pic', '-'), center_fmt)
        ws1.write(idx, 7, row.get('target_date', '-'), center_fmt)
        ws1.write(idx, 8, row.get('status', 'OPEN'), center_fmt)

    ws1.set_column('A:A', 5)
    ws1.set_column('B:B', 20)
    ws1.set_column('C:C', 34)
    ws1.set_column('D:D', 14)
    ws1.set_column('E:E', 34)
    ws1.set_column('F:F', 30)
    ws1.set_column('G:I', 15)

    # Tabel Ringkasan & Donut Chart Native
    max_row = max(5, len(findings_data) + 4)
    ws1.write('K4', 'Level Risiko', header_fmt)
    ws1.write('L4', 'Jumlah', header_fmt)
    ws1.write('K5', 'HIGH', high_fmt)
    ws1.write_formula('L5', f'=COUNTIF(D5:D{max_row}, "HIGH")', num_fmt)
    ws1.write('K6', 'MEDIUM', med_fmt)
    ws1.write_formula('L6', f'=COUNTIF(D5:D{max_row}, "MEDIUM")', num_fmt)
    ws1.write('K7', 'LOW', low_fmt)
    ws1.write_formula('L7', f'=COUNTIF(D5:D{max_row}, "LOW")', num_fmt)

    chart = workbook.add_chart({'type': 'doughnut'})
    chart.add_series({
        'name': 'Distribusi Risiko Temuan',
        'categories': "='Action Plan Matrix'!$K$5:$K$7",
        'values': "='Action Plan Matrix'!$L$5:$L$7",
        'points': [
            {'fill': {'color': '#FFC7CE'}},
            {'fill': {'color': '#FFEB9C'}},
            {'fill': {'color': '#C6EFCE'}}
        ]
    })
    chart.set_title({'name': 'Distribusi Risiko Audit'})
    ws1.insert_chart('K9', chart)

    # ---------------------------------------------------------
    # Sheet 2: 3-Way Matching Mismatches
    # ---------------------------------------------------------
    ws2 = workbook.add_worksheet('3-Way Matching Mismatches')
    ws2.write('A1', 'RINCIAN SELISIH 3-WAY MATCHING (PO vs RR vs INVOICE) — PT SURYAMICROSYSTEM', title_fmt)

    headers2 = [
        'PO Number', 'Item Code', 'Qty PO', 'Qty Received (RR)',
        'Qty Billed (Inv)', 'Harga PO (Rp)', 'Harga Inv (Rp)', 'Varians (Rp)', 'Status Match'
    ]
    for col, h in enumerate(headers2):
        ws2.write(3, col, h, header_fmt)

    if mismatch_df is not None and not mismatch_df.empty:
        for idx, (_, row) in enumerate(mismatch_df.iterrows()):
            r_idx = idx + 4
            status_val = str(row.get('match_status', 'UNMATCHED'))
            status_fmt = low_fmt if status_val == 'MATCHED' else high_fmt

            ws2.write(r_idx, 0, str(row.get('po_number', '')), center_fmt)
            ws2.write(r_idx, 1, str(row.get('item_code', '')), center_fmt)
            ws2.write(r_idx, 2, float(row.get('qty', 0)), num_fmt)
            ws2.write(r_idx, 3, float(row.get('qty_received', 0)), num_fmt)
            ws2.write(r_idx, 4, float(row.get('qty_billed', 0)), num_fmt)
            ws2.write(r_idx, 5, float(row.get('po_price', 0)), num_fmt)
            ws2.write(r_idx, 6, float(row.get('inv_price', 0)), num_fmt)
            ws2.write(r_idx, 7, float(row.get('variance_amount', 0)), num_fmt)
            ws2.write(r_idx, 8, status_val, status_fmt)

    ws2.set_column('A:B', 16)
    ws2.set_column('C:E', 16)
    ws2.set_column('F:H', 18)
    ws2.set_column('I:I', 22)

    workbook.close()
    output.seek(0)
    return output.getvalue()
