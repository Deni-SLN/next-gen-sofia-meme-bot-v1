from fastapi import APIRouter, Query
from app.services import news

router = APIRouter()


@router.get("")
@router.get("/")
def get_news_feed(
    category: str = Query(
        "all",
        description="Kategori berita: all, crypto, saham, emas, ekonomi, teknologi",
    ),
    q: str | None = Query(None, description="Kata kunci pencarian opsional"),
    limit: int = Query(24, ge=1, le=50, description="Jumlah artikel maksimal"),
    refresh: bool = Query(False, description="Paksa muat ulang dari sumber berita live"),
):
    return news.fetch_indonesian_news(
        category=category,
        search_query=q,
        limit=limit,
        force_refresh=refresh,
    )
