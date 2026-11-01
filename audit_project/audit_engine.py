import pandas as pd
import numpy as np
from PIL import Image

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx
except ImportError:
    docx = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


def extract_unstructured_file(uploaded_file) -> tuple[pd.DataFrame, str]:
    """
    Mengekstrak tabel dan teks dari berkas multimodal (Excel, CSV, PDF, DOCX, PNG/JPG).
    Mengembalikan tuple: (DataFrame hasil ekstraksi, Teks mentah hasil ekstraksi).
    """
    filename = uploaded_file.name.lower()
    text_content = ""
    tables_extracted = []

    if filename.endswith(('.xlsx', '.xls', '.csv')):
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        return df, ""

    elif filename.endswith('.pdf'):
        if pdfplumber:
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    text_content += (page.extract_text() or "") + "\n"
                    extracted_tbl = page.extract_tables()
                    for tbl in extracted_tbl:
                        if tbl and len(tbl) > 1:
                            tables_extracted.append(pd.DataFrame(tbl[1:], columns=tbl[0]))
        else:
            text_content = "PDF engine (pdfplumber) tidak terpasang."

    elif filename.endswith('.docx'):
        if docx:
            doc = docx.Document(uploaded_file)
            text_content = "\n".join([p.text for p in doc.paragraphs if p.text])
            for table in doc.tables:
                data = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                if len(data) > 1:
                    tables_extracted.append(pd.DataFrame(data[1:], columns=data[0]))
        else:
            text_content = "Word engine (python-docx) tidak terpasang."

    elif filename.endswith(('.png', '.jpg', '.jpeg')):
        if pytesseract:
            try:
                image = Image.open(uploaded_file)
                text_content = pytesseract.image_to_string(image)
            except Exception as e:
                text_content = f"Gagal memindai OCR gambar: {e}"
        else:
            text_content = "OCR Engine (pytesseract) belum terpasang. Teks gambar tidak dapat dipindai."

    if tables_extracted:
        return tables_extracted[0], text_content
    return pd.DataFrame(), text_content


def run_3way_matching(df_po: pd.DataFrame, df_rr: pd.DataFrame, df_inv: pd.DataFrame) -> pd.DataFrame:
    """
    Mengeksekusi pencocokan 3-Way Matching antara Purchase Order (PO),
    Receiving Report (RR), dan Vendor Invoice (INV).
    """
    if df_po.empty or df_rr.empty or df_inv.empty:
        return pd.DataFrame()

    po_copy = df_po.copy()
    rr_copy = df_rr.copy()
    inv_copy = df_inv.copy()

    # Normalisasi nama kolom harga agar konsisten sebelum merge
    if 'unit_price_x' not in po_copy.columns and 'unit_price' in po_copy.columns:
        po_copy = po_copy.rename(columns={'unit_price': 'unit_price_x'})
    if 'unit_price_y' not in inv_copy.columns and 'unit_price' in inv_copy.columns:
        inv_copy = inv_copy.rename(columns={'unit_price': 'unit_price_y'})

    merged = po_copy.merge(rr_copy, on=['po_number', 'item_code'], how='left')
    merged = merged.merge(inv_copy, on=['po_number', 'item_code'], how='left')

    merged['qty'] = pd.to_numeric(merged['qty'], errors='coerce').fillna(0)
    merged['qty_received'] = pd.to_numeric(merged.get('qty_received', 0), errors='coerce').fillna(0)
    merged['qty_billed'] = pd.to_numeric(merged.get('qty_billed', 0), errors='coerce').fillna(0)

    if 'unit_price_x' in merged.columns:
        merged['po_price'] = pd.to_numeric(merged['unit_price_x'], errors='coerce').fillna(0)
    else:
        merged['po_price'] = 0.0

    if 'unit_price_y' in merged.columns:
        merged['inv_price'] = pd.to_numeric(merged['unit_price_y'], errors='coerce').fillna(0)
    else:
        merged['inv_price'] = 0.0

    conditions = [
        (merged['qty'] == merged['qty_received']) & (merged['qty_received'] == merged['qty_billed']) & (merged['po_price'] == merged['inv_price']),
        (merged['qty'] != merged['qty_received']) | (merged['qty_received'] != merged['qty_billed']),
        (merged['po_price'] != merged['inv_price'])
    ]
    choices = ['MATCHED', 'QTY_MISMATCH', 'PRICE_MISMATCH']
    merged['match_status'] = np.select(conditions, choices, default='UNMATCHED_EXCEPTION')
    merged['variance_amount'] = np.abs((merged['qty'] * merged['po_price']) - (merged['qty_billed'] * merged['inv_price']))

    return merged


def scan_journal_anomalies(df_gl: pd.DataFrame) -> pd.DataFrame:
    """
    Memindai anomali jurnal buku besar (General Ledger):
    1. Off-Hours Posting (20:00 - 05:00)
    2. Nominal Bulat Besar (Round-Sum >= Rp 10.000.000)
    3. Konflik Pemisahan Tugas / Segregation of Duties (created_by == approved_by)
    """
    if df_gl.empty:
        return pd.DataFrame()

    df = df_gl.copy()
    df['posting_time_clean'] = pd.to_datetime(
        df['posting_time'].astype(str), format='%H:%M:%S', errors='coerce'
    ).dt.hour.fillna(12)

    df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)

    off_hours = (df['posting_time_clean'] >= 20) | (df['posting_time_clean'] <= 5)
    round_sum = (df['debit'] % 10000000 == 0) & (df['debit'] > 0)
    sod_violation = df['created_by'].astype(str).str.strip() == df['approved_by'].astype(str).str.strip()

    df['is_anomaly'] = off_hours | round_sum | sod_violation
    df['anomaly_type'] = (
        np.where(off_hours, 'Off-Hours Posting; ', '') +
        np.where(round_sum, 'Round-Sum Amount; ', '') +
        np.where(sod_violation, 'SoD Conflict; ', '')
    )
    df['anomaly_type'] = df['anomaly_type'].str.rstrip('; ')

    return df[df['is_anomaly']].drop(columns=['posting_time_clean'], errors='ignore')
