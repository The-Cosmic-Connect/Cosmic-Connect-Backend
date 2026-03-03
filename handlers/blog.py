from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from models.blog import (
    BlogPostCreate, BlogPostUpdate,
    list_posts, get_post_by_slug, get_post, create_post,
    update_post, delete_post, increment_views, get_related_posts,
    seed_initial_posts, CATEGORIES,
)

router = APIRouter(prefix='/blog', tags=['blog'])

@router.get('')
def api_list_posts(
    category: Optional[str] = Query(None),
    search:   Optional[str] = Query(None),
    limit:    int            = Query(50, le=100),
):
    posts = list_posts(published_only=True, category=category, limit=limit)
    if search:
        q = search.lower()
        posts = [
            p for p in posts
            if q in p['title'].lower()
            or q in p['excerpt'].lower()
            or any(q in t.lower() for t in p.get('tags', []))
        ]
    # Strip full content from listing — return only summary fields
    summary_fields = ['id', 'slug', 'title', 'category', 'excerpt',
                      'coverImage', 'readTime', 'tags', 'author',
                      'createdAt', 'viewCount']
    return {
        'posts':      [{k: p[k] for k in summary_fields if k in p} for p in posts],
        'total':      len(posts),
        'categories': ['All'] + CATEGORIES,
    }

@router.get('/slug/{slug}')
def api_get_post_by_slug(slug: str):
    post = get_post_by_slug(slug)
    if not post:
        raise HTTPException(404, 'Post not found')
    # Increment view count asynchronously (don't fail if this errors)
    try:
        increment_views(post['id'])
    except Exception:
        pass
    return post

@router.get('/related/{post_id}')
def api_get_related(post_id: str, category: str = Query(...)):
    return {'posts': get_related_posts(post_id, category)}

@router.get('/{post_id}')
def api_get_post(post_id: str):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, 'Post not found')
    return post

@router.post('', status_code=201)
def api_create_post(data: BlogPostCreate):
    return create_post(data)

@router.put('/{post_id}')
def api_update_post(post_id: str, data: BlogPostUpdate):
    post = update_post(post_id, data)
    if not post:
        raise HTTPException(404, 'Post not found')
    return post

@router.delete('/{post_id}')
def api_delete_post(post_id: str):
    delete_post(post_id)
    return {'deleted': True}

@router.post('/seed', status_code=201)
def api_seed_posts():
    """Seed the 6 initial blog posts. Call once from admin or setup script."""
    seed_initial_posts()
    return {'status': 'seeded'}

@router.get('/meta/categories')
def api_categories():
    return {'categories': ['All'] + CATEGORIES}