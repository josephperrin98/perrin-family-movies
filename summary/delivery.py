"""
Delivery: an email to Joseph with a one-tap "send to WhatsApp" link.

WhatsApp has no free API for posting to a family group, so a person reviews
the message and forwards it: wa.me opens WhatsApp with the text pre-filled.
"""

import html
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

WA_URL = "https://wa.me/?text="
MAX_MESSAGE_CHARS = 1500  # checked on a phone during the first live send
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465


def whatsapp_link(message: str) -> str:
    return WA_URL + quote(message, safe="")


def build_email(sender: str, to: str, subject: str, message: str) -> EmailMessage:
    link = whatsapp_link(message)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(f"{message}\n\n---\nEnvoyer sur WhatsApp : {link}\n")
    msg.add_alternative(
        f"""<p style="white-space: pre-wrap; font-family: sans-serif;">{html.escape(message)}</p>
<p><a href="{html.escape(link)}" style="display: inline-block; padding: 12px 20px;
background: #25D366; color: white; border-radius: 8px; text-decoration: none;
font-family: sans-serif; font-weight: bold;">Envoyer sur WhatsApp</a></p>""",
        subtype="html",
    )
    return msg


def send_email(msg: EmailMessage, user: str, password: str) -> None:
    # Google displays app passwords in groups of four; the spaces aren't part of it
    password = password.replace(" ", "")
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        # login() greets the server for us; auth() doesn't. Without the greeting
        # Gmail answers "503 EHLO first", which smtplib mistakes for success.
        server.ehlo()
        # One mechanism only. server.login() falls back to AUTH LOGIN after a
        # rejected AUTH PLAIN, Gmail then hangs up, and the real "535 wrong
        # credentials" error is replaced by "connection unexpectedly closed".
        server.auth("PLAIN", lambda challenge=None: f"\0{user}\0{password}")
        server.send_message(msg)
