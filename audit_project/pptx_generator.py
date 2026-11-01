import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor


def generate_audit_pptx(
    project_name: str = "Audit Keuangan 2026",
    client_name: str = "PT Suryamicrosystem",
    opinion: str = "WDP (Wajar Dengan Pengecualian)",
    findings: list = None
) -> bytes:
    """
    Menghasilkan berkas PowerPoint (.pptx) untuk presentasi Komite Audit & Direksi.
    """
    if findings is None:
        findings = []

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    DARK_BLUE = RGBColor(26, 54, 93)
    SLATE_GRAY = RGBColor(74, 85, 104)
    RED_RISK = RGBColor(197, 48, 48)

    # ---------------------------------------------------------
    # Slide 1: Cover Slide
    # ---------------------------------------------------------
    slide1 = prs.slides.add_slide(blank_layout)
    txBox = slide1.shapes.add_textbox(Inches(1.2), Inches(1.8), Inches(10.8), Inches(4.0))
    tf = txBox.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "LAPORAN HASIL AUDIT FINANCIAL REVIEW"
    p.font.bold = True
    p.font.size = Pt(32)
    p.font.color.rgb = DARK_BLUE

    p2 = tf.add_paragraph()
    p2.text = f"Klien: {client_name}"
    p2.font.bold = True
    p2.font.size = Pt(22)
    p2.font.color.rgb = SLATE_GRAY

    p3 = tf.add_paragraph()
    p3.text = f"Penugasan: {project_name} | AuditLens AI Core"
    p3.font.size = Pt(16)
    p3.font.color.rgb = SLATE_GRAY

    # ---------------------------------------------------------
    # Slide 2: Executive Summary & Opini Auditor
    # ---------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_layout)
    header_box = slide2.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(1.0))
    hp = header_box.text_frame.paragraphs[0]
    hp.text = f"EXECUTIVE SUMMARY & OPINI AUDITOR — {client_name.upper()}"
    hp.font.bold = True
    hp.font.size = Pt(24)
    hp.font.color.rgb = DARK_BLUE

    body_box = slide2.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.0))
    btf = body_box.text_frame
    btf.word_wrap = True

    high_cnt = sum(1 for f in findings if str(f.get('risk_level', '')).upper() == 'HIGH')
    med_cnt = sum(1 for f in findings if str(f.get('risk_level', '')).upper() == 'MEDIUM')
    low_cnt = sum(1 for f in findings if str(f.get('risk_level', '')).upper() == 'LOW')

    bp1 = btf.paragraphs[0]
    bp1.text = f"Opini Audit Usulan: {opinion}"
    bp1.font.bold = True
    bp1.font.size = Pt(20)
    bp1.font.color.rgb = RED_RISK if "WDP" in opinion or "TW" in opinion else DARK_BLUE

    bp2 = btf.add_paragraph()
    bp2.text = (
        f"\nTotal Temuan Teridentifikasi: {len(findings)} Temuan\n"
        f"• High Risk (Prioritas Utama): {high_cnt} Temuan\n"
        f"• Medium Risk (Perlu Perbaikan SOP): {med_cnt} Temuan\n"
        f"• Low Risk (Observasi Operasional): {low_cnt} Temuan"
    )
    bp2.font.size = Pt(16)
    bp2.font.color.rgb = SLATE_GRAY

    # ---------------------------------------------------------
    # Slide 3: Ikhtisar Temuan Utama (5C Framework)
    # ---------------------------------------------------------
    if findings:
        slide3 = prs.slides.add_slide(blank_layout)
        h3_box = slide3.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9))
        h3p = h3_box.text_frame.paragraphs[0]
        h3p.text = "IKHTISAR TEMUAN KUNCI & REKOMENDASI (5C FRAMEWORK)"
        h3p.font.bold = True
        h3p.font.size = Pt(22)
        h3p.font.color.rgb = DARK_BLUE

        f_box = slide3.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(5.5))
        ftf = f_box.text_frame
        ftf.word_wrap = True

        for idx, item in enumerate(findings[:5], 1):
            fp = ftf.paragraphs[0] if idx == 1 else ftf.add_paragraph()
            area = item.get('area', '-')
            risk = item.get('risk_level', 'LOW')
            cond = item.get('condition', '-')
            rec = item.get('recommendation', '-')
            fp.text = f"{idx}. [{risk}] {area}: {cond}\n    ➔ Rekomendasi: {rec}\n"
            fp.font.size = Pt(13)
            fp.font.color.rgb = SLATE_GRAY

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.getvalue()
