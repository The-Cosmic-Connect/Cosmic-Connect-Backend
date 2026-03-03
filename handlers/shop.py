from fastapi import APIRouter, HTTPException
from models.product import ProductCreate, ProductUpdate, list_products, get_product, get_product_by_slug, create_product, update_product, delete_product
from models.coupon import CouponCreate, validate_coupon, create_coupon, list_coupons, delete_coupon
from pydantic import BaseModel
from typing import Optional

# ── Products ──────────────────────────────────────────────────────────────────
products_router = APIRouter(prefix='/products', tags=['products'])

@products_router.get('')
def api_list_products(category: Optional[str] = None):
    return {'products': list_products(category)}

@products_router.get('/{product_id}')
def api_get_product(product_id: str):
    p = get_product(product_id)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@products_router.get('/slug/{slug}')
def api_get_product_by_slug(slug: str):
    p = get_product_by_slug(slug)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@products_router.post('', status_code=201)
def api_create_product(data: ProductCreate):
    return create_product(data)

@products_router.put('/{product_id}')
def api_update_product(product_id: str, data: ProductUpdate):
    p = update_product(product_id, data)
    if not p:
        raise HTTPException(404, 'Product not found')
    return p

@products_router.delete('/{product_id}')
def api_delete_product(product_id: str):
    delete_product(product_id)
    return {'deleted': True}

# ── Coupons ───────────────────────────────────────────────────────────────────
coupons_router = APIRouter(prefix='/coupons', tags=['coupons'])

class ValidateCouponRequest(BaseModel):
    code: str

@coupons_router.post('/validate')
def api_validate_coupon(req: ValidateCouponRequest):
    try:
        result = validate_coupon(req.code)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))

@coupons_router.get('')
def api_list_coupons():
    return {'coupons': list_coupons()}

@coupons_router.post('', status_code=201)
def api_create_coupon(data: CouponCreate):
    return create_coupon(data)

@coupons_router.delete('/{code}')
def api_delete_coupon(code: str):
    delete_coupon(code)
    return {'deleted': True}
