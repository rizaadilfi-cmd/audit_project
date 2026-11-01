import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_management_letter_pdf(output_target, project_name, client_name, opinion, findings_list):
    doc = SimpleDocTemplate(
        output_target,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1A365D'), alignment=1)
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor('#4A5568'), alignment=1)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=13, leading=16, textColor=colors.HexColor('#1A365D'), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9.5, leading=13, textColor=colors.HexColor('#2D3748'))
    bold_body = ParagraphStyle('BoldBody', parent=body_style, fontName='Helvetica-Bold')

    story = []

    # 1. Header Dokumen Resmi
    story.append(Paragraph("SURAT MANAJEMEN (MANAGEMENT LETTER)", title_style))
    story.append(Paragraph("Laporan Hasil Audit Internal Keuangan — Period: 2026", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1A365D'), spaceAfter=15))

    # 2. Metadata Penugasan & Opini Auditor
    meta_data = [
        [Paragraph("<b>Nama Klien:</b>", body_style), Paragraph(str(client_name), body_style),
         Paragraph("<b>Tanggal Terbit:</b>", body_style), Paragraph("01 November 2026", body_style)],
        [Paragraph("<b>Penugasan:</b>", body_style), Paragraph(str(project_name), body_style),
         Paragraph("<b>Opini Auditor:</b>", body_style), Paragraph(f"<b>{opinion}</b>", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[90, 180, 90, 180])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F7FAFC')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    # 3. Eksekutif Ringkasan Opini
    story.append(Paragraph("1. PERNYATAAN OPINI AUDITOR", heading_style))
    opinion_text = (
        f"Berdasarkan pengujian audit yang telah kami laksanakan, kami menyimpulkan bahwa Laporan Keuangan "
        f"<b>{client_name}</b> diberikan opini <b>{opinion}</b>. Evaluasi pengendalian internal menunjukkan "
        f"beberapa kelemahan signifikan yang memerlukan tindakan perbaikan mendesak dari pihak manajemen."
    )
    story.append(Paragraph(opinion_text, body_style))
    story.append(Spacer(1, 15))

    # 4. Detail Temuan Framework 5C
    story.append(Paragraph("2. RINCIAN TEMUAN AUDIT & REKOMENDASI (5C FRAMEWORK)", heading_style))

    for idx, f in enumerate(findings_list, 1):
        area = f.get('area', '-')
        risk = f.get('risk_level', 'LOW')
        story.append(Paragraph(f"Temuan #{idx}: {area} (Risiko: {risk})", bold_body))

        table_5c_data = [
            [Paragraph("<b>Condition (Kondisi):</b>", body_style), Paragraph(str(f.get('condition', '-')), body_style)],
            [Paragraph("<b>Criteria (Kriteria):</b>", body_style), Paragraph(str(f.get('criteria', '-')), body_style)],
            [Paragraph("<b>Cause (Sebab):</b>", body_style), Paragraph(str(f.get('cause', '-')), body_style)],
            [Paragraph("<b>Effect (Dampak):</b>", body_style), Paragraph(str(f.get('effect', '-')), body_style)],
            [Paragraph("<b>Recommendation:</b>", body_style), Paragraph(str(f.get('recommendation', '-')), body_style)]
        ]

        t_5c = Table(table_5c_data, colWidths=[130, 410])
        t_5c.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EDF2F7')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_5c)
        story.append(Spacer(1, 10))

    doc.build(story)


def generate_management_letter_pdf_bytes(
    project_name: str = "Audit Keuangan TA 2026",
    client_name: str = "PT Suryamicrosystem",
    opinion: str = "WDP (Wajar Dengan Pengecualian)",
    findings_list: list = None
) -> bytes:
    """
    Menghasilkan Management Letter PDF dalam bentuk bytes di memori untuk diunduh langsung via Streamlit.
    """
    if findings_list is None:
        findings_list = []
    buf = io.BytesIO()
    generate_management_letter_pdf(buf, project_name, client_name, opinion, findings_list)
    buf.seek(0)
    return buf.getvalue()


if __name__ == "__main__":
    sample_findings = [{
        'area': 'Kas & Bank / Petty Cash',
        'risk_level': 'HIGH',
        'condition': 'Pengeluaran petty cash sebesar Rp 65.000.000 dilakukan tanpa otorisasi Direktur Keuangan.',
        'criteria': 'SOP-FIN-004 Batas maksimal petty cash adalah Rp 5.000.000.',
        'cause': 'Pemegang kas menghindari proses transfer e-banking untuk percepatan operasional.',
        'effect': 'Potensi penyalahgunaan dana kas kecil dan tidak tercatatnya kewajiban pajak.',
        'recommendation': 'Terapkan hard-limit pada sistem kasir dan wajibkan dual-approval.'
    }]

    generate_management_letter_pdf(
        "Management_Letter_Final.pdf",
        "Audit Keuangan TA 2026",
        "PT Suryamicrosystem",
        "WDP (Wajar Dengan Pengecualian)",
        sample_findings
    )
