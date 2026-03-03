from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import boto3, os

router = APIRouter(prefix='/contact', tags=['contact'])

# ── SES ────────────────────────────────────────────────────────────────────────
def ses():   return boto3.client('ses', region_name=os.getenv('AWS_REGION', 'ap-south-1'))
SENDER = lambda: os.getenv('SES_SENDER_EMAIL', 'orders@thecosmicconnect.com')
OWNER  = lambda: os.getenv('OWNER_EMAIL',      'info@thecosmicconnect.com')
def ts(): return datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')

def email_shell(title: str, rows: list) -> str:
    rows_html = ''.join(f'<tr><td style="padding:7px 0;color:#C9A84C88;font-size:12px;'
        f'letter-spacing:2px;text-transform:uppercase;width:36%;vertical-align:top">{l}</td>'
        f'<td style="padding:7px 0;color:#F5EDD6;font-size:14px">{v}</td></tr>' for l, v in rows)
    return f"""<div style="font-family:Arial,sans-serif;background:#0A0708;padding:32px">
      <div style="max-width:540px;margin:0 auto;background:#1A0A2E;border:1px solid #C9A84C33;padding:28px">
        <p style="color:#C9A84C;font-size:11px;letter-spacing:4px;text-transform:uppercase;margin:0 0 14px">✦ The Cosmic Connect</p>
        <h2 style="color:#F5EDD6;font-size:20px;margin:0 0 20px">{title}</h2>
        <table style="width:100%;border-collapse:collapse">{rows_html}</table>
      </div></div>"""

def confirm_shell(name: str, subject: str, body: str) -> str:
    return f"""<div style="font-family:Arial,sans-serif;background:#0A0708;padding:32px">
      <div style="max-width:540px;margin:0 auto;background:#1A0A2E;border:1px solid #C9A84C33;padding:28px">
        <p style="color:#C9A84C;font-size:11px;letter-spacing:4px;text-transform:uppercase;margin:0 0 8px">✦ The Cosmic Connect</p>
        <h2 style="color:#F5EDD6;font-size:20px;margin:0 0 16px">{subject}</h2>
        <p style="color:#F5EDD6aa;font-size:15px;font-family:Georgia,serif;font-style:italic;margin:0 0 14px">Dear {name},</p>
        <p style="color:#F5EDD6aa;font-size:14px;line-height:1.7;margin:0 0 20px">{body}</p>
        <p style="color:#F5EDD655;font-size:11px">© The Cosmic Connect · GG1/5A PVR Road, Vikaspuri, New Delhi 110018</p>
      </div></div>"""

def send(to: str, subject: str, html: str):
    ses().send_email(Source=SENDER(), Destination={'ToAddresses': [to]},
        Message={'Subject': {'Data': subject}, 'Body': {'Html': {'Data': html}}})

# Lazy import to avoid circular dependency
def _store(type_: str, data: dict):
    try:
        from handlers.inbox import store
        store(type_, data)
    except Exception as e:
        print(f'[contact] store failed: {e}')

# ── Models ─────────────────────────────────────────────────────────────────────
class GeneralContact(BaseModel):
    name: str; email: str; phone: str; subject: str; message: str

class BookingInquiry(BaseModel):
    name: str; email: str; phone: str; service: str; mode: str
    preferredDate: Optional[str] = ''; preferredTime: Optional[str] = ''
    message: Optional[str] = ''

class CourseInquiry(BaseModel):
    name: str; email: str; phone: str; course: str; mode: str
    message: Optional[str] = ''

# ── Routes ─────────────────────────────────────────────────────────────────────
@router.post('/general')
async def general_contact(req: GeneralContact):
    send(OWNER(), f'Message: {req.subject} — {req.name}',
        email_shell(f'New Message: {req.subject}',
            [('Name', req.name), ('Email', req.email), ('Phone', req.phone),
             ('Subject', req.subject), ('Message', req.message), ('Received', ts())]))
    send(req.email, 'We received your message | The Cosmic Connect',
        confirm_shell(req.name, 'Message Received',
            f"Thank you for reaching out. Dr. Bhatt's team will reply within 24–48 hours. "
            f'WhatsApp: <a href="https://wa.me/919599474758" style="color:#C9A84C">+91 95994 74758</a>'))
    _store('general', {'name': req.name, 'email': req.email, 'phone': req.phone,
                       'subject': req.subject, 'message': req.message})
    return {'status': 'sent'}

@router.post('/booking')
async def booking_inquiry(req: BookingInquiry):
    send(OWNER(), f'Booking: {req.service} ({req.mode}) — {req.name}',
        email_shell(f'Booking Request: {req.service}',
            [('Name', req.name), ('Email', req.email), ('Phone', req.phone),
             ('Service', req.service), ('Mode', req.mode.title()),
             ('Preferred Date', req.preferredDate or '—'),
             ('Preferred Time', req.preferredTime or '—'),
             ('Message', req.message or '—'), ('Received', ts())]))
    send(req.email, f'Booking Request Received — {req.service} | The Cosmic Connect',
        confirm_shell(req.name, 'Booking Request Received',
            f"Thank you for your interest in <strong style='color:#C9A84C'>{req.service}</strong> "
            f"({req.mode.title()}). We'll confirm your appointment within 24 hours."))
    _store('booking', {'name': req.name, 'email': req.email, 'phone': req.phone,
                       'service': req.service, 'mode': req.mode,
                       'preferredDate': req.preferredDate, 'preferredTime': req.preferredTime,
                       'message': req.message})
    return {'status': 'sent'}

@router.post('/course-inquiry')
async def course_inquiry(req: CourseInquiry):
    send(OWNER(), f'Course: {req.course} ({req.mode.title()}) — {req.name}',
        email_shell(f'Course Inquiry: {req.course}',
            [('Name', req.name), ('Email', req.email), ('Phone', req.phone),
             ('Course', req.course), ('Mode', req.mode.title()),
             ('Message', req.message or '—'), ('Received', ts())]))
    send(req.email, f'Course Inquiry — {req.course} | The Cosmic Connect',
        confirm_shell(req.name, 'Inquiry Received',
            f"Thank you for your interest in <strong style='color:#C9A84C'>{req.course}</strong>. "
            f"We'll contact you within 24 hours with batch dates and enrollment details."))
    _store('course_inquiry', {'name': req.name, 'email': req.email, 'phone': req.phone,
                              'course': req.course, 'mode': req.mode, 'message': req.message})
    return {'status': 'sent'}
