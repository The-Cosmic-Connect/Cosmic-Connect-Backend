from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import boto3, os, uuid

# ── Sub-models ────────────────────────────────────────────────────────────────

class ProductSpec(BaseModel):
    title: str
    value: str

class ProductOption(BaseModel):
    name: str
    type: str   # "dropdown" | "color" | "radio"
    choices: List[str] = []

# ── Main product model ────────────────────────────────────────────────────────

class Product(BaseModel):
    id:               Optional[str]  = None
    name:             str
    slug:             str
    sku:              Optional[str]  = ""
    description:      str            = ""
    collections:      List[str]      = []
    priceINR:         float          = 0
    priceUSD:         float          = 0
    originalPriceINR: float          = 0
    originalPriceUSD: float          = 0
    discountValue:    float          = 0
    ribbon:           Optional[str]  = ""
    weight:           float          = 0
    cost:             float          = 0
    brand:            str            = "The Cosmic Connect"
    images:           List[str]      = []
    specs:            List[ProductSpec] = []
    options:          List[ProductOption] = []
    tags:             List[str]      = []
    inStock:          bool           = True
    stock:            int            = 0
    published:        bool           = True
    featured:         bool           = False
    createdAt:        Optional[str]  = None
    updatedAt:        Optional[str]  = None

class ProductCreate(BaseModel):
    name:             str
    slug:             str
    sku:              Optional[str]  = ""
    description:      str            = ""
    collections:      List[str]      = []
    priceINR:         float          = 0
    priceUSD:         float          = 0
    originalPriceINR: float          = 0
    originalPriceUSD: float          = 0
    discountValue:    float          = 0
    ribbon:           Optional[str]  = ""
    weight:           float          = 0
    cost:             float          = 0
    brand:            str            = "The Cosmic Connect"
    images:           List[str]      = []
    specs:            List[ProductSpec] = []
    options:          List[ProductOption] = []
    tags:             List[str]      = []
    inStock:          bool           = True
    stock:            int            = 0
    published:        bool           = True
    featured:         bool           = False

class ProductUpdate(BaseModel):
    name:             Optional[str]  = None
    slug:             Optional[str]  = None
    sku:              Optional[str]  = None
    description:      Optional[str]  = None
    collections:      Optional[List[str]] = None
    priceINR:         Optional[float] = None
    priceUSD:         Optional[float] = None
    originalPriceINR: Optional[float] = None
    originalPriceUSD: Optional[float] = None
    discountValue:    Optional[float] = None
    ribbon:           Optional[str]  = None
    weight:           Optional[float] = None
    cost:             Optional[float] = None
    brand:            Optional[str]  = None
    images:           Optional[List[str]] = None
    specs:            Optional[List[ProductSpec]] = None
    options:          Optional[List[ProductOption]] = None
    tags:             Optional[List[str]] = None
    inStock:          Optional[bool] = None
    stock:            Optional[int]  = None
    published:        Optional[bool] = None
    featured:         Optional[bool] = None

# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def get_table():
    db = boto3.resource('dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'))
    return db.Table(os.getenv('PRODUCTS_TABLE', 'products-dev'))

def get_coupons_table():
    db = boto3.resource('dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'))
    return db.Table(os.getenv('COUPONS_TABLE', 'coupons-dev'))

def serialize(p: dict) -> dict:
    from decimal import Decimal
    out = {}
    for k, v in p.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, list):
            out[k] = [serialize(i) if isinstance(i, dict) else
                      (float(i) if isinstance(i, Decimal) else i) for i in v]
        elif isinstance(v, dict):
            out[k] = serialize(v)
        else:
            out[k] = v
    return out

def _scan_all(table, **kwargs) -> List[dict]:
    """Paginate through ALL DynamoDB scan results."""
    items = []
    resp = table.scan(**kwargs)
    items.extend(resp.get('Items', []))
    while 'LastEvaluatedKey' in resp:
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        resp = table.scan(**kwargs)
        items.extend(resp.get('Items', []))
    return items

def create_product(data: ProductCreate) -> dict:
    now = datetime.utcnow().isoformat()
    item = {
        'id':        str(uuid.uuid4()),
        'createdAt': now,
        'updatedAt': now,
        **data.model_dump(),
    }
    item['specs']   = [s.model_dump() for s in data.specs]
    item['options'] = [o.model_dump() for o in data.options]
    get_table().put_item(Item=item)
    return item

def get_product_by_id(product_id: str) -> Optional[dict]:
    r = get_table().get_item(Key={'id': product_id})
    item = r.get('Item')
    return serialize(item) if item else None

def get_product_by_slug(slug: str) -> Optional[dict]:
    """Use slug-index GSI for efficient lookup."""
    try:
        r = get_table().query(
            IndexName='slug-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('slug').eq(slug)
        )
        items = r.get('Items', [])
    except Exception:
        # Fallback to scan if GSI not ready
        items = _scan_all(get_table(),
            FilterExpression=boto3.dynamodb.conditions.Attr('slug').eq(slug))
    return serialize(items[0]) if items else None

def list_products(
    published_only: bool = True,
    collection: Optional[str] = None,
    search: Optional[str] = None,
    featured_only: bool = False,
) -> List[dict]:
    """Scan ALL products with full DynamoDB pagination."""
    filters = []
    if published_only:
        filters.append(boto3.dynamodb.conditions.Attr('published').eq(True))
    if featured_only:
        filters.append(boto3.dynamodb.conditions.Attr('featured').eq(True))
    if collection:
        filters.append(boto3.dynamodb.conditions.Attr('collections').contains(collection))

    fe = filters[0] if filters else None
    for f in filters[1:]:
        fe = fe & f

    scan_kwargs = {}
    if fe:
        scan_kwargs['FilterExpression'] = fe

    raw_items = _scan_all(get_table(), **scan_kwargs)
    items = [serialize(i) for i in raw_items]

    if search:
        s = search.lower()
        items = [i for i in items if
                 s in i.get('name', '').lower() or
                 s in i.get('description', '').lower() or
                 any(s in t.lower() for t in i.get('tags', []))]

    # Sort: featured first, then by createdAt desc
    items.sort(key=lambda x: (not x.get('featured', False), x.get('createdAt', '')), reverse=False)
    items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    items.sort(key=lambda x: not x.get('featured', False))

    return items

def update_product(product_id: str, data: ProductUpdate) -> Optional[dict]:
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return get_product_by_id(product_id)
    updates['updatedAt'] = datetime.utcnow().isoformat()
    if 'specs' in updates:
        updates['specs'] = [s.model_dump() if hasattr(s, 'model_dump') else s for s in updates['specs']]
    if 'options' in updates:
        updates['options'] = [o.model_dump() if hasattr(o, 'model_dump') else o for o in updates['options']]

    expr   = 'SET ' + ', '.join(f'#{k} = :{k}' for k in updates)
    names  = {f'#{k}': k for k in updates}
    values = {f':{k}': v for k, v in updates.items()}

    get_table().update_item(
        Key={'id': product_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    return get_product_by_id(product_id)

def delete_product(product_id: str):
    get_table().delete_item(Key={'id': product_id})