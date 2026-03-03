import boto3
import os
import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

# ── Pydantic models ────────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    name: str
    slug: str
    category: str
    categorySlug: str
    priceINR: float
    priceUSD: float
    originalPriceINR: Optional[float] = None
    originalPriceUSD: Optional[float] = None
    image: str = ''
    badge: Optional[str] = None
    description: str = ''
    benefit: Optional[str] = None
    inStock: bool = True
    weight: Optional[str] = None
    material: Optional[str] = None
    stockCount: int = 100

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    priceINR: Optional[float] = None
    priceUSD: Optional[float] = None
    originalPriceINR: Optional[float] = None
    originalPriceUSD: Optional[float] = None
    image: Optional[str] = None
    badge: Optional[str] = None
    description: Optional[str] = None
    benefit: Optional[str] = None
    inStock: Optional[bool] = None
    stockCount: Optional[int] = None

class Product(ProductBase):
    id: str

# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def get_table():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'),  # http://localhost:8080 locally
    )
    return dynamodb.Table(os.getenv('PRODUCTS_TABLE', 'cosmic-products'))

def float_to_decimal(obj):
    """DynamoDB requires Decimal, not float"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [float_to_decimal(i) for i in obj]
    return obj

def decimal_to_float(obj):
    """Convert Decimal back to float for JSON response"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj

# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_products(category_slug: Optional[str] = None) -> list:
    table = get_table()
    if category_slug:
        resp = table.query(
            IndexName='categorySlug-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('categorySlug').eq(category_slug)
        )
    else:
        resp = table.scan()
    return [decimal_to_float(item) for item in resp.get('Items', [])]

def get_product(product_id: str) -> Optional[dict]:
    table = get_table()
    resp = table.get_item(Key={'id': product_id})
    item = resp.get('Item')
    return decimal_to_float(item) if item else None

def get_product_by_slug(slug: str) -> Optional[dict]:
    table = get_table()
    resp = table.query(
        IndexName='slug-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('slug').eq(slug)
    )
    items = resp.get('Items', [])
    return decimal_to_float(items[0]) if items else None

def create_product(data: ProductCreate) -> dict:
    table = get_table()
    item = float_to_decimal({
        'id': str(uuid.uuid4()),
        **data.dict(),
    })
    table.put_item(Item=item)
    return decimal_to_float(item)

def update_product(product_id: str, data: ProductUpdate) -> Optional[dict]:
    table = get_table()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        return get_product(product_id)

    expr = 'SET ' + ', '.join(f'#{k} = :{k}' for k in updates)
    names = {f'#{k}': k for k in updates}
    values = float_to_decimal({f':{k}': v for k, v in updates.items()})

    resp = table.update_item(
        Key={'id': product_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues='ALL_NEW',
    )
    return decimal_to_float(resp.get('Attributes', {}))

def delete_product(product_id: str) -> bool:
    table = get_table()
    table.delete_item(Key={'id': product_id})
    return True
