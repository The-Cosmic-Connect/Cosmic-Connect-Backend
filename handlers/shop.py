from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from models.product import (
    ProductCreate, ProductUpdate,
    create_product, get_product_by_id, get_product_by_slug,
    list_products, update_product, delete_product,
    get_coupons_table, serialize,
)
from datetime import datetime
import boto3, os, uuid

router = APIRouter(tags=['shop'])

# ── Products ──────────────────────────────────────────────────────────────────

@router.get('/products')
def get_products(
    published_only: bool  = Query(True),
    collection:     Optional[str] = Query(None),
    search:         Optional[str] = Query(None),
    featured_only:  bool  = Query(False),
):
    products = list_products(
        published_only=published_only,
        collection=collection,
        search=search,
        featured_only=featured_only,
    )
    return {'products': products, 'total': len(products)}

@router.get('/products/slug/{slug}')
def get_product_slug(slug: str):
    p = get_product_by_slug(slug)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@router.get('/products/{product_id}')
def get_product(product_id: str):
    p = get_product_by_id(product_id)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@router.post('/products', status_code=201)
def create(data: ProductCreate):
    return create_product(data)

@router.put('/products/{product_id}')
def update(product_id: str, data: ProductUpdate):
    p = update_product(product_id, data)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@router.delete('/products/{product_id}', status_code=204)
def delete(product_id: str):
    delete_product(product_id)

# ── Collections list ──────────────────────────────────────────────────────────

@router.get('/collections')
def get_collections():
    """Returns all unique collection names from products."""
    products = list_products(published_only=False)
    collections = set()
    for p in products:
        for c in p.get('collections', []):
            collections.add(c)
    return {'collections': sorted(list(collections))}

# ── Coupons ───────────────────────────────────────────────────────────────────

def coupon_table():
    return get_coupons_table()

class CouponCreate:
    pass

@router.get('/coupons')
def get_coupons():
    r = coupon_table().scan()
    return {'coupons': [serialize(c) for c in r.get('Items', [])]}

@router.post('/coupons', status_code=201)
def create_coupon(data: dict):
    now = datetime.utcnow().isoformat()
    item = {
        'id':         str(uuid.uuid4()),
        'code':       data.get('code', '').upper().strip(),
        'discountType':  data.get('discountType', 'percentage'),
        'discountValue': float(data.get('discountValue', 0)),
        'minOrderINR':   float(data.get('minOrderINR', 0)),
        'maxUsage':      data.get('maxUsage'),
        'usageCount':    0,
        'expiresAt':     data.get('expiresAt', ''),
        'active':        data.get('active', True),
        'createdAt':     now,
    }
    coupon_table().put_item(Item=item)
    return item

@router.post('/coupons/validate')
def validate_coupon(data: dict):
    code      = data.get('code', '').upper().strip()
    orderINR  = float(data.get('orderTotal', 0))

    r = coupon_table().scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('code').eq(code)
    )
    items = r.get('Items', [])
    if not items:
        raise HTTPException(404, 'Coupon not found')

    c = serialize(items[0])
    if not c.get('active'):
        raise HTTPException(400, 'Coupon is inactive')
    if c.get('expiresAt') and c['expiresAt'] < datetime.utcnow().isoformat():
        raise HTTPException(400, 'Coupon has expired')
    if c.get('maxUsage') and c.get('usageCount', 0) >= c['maxUsage']:
        raise HTTPException(400, 'Coupon usage limit reached')
    if orderINR < c.get('minOrderINR', 0):
        raise HTTPException(400, f"Minimum order ₹{c['minOrderINR']} required")

    if c['discountType'] == 'percentage':
        discount = round(orderINR * c['discountValue'] / 100, 2)
    else:
        discount = min(c['discountValue'], orderINR)

    return {
        'valid':         True,
        'code':          code,
        'discountType':  c['discountType'],
        'discountValue': c['discountValue'],
        'discountINR':   discount,
        'finalTotal':    round(orderINR - discount, 2),
    }

@router.put('/coupons/{code}')
def update_coupon(code: str, data: dict):
    r = coupon_table().scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('code').eq(code)
    )
    items = r.get('Items', [])
    if not items:
        raise HTTPException(404, 'Coupon not found')
    item_id = items[0]['id']
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return serialize(items[0])
    expr   = 'SET ' + ', '.join(f'#{k} = :{k}' for k in updates)
    names  = {f'#{k}': k for k in updates}
    values = {f':{k}': v for k, v in updates.items()}
    coupon_table().update_item(
        Key={'id': item_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    return {'ok': True}

@router.delete('/coupons/{code}', status_code=204)
def delete_coupon(code: str):
    r = coupon_table().scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('code').eq(code)
    )
    items = r.get('Items', [])
    if items:
        coupon_table().delete_item(Key={'id': items[0]['id']})
