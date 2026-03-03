import base64
import hashlib
import httpx
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from models.coupon import increment_coupon_usage
from utils.email import send_order_confirmation

router = APIRouter(prefix='/orders', tags=['orders'])

# ── DynamoDB ──────────────────────────────────────────────────────────────────
def get_order_table():
    import boto3
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'),
    )
    return dynamodb.Table(os.getenv('ORDERS_TABLE', 'cosmic-orders'))

def save_order(order: dict):
    table = get_order_table()
    def to_dec(obj):
        if isinstance(obj, float): return Decimal(str(obj))
        if isinstance(obj, dict): return {k: to_dec(v) for k, v in obj.items()}
        if isinstance(obj, list): return [to_dec(i) for i in obj]
        return obj
    table.put_item(Item=to_dec(order))

def update_order_status(order_id: str, status: str, extra: dict = {}):
    table = get_order_table()
    updates = {'#s': status, **{k: v for k, v in extra.items()}}
    table.update_item(
        Key={'id': order_id},
        UpdateExpression='SET #status = :s' + (
            ''.join(f', #{k} = :{k}' for k in extra) if extra else ''
        ),
        ExpressionAttributeNames={'#status': 'status', **{f'#{k}': k for k in extra}},
        ExpressionAttributeValues={
            ':s': status,
            **{f':{k}': v for k, v in extra.items()},
        },
    )

# ── Schemas ───────────────────────────────────────────────────────────────────
class OrderItem(BaseModel):
    id: str
    name: str
    priceINR: float
    priceUSD: float
    quantity: int
    image: str = ''
    category: str = ''

class PhonePeInitiateRequest(BaseModel):
    amountINR: float
    items: List[OrderItem]
    coupon: Optional[str] = None
    customerEmail: str
    customerName: str
    customerPhone: str = ''

class PayPalCreateRequest(BaseModel):
    paypalOrderId: str
    amountUSD: float
    items: List[OrderItem]
    coupon: Optional[str] = None
    customerEmail: str

# ── PhonePe V2 helpers ────────────────────────────────────────────────────────
PHONEPE_BASE_UAT  = 'https://api-preprod.phonepe.com/apis/pg-sandbox'
PHONEPE_BASE_PROD = 'https://api.phonepe.com/apis/pg'

def phonepe_base() -> str:
    return PHONEPE_BASE_PROD if os.getenv('PHONEPE_ENV') == 'production' else PHONEPE_BASE_UAT

async def get_phonepe_token() -> str:
    """PhonePe V2 — fetch OAuth access token using Client ID + Client Secret"""
    client_id     = os.getenv('PHONEPE_CLIENT_ID')
    client_secret = os.getenv('PHONEPE_CLIENT_SECRET')
    client_version = os.getenv('PHONEPE_CLIENT_VERSION', '1')

    if not client_id or not client_secret:
        raise HTTPException(500, 'PhonePe credentials not configured')

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f'{phonepe_base()}/v1/oauth/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'client_id':      client_id,
                'client_secret':  client_secret,
                'client_version': client_version,
                'grant_type':     'client_credentials',
            },
        )
        data = r.json()
        if r.status_code != 200 or 'access_token' not in data:
            raise HTTPException(500, f'PhonePe token error: {data}')
        return data['access_token']

# ── PhonePe routes ─────────────────────────────────────────────────────────────

@router.post('/phonepe/initiate')
async def phonepe_initiate(req: PhonePeInitiateRequest):
    """Step 1 — Create a PhonePe V2 payment order and return the redirect URL"""
    merchant_order_id = f'COSMIC_{uuid.uuid4().hex[:12].upper()}'
    amount_paise = int(req.amountINR * 100)          # PhonePe expects paise
    site_url = os.getenv('SITE_URL', 'http://localhost:3000')

    token = await get_phonepe_token()

    payload = {
        'merchantOrderId': merchant_order_id,
        'amount':          amount_paise,
        'expireAfter':     1800,                      # 30 minutes
        'metaInfo': {
            'udf1': req.customerEmail,
            'udf2': req.customerName,
            'udf3': req.customerPhone,
        },
        'paymentFlow': {
            'type': 'PG_CHECKOUT',
            'message': 'The Cosmic Connect — Healing Crystals',
            'merchantUrls': {
                'redirectUrl': f'{site_url}/shop/order-success?orderId={merchant_order_id}&gateway=phonepe',
            },
        },
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f'{phonepe_base()}/checkout/v2/pay',
            headers={
                'Authorization':  f'O-Bearer {token}',
                'Content-Type':   'application/json',
            },
            json=payload,
        )
        data = r.json()

    if r.status_code not in (200, 201):
        raise HTTPException(500, f'PhonePe initiation failed: {data}')

    redirect_url = (
        data.get('redirectUrl')
        or data.get('data', {}).get('redirectUrl')
        or data.get('instrumentResponse', {}).get('redirectInfo', {}).get('url')
    )
    if not redirect_url:
        raise HTTPException(500, f'No redirect URL in PhonePe response: {data}')

    # Persist pending order to DynamoDB
    save_order({
        'id':              merchant_order_id,
        'gateway':         'phonepe',
        'status':          'pending',
        'items':           [i.dict() for i in req.items],
        'totalINR':        req.amountINR,
        'currency':        'INR',
        'coupon':          req.coupon,
        'customerEmail':   req.customerEmail,
        'customerName':    req.customerName,
        'customerPhone':   req.customerPhone,
        'createdAt':       datetime.utcnow().isoformat(),
    })

    return {'redirectUrl': redirect_url, 'merchantOrderId': merchant_order_id}


@router.get('/phonepe/status/{merchant_order_id}')
async def phonepe_status(merchant_order_id: str):
    """
    Check payment status from PhonePe — called by success page to confirm payment.
    PhonePe V2: GET /checkout/v2/order/{merchantOrderId}/status
    """
    token = await get_phonepe_token()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f'{phonepe_base()}/checkout/v2/order/{merchant_order_id}/status',
            headers={'Authorization': f'O-Bearer {token}'},
        )
        data = r.json()

    if r.status_code != 200:
        raise HTTPException(500, f'PhonePe status check failed: {data}')

    state = (
        data.get('state')
        or data.get('data', {}).get('state')
        or 'UNKNOWN'
    )

    if state == 'COMPLETED':
        # Update order in DynamoDB
        table = get_order_table()
        order = table.get_item(Key={'id': merchant_order_id}).get('Item', {})

        if order.get('status') != 'paid':
            update_order_status(merchant_order_id, 'paid', {
                'paidAt': datetime.utcnow().isoformat()
            })

            # Increment coupon usage if one was applied
            if order.get('coupon'):
                try:
                    increment_coupon_usage(order['coupon'])
                except Exception:
                    pass

            # Send confirmation email
            try:
                items = order.get('items', [])
                send_order_confirmation(
                    customer_email=order.get('customerEmail', ''),
                    customer_name=order.get('customerName', 'Customer'),
                    order_id=merchant_order_id,
                    items=items,
                    total=float(order.get('totalINR', 0)),
                    currency='INR',
                    gateway='PhonePe',
                )
            except Exception as e:
                print(f'Email error: {e}')

    return {'state': state, 'merchantOrderId': merchant_order_id}


@router.post('/phonepe/callback')
async def phonepe_callback(request: Request):
    """
    PhonePe server-to-server callback — optional but recommended.
    PhonePe POSTs payment result to this URL as a backup to the redirect.
    Configure this URL in your PhonePe merchant dashboard.
    """
    try:
        body = await request.json()
        merchant_order_id = (
            body.get('merchantOrderId')
            or body.get('data', {}).get('merchantOrderId')
        )
        state = (
            body.get('state')
            or body.get('data', {}).get('state')
        )
        if merchant_order_id and state == 'COMPLETED':
            table = get_order_table()
            order = table.get_item(Key={'id': merchant_order_id}).get('Item', {})
            if order and order.get('status') != 'paid':
                update_order_status(merchant_order_id, 'paid', {
                    'paidAt': datetime.utcnow().isoformat()
                })
    except Exception as e:
        print(f'PhonePe callback error: {e}')

    # PhonePe expects HTTP 200 to acknowledge receipt
    return {'status': 'acknowledged'}


# ── PayPal routes ─────────────────────────────────────────────────────────────

@router.post('/paypal/create')
async def paypal_create(req: PayPalCreateRequest):
    save_order({
        'id':            req.paypalOrderId,
        'gateway':       'paypal',
        'status':        'pending',
        'items':         [i.dict() for i in req.items],
        'totalUSD':      req.amountUSD,
        'currency':      'USD',
        'customerEmail': req.customerEmail,
        'coupon':        req.coupon,
        'createdAt':     datetime.utcnow().isoformat(),
    })
    return {'status': 'created'}


@router.get('/paypal/capture')
async def paypal_capture(token: str, PayerID: str):
    pp_client_id = os.getenv('PAYPAL_CLIENT_ID')
    pp_secret    = os.getenv('PAYPAL_SECRET')
    base         = os.getenv('PAYPAL_BASE_URL', 'https://api-m.sandbox.paypal.com')

    if not pp_client_id or not pp_secret:
        raise HTTPException(500, 'PayPal not configured')

    async with httpx.AsyncClient() as client:
        auth_r = await client.post(
            f'{base}/v1/oauth2/token',
            headers={
                'Authorization': 'Basic ' + base64.b64encode(
                    f'{pp_client_id}:{pp_secret}'.encode()
                ).decode()
            },
            data={'grant_type': 'client_credentials'},
        )
        access_token = auth_r.json()['access_token']

        cap_r = await client.post(
            f'{base}/v2/checkout/orders/{token}/capture',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
        )
        cap_data = cap_r.json()

    if cap_data.get('status') != 'COMPLETED':
        raise HTTPException(400, 'PayPal capture failed')

    table = get_order_table()
    table.update_item(
        Key={'id': token},
        UpdateExpression='SET #s = :s, payerId = :p, capturedAt = :t',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':s': 'paid', ':p': PayerID,
            ':t': datetime.utcnow().isoformat(),
        },
    )

    try:
        order = table.get_item(Key={'id': token}).get('Item', {})
        send_order_confirmation(
            customer_email=order.get('customerEmail', ''),
            customer_name=order.get('customer', {}).get('name', 'Customer'),
            order_id=token,
            items=order.get('items', []),
            total=float(order.get('totalUSD', 0)),
            currency='USD',
            gateway='PayPal',
        )
    except Exception as e:
        print(f'Email error: {e}')

    site = os.getenv('SITE_URL', 'http://localhost:3000')
    return RedirectResponse(
        f'{site}/shop/order-success?orderId={token}&gateway=paypal'
    )
