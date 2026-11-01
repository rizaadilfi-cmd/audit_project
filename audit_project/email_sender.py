import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def send_audit_report_email(
    to_email: str, 
    subject: str, 
    body_text: str, 
    excel_bytes: bytes, 
    filename: str = "Laporan_Hasil_Audit_2026.xlsx",
    smtp_server: str = "smtp.gmail.com", 
    smtp_port: int = 587, 
    sender_email: str = "", 
    sender_password: str = ""
) -> bool:
    """
    Mengirimkan laporan Excel hasil audit via SMTP SSL/TLS.
    """
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body_text, 'html'))

    # Lampirkan Excel Bytes
    attachment = MIMEApplication(excel_bytes, Name=filename)
    attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
    msg.attach(attachment)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Gagal mengirim email: {e}")
        return False