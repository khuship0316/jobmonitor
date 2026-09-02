"""
Sends alerts via plain SMTP email, and optionally to a carrier SMS-gateway
address (e.g. 5551234567@vtext.com) for a text-message-style ping.
"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]

ALERT_EMAIL_TO = os.environ["ALERT_EMAIL_TO"]
SMS_GATEWAY_TO = os.environ.get("SMS_GATEWAY_TO")  # optional


def _send(to_addr: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_addr

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to_addr], msg.as_string())


def send_alert(new_postings: list):
    """new_postings: list of dicts {firm, title, url}"""
    if not new_postings:
        return

    lines = [
        f"{p['firm']}: {p['title']}\n{p['url']}\n(found via: {p.get('evidence', '')})\n"
        for p in new_postings
    ]
    body = "New Summer 2028 posting(s) found:\n\n" + "\n".join(lines)
    subject = f"[Job Monitor] {len(new_postings)} new Summer 2028 posting(s)"

    _send(ALERT_EMAIL_TO, subject, body)

    if SMS_GATEWAY_TO:
        # Keep the SMS body short - carrier gateways often truncate ~140-160 chars
        firms = ", ".join(sorted({p["firm"] for p in new_postings}))
        sms_body = f"{len(new_postings)} new Summer 2028 posting(s): {firms}. Check email for links."
        _send(SMS_GATEWAY_TO, "", sms_body)
