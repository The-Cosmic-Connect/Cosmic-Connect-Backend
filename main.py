from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from handlers.orders import router as orders_router
from handlers.shop import router as shop_router
from handlers.contact import router as contact_router

from handlers.blog import router as blog_router
from handlers.inbox import router as inbox_router


app = FastAPI(title='The Cosmic Connect API', version='1.0.0')
app.include_router(contact_router)
app.include_router(inbox_router)
app.include_router(blog_router)


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'http://localhost:3001',
        'https://www.thecosmicconnect.com',
        'https://admin.thecosmicconnect.com',
        "https://thecosmicconnect.in",
        "https://staging.thecosmicconnect.in",
        "https://dev.thecosmicconnect.in",
        "https://arkasuryacrystals.com",
        "https://www.arkasuryacrystals.com",
        "https://admin.arkasuryacrystals.com",
        "https://staging.arkasuryacrystals.com",
        "https://dev.arkasuryacrystals.com",
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(orders_router)
app.include_router(shop_router)

# ── Health ────────────────────────────────────────────────────────────────────
@app.get('/')
def root():
    return {'status': 'ok', 'service': 'The Cosmic Connect API'}

@app.get("/health")
def health():
    return {"status": "ok", "service": "cosmic-backend"}
