import pandas as pd
import numpy as np


def generate_audit_sample_files():
    print("⏳ Menghasilkan data sampel audit dummy (150+ baris & berkas individu) untuk PT Suryamicrosystem...")
    np.random.seed(42)

    # ---------------------------------------------------------
    # A. GENERATE 150+ ROWS MULTI-SHEET (sample_audit_150_rows.xlsx)
    # ---------------------------------------------------------
    n_rows = 150
    items = ['ELEC-COMP-08', 'OFFICE-SUP-10', 'PACK-BOX-01', 'RAW-MAT-01', 'RAW-MAT-02', 'SPAREPART-05']
    prices_map = {
        'ELEC-COMP-08': 500000,
        'OFFICE-SUP-10': 50000,
        'PACK-BOX-01': 12000,
        'RAW-MAT-01': 150000,
        'RAW-MAT-02': 200000,
        'SPAREPART-05': 750000
    }
    vendors = [
        'CV Sentosa Perkasa', 'PT Nusantara Kemasan', 'PT Supplier Utama',
        'CV Rekanan Abadi', 'PT Teknik Mandiri', 'Toko Alat Tulis Jaya'
    ]
    proc_users = ['Procurement_UserA', 'Procurement_UserB', 'Procurement_UserC']
    whs_users = ['Whs_Staff1', 'Whs_Staff2', 'Whs_Staff3']

    po_rows = []
    rr_rows = []
    inv_rows = []

    for i in range(1, n_rows + 1):
        po_num = f"PO-2026-{i:03d}"
        item = np.random.choice(items)
        qty = int(np.random.choice([10, 20, 50, 100, 150, 200, 500]))
        price = prices_map[item]
        vendor = np.random.choice(vendors)
        c_by = np.random.choice(proc_users)

        po_rows.append({
            'po_number': po_num,
            'item_code': item,
            'qty': qty,
            'unit_price': price,
            'vendor_name': vendor,
            'created_by': c_by
        })

        # Simulasi anomaly pada sebagian baris RR & Invoice
        day = (i % 28) + 1
        r_date = f"2026-10-{day:02d}"
        r_by = np.random.choice(whs_users)

        # 11 PO sengaja belum ada RR (Missing RR -> 139 baris RR)
        if i % 13 != 0:
            if i % 9 == 0:
                qty_rec = max(0, qty - 10)  # Qty Mismatch
            else:
                qty_rec = qty
            rr_rows.append({
                'po_number': po_num,
                'item_code': item,
                'qty_received': qty_rec,
                'receive_date': r_date,
                'received_by': r_by
            })

        # Invoice: sebagian mengalami Price Mismatch
        if i % 11 == 0:
            inv_price = int(price * 1.15)  # Markup harga 15%
        else:
            inv_price = price

        inv_rows.append({
            'invoice_number': f"INV-SUP-{100 + i}",
            'po_number': po_num,
            'item_code': item,
            'qty_billed': qty,
            'unit_price': inv_price,
            'total_amount': qty * inv_price
        })

    df_po_150 = pd.DataFrame(po_rows)
    df_rr_150 = pd.DataFrame(rr_rows)
    df_inv_150 = pd.DataFrame(inv_rows)

    # GL Data 150 baris
    accounts = ['5001-HPP', '6002-MISC', '6001-ADM', '1101-KAS', '1103-PIUTANG', '2101-UTANG']
    fin_staff = ['Fin_StaffA', 'Fin_StaffB', 'Fin_StaffC']
    fin_spv = ['Fin_SpvX', 'Fin_SpvY']
    gl_rows = []
    for i in range(1, n_rows + 1):
        day = (i % 28) + 1
        created = np.random.choice(fin_staff)
        # Buat anomali jam malam, nominal bulat, atau konflik SoD pada indeks tertentu
        if i % 15 == 0:
            p_time = f"{np.random.choice([21, 22, 23, 1, 2, 3]):02d}:{np.random.randint(0, 59):02d}:00"
            debit_val = int(np.random.choice([10000000, 20000000, 50000000]))
            approved = created if i % 30 == 0 else np.random.choice(fin_spv)
        elif i % 19 == 0:
            p_time = f"{np.random.randint(9, 17):02d}:{np.random.randint(0, 59):02d}:00"
            debit_val = int(np.random.randint(150, 950) * 100000)
            approved = created  # Violasi SoD
        else:
            p_time = f"{np.random.randint(8, 17):02d}:{np.random.randint(0, 59):02d}:00"
            debit_val = int(np.random.randint(105, 895) * 100000 + 25000)
            approved = np.random.choice(fin_spv)

        gl_rows.append({
            'journal_id': f"J-{100 + i}",
            'posting_date': f"2026-10-{day:02d}",
            'posting_time': p_time,
            'account_code': np.random.choice(accounts),
            'debit': debit_val,
            'credit': 0,
            'created_by': created,
            'approved_by': approved
        })
    df_gl_150 = pd.DataFrame(gl_rows)

    # AR Aging Data 120 baris
    customers = ['PT Client Alfa', 'PT Client Beta', 'CV Client Gamma', 'PT Client Delta', 'PT Client Eka', 'PT Mitra Surya']
    due_dates_pool = ['2026-11-01', '2026-10-18', '2026-09-20', '2026-08-12', '2026-06-15', '2026-05-01']
    ar_rows = []
    for i in range(1, 121):
        ar_rows.append({
            'invoice_number': f"INV-AR-{i:03d}",
            'customer_name': np.random.choice(customers),
            'due_date': np.random.choice(due_dates_pool),
            'amount': int(np.random.choice([15000000, 25000000, 34000000, 45000000, 85000000, 156000000]))
        })
    df_ar_120 = pd.DataFrame(ar_rows)

    with pd.ExcelWriter('sample_audit_150_rows.xlsx', engine='openpyxl') as writer:
        df_po_150.to_excel(writer, sheet_name='PO_Data', index=False)
        df_rr_150.to_excel(writer, sheet_name='RR_Data', index=False)
        df_inv_150.to_excel(writer, sheet_name='Invoice_Data', index=False)
        df_gl_150.to_excel(writer, sheet_name='GL_Data', index=False)
        df_ar_120.to_excel(writer, sheet_name='AR_Aging_Data', index=False)

    # ---------------------------------------------------------
    # B. INDIVIDUAL SAMPLE FILES (UNTUK UPLOAD PER MODUL)
    # ---------------------------------------------------------
    df_po = pd.DataFrame([
        {'po_number': 'PO-2026-001', 'item_code': 'RAW-MAT-01', 'qty': 100, 'unit_price_x': 150000, 'vendor_name': 'PT Supplier Utama', 'created_by': 'Procurement_UserA'},
        {'po_number': 'PO-2026-002', 'item_code': 'RAW-MAT-02', 'qty': 50,  'unit_price_x': 200000, 'vendor_name': 'CV Rekanan Abadi', 'created_by': 'Procurement_UserA'},
        {'po_number': 'PO-2026-003', 'item_code': 'PACK-BOX-01', 'qty': 500, 'unit_price_x': 12000,  'vendor_name': 'PT Kemasan Nusantara', 'created_by': 'Procurement_UserB'},
        {'po_number': 'PO-2026-004', 'item_code': 'SPAREPART-05', 'qty': 20, 'unit_price_x': 750000, 'vendor_name': 'PT Teknik Mandiri', 'created_by': 'Procurement_UserB'},
        {'po_number': 'PO-2026-005', 'item_code': 'OFFICE-SUP-10', 'qty': 10, 'unit_price_x': 500000, 'vendor_name': 'Toko Alat Tulis Jaya', 'created_by': 'Procurement_UserA'},
    ])

    df_rr = pd.DataFrame([
        {'po_number': 'PO-2026-001', 'item_code': 'RAW-MAT-01', 'qty_received': 100, 'receive_date': '2026-10-05', 'received_by': 'Whs_Staff1'},
        {'po_number': 'PO-2026-002', 'item_code': 'RAW-MAT-02', 'qty_received': 40,  'receive_date': '2026-10-06', 'received_by': 'Whs_Staff2'},
        {'po_number': 'PO-2026-003', 'item_code': 'PACK-BOX-01', 'qty_received': 500, 'receive_date': '2026-10-08', 'received_by': 'Whs_Staff1'},
        {'po_number': 'PO-2026-004', 'item_code': 'SPAREPART-05', 'qty_received': 20, 'receive_date': '2026-10-10', 'received_by': 'Whs_Staff3'},
        {'po_number': 'PO-2026-005', 'item_code': 'OFFICE-SUP-10', 'qty_received': 10, 'receive_date': '2026-10-12', 'received_by': 'Whs_Staff2'},
    ])

    df_inv = pd.DataFrame([
        {'invoice_number': 'INV-SUP-881', 'po_number': 'PO-2026-001', 'item_code': 'RAW-MAT-01', 'qty_billed': 100, 'unit_price_y': 150000, 'total_amount': 15000000},
        {'invoice_number': 'INV-RA-902',  'po_number': 'PO-2026-002', 'item_code': 'RAW-MAT-02', 'qty_billed': 50,  'unit_price_y': 200000, 'total_amount': 10000000},
        {'invoice_number': 'INV-KN-104',  'po_number': 'PO-2026-003', 'item_code': 'PACK-BOX-01', 'qty_billed': 500, 'unit_price_y': 15000,  'total_amount': 7500000},
        {'invoice_number': 'INV-TM-305',  'po_number': 'PO-2026-004', 'item_code': 'SPAREPART-05', 'qty_billed': 20, 'unit_price_y': 750000, 'total_amount': 15000000},
        {'invoice_number': 'INV-TJ-009',  'po_number': 'PO-2026-005', 'item_code': 'OFFICE-SUP-10', 'qty_billed': 10, 'unit_price_y': 500000, 'total_amount': 5000000},
    ])

    df_gl = pd.DataFrame([
        {'journal_id': 'J-101', 'posting_date': '2026-10-01', 'posting_time': '10:15:00', 'account_code': '5001-HPP', 'debit': 15000000, 'credit': 0, 'created_by': 'Fin_StaffA', 'approved_by': 'Fin_SpvX'},
        {'journal_id': 'J-102', 'posting_date': '2026-10-02', 'posting_time': '23:45:00', 'account_code': '6002-MISC', 'debit': 50000000, 'credit': 0, 'created_by': 'Fin_StaffB', 'approved_by': 'Fin_SpvY'},
        {'journal_id': 'J-103', 'posting_date': '2026-10-05', 'posting_time': '14:30:00', 'account_code': '5001-HPP', 'debit': 7500000,  'credit': 0, 'created_by': 'Fin_StaffA', 'approved_by': 'Fin_SpvX'},
        {'journal_id': 'J-104', 'posting_date': '2026-10-10', 'posting_time': '11:20:00', 'account_code': '6001-ADM',  'debit': 25000000, 'credit': 0, 'created_by': 'Fin_StaffC', 'approved_by': 'Fin_StaffC'},
        {'journal_id': 'J-105', 'posting_date': '2026-10-15', 'posting_time': '02:10:00', 'account_code': '1101-KAS',  'debit': 10000000, 'credit': 0, 'created_by': 'Fin_StaffB', 'approved_by': 'Fin_SpvY'},
    ])

    df_ar = pd.DataFrame([
        {'invoice_number': 'INV-AR-001', 'customer_name': 'PT Client Alfa',  'due_date': '2026-11-01', 'amount': 85000000},
        {'invoice_number': 'INV-AR-002', 'customer_name': 'PT Client Beta',  'due_date': '2026-10-15', 'amount': 45000000},
        {'invoice_number': 'INV-AR-003', 'customer_name': 'CV Client Gamma', 'due_date': '2026-09-20', 'amount': 30000000},
        {'invoice_number': 'INV-AR-004', 'customer_name': 'PT Client Delta', 'due_date': '2026-08-10', 'amount': 25000000},
        {'invoice_number': 'INV-AR-005', 'customer_name': 'PT Client Eka',   'due_date': '2026-05-01', 'amount': 15000000},
    ])

    df_po.to_excel('sample_po.xlsx', index=False)
    df_rr.to_excel('sample_rr.xlsx', index=False)
    df_inv.to_excel('sample_invoice.xlsx', index=False)
    df_gl.to_excel('sample_gl.xlsx', index=False)
    df_ar.to_excel('sample_ar.xlsx', index=False)

    print("✅ Seluruh Berkas Sampel Excel Berhasil Dibuat:")
    print("  - sample_audit_150_rows.xlsx (Multi-sheet 150+ baris)")
    print("  - sample_po.xlsx")
    print("  - sample_rr.xlsx")
    print("  - sample_invoice.xlsx")
    print("  - sample_gl.xlsx")
    print("  - sample_ar.xlsx")


if __name__ == "__main__":
    generate_audit_sample_files()
