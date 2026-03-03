"""
Extends the contact handler to STORE submissions in DynamoDB
so the admin portal can retrieve them.

Add to backend/main.py:
    from handlers.inbox import router as inbox_router
    app.include_router(inbox_router)

Also update contact.py to call store_submission() after sending emails.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import boto3, os, uuid

router = APIRouter(prefix='/inbox', tags=['inbox'])

INBOX_TABLE = lambda: os.getenv('INBOX_TABLE', 'cosmic-inbox')

def get_table():
    db = boto3.resource('dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'))
    return db.Table(INBOX_TABLE())

def store(type_: str, data: dict):
    """Call this from contact.py after sending SES emails."""
    try:
        get_table().put_item(Item={
            'id':        str(uuid.uuid4()),
            'type':      type_,
            'createdAt': datetime.utcnow().isoformat(),
            **{k: v for k, v in data.items() if v is not None},
        })
    except Exception as e:
        print(f'[inbox] store failed: {e}')  # don't crash the contact endpoint

def get_by_type(type_: str) -> List[dict]:
    try:
        resp  = get_table().scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('type').eq(type_)
        )
        items = resp.get('Items', [])
        items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        return items
    except Exception as e:
        print(f'[inbox] fetch failed: {e}')
        return []

# ── Routes ─────────────────────────────────────────────────────────────────────
@router.get('/bookings')
def get_bookings():
    return {'items': get_by_type('booking')}

@router.get('/course-inquiries')
def get_course_inquiries():
    return {'items': get_by_type('course_inquiry')}

@router.get('/messages')
def get_messages():
    return {'items': get_by_type('general')}
