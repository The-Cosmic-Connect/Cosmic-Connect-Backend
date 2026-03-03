import boto3
import os
import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from models.product import get_table as get_dynamo, decimal_to_float, float_to_decimal

class CouponCreate(BaseModel):
    code: str
    discountPct: float          # e.g. 10 = 10% off
    minOrderINR: float = 0
    minOrderUSD: float = 0
    maxUsages: int = 100
    expiresAt: Optional[str] = None   # ISO date string
    active: bool = True

class CouponUpdate(BaseModel):
    discountPct: Optional[float] = None
    active: Optional[bool] = None
    maxUsages: Optional[int] = None
    expiresAt: Optional[str] = None

def get_coupon_table():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'),
    )
    return dynamodb.Table(os.getenv('COUPONS_TABLE', 'cosmic-coupons'))

def validate_coupon(code: str) -> dict:
    """Returns dict with discountPct if valid, raises ValueError if not"""
    table = get_coupon_table()
    resp = table.get_item(Key={'code': code.upper().strip()})
    item = resp.get('Item')

    if not item:
        raise ValueError('Coupon code not found')

    item = decimal_to_float(item)

    if not item.get('active', True):
        raise ValueError('This coupon is no longer active')

    if item.get('expiresAt'):
        try:
            expiry = datetime.fromisoformat(item['expiresAt'])
            if datetime.utcnow() > expiry:
                raise ValueError('This coupon has expired')
        except ValueError as e:
            if 'expired' in str(e):
                raise

    usages = item.get('usages', 0)
    max_usages = item.get('maxUsages', 100)
    if usages >= max_usages:
        raise ValueError('This coupon has reached its usage limit')

    return {
        'code': item['code'],
        'discountPct': item['discountPct'],
        'minOrderINR': item.get('minOrderINR', 0),
        'minOrderUSD': item.get('minOrderUSD', 0),
    }

def increment_coupon_usage(code: str):
    table = get_coupon_table()
    table.update_item(
        Key={'code': code.upper()},
        UpdateExpression='ADD usages :inc',
        ExpressionAttributeValues={':inc': 1},
    )

def create_coupon(data: CouponCreate) -> dict:
    table = get_coupon_table()
    item = float_to_decimal({
        'code': data.code.upper().strip(),
        'discountPct': data.discountPct,
        'minOrderINR': data.minOrderINR,
        'minOrderUSD': data.minOrderUSD,
        'maxUsages': data.maxUsages,
        'expiresAt': data.expiresAt,
        'active': data.active,
        'usages': 0,
        'createdAt': datetime.utcnow().isoformat(),
    })
    table.put_item(Item=item)
    return decimal_to_float(item)

def list_coupons() -> list:
    table = get_coupon_table()
    resp = table.scan()
    return [decimal_to_float(i) for i in resp.get('Items', [])]

def delete_coupon(code: str) -> bool:
    table = get_coupon_table()
    table.delete_item(Key={'code': code.upper()})
    return True
