"""Карточка WB (сводка) и позиция в поиске — поверх core.fetch_json."""

import random
import time
import urllib.parse

from .core import DEFAULT_DEST, fetch_json


def catalog_url(nm):
    """Публичная страница товара на wildberries.ru."""
    return f"https://www.wildberries.ru/catalog/{nm}/detail.aspx"


def _rub_from_kopecks(kop):
    if kop is None:
        return None
    try:
        return round(float(kop) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def _rating(product):
    for key in ("nmReviewRating", "reviewRating", "rating"):
        v = product.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def fetch_product_for_nm(session, nm, dest=DEFAULT_DEST):
    url = (
        f"https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest={dest}&nm={nm}"
    )
    data, err = fetch_json(session, url, timeout=15, attempts=3)
    if data is None or err is not None:
        return None, err
    products = data.get("products") or []
    if not products:
        return None, None
    return products[0], None


def snapshot_row(nm, product):
    name = (product.get("name") or "").strip()
    sizes = product.get("sizes") or []
    price_block = (sizes[0].get("price") or {}) if sizes else {}
    basic_k = price_block.get("basic")
    product_k = price_block.get("product")
    price_rub = _rub_from_kopecks(product_k)
    basic_rub = _rub_from_kopecks(basic_k)
    discount_pct = None
    if basic_k and product_k:
        try:
            bk, pk = float(basic_k), float(product_k)
            if bk > pk:
                discount_pct = round((1 - pk / bk) * 100, 1)
        except (TypeError, ValueError):
            pass

    pics = product.get("pics")
    try:
        pics_i = int(pics) if pics is not None else 0
    except (TypeError, ValueError):
        pics_i = 0

    feedbacks = product.get("feedbacks")
    try:
        fb_i = int(feedbacks) if feedbacks is not None else 0
    except (TypeError, ValueError):
        fb_i = 0

    return {
        "Артикул": nm,
        "Название": name,
        "Ссылка": catalog_url(nm),
        "Бренд": product.get("brand") or "",
        "Продавец": product.get("supplier") or "",
        "Цена руб": price_rub,
        "Цена до скидки руб": basic_rub,
        "Скидка %": discount_pct,
        "Рейтинг": _rating(product),
        "Отзывов": fb_i,
        "Фото шт": pics_i,
    }


def empty_summary_row(nm):
    return snapshot_row(
        nm,
        {
            "name": "",
            "brand": "",
            "supplier": "",
            "feedbacks": 0,
            "sizes": [{"price": {}}],
            "pics": 0,
            "nmReviewRating": None,
            "reviewRating": None,
            "rating": None,
        },
    )


def load_snapshot_for_article(session, nm, dest=DEFAULT_DEST):
    product, err = fetch_product_for_nm(session, nm, dest=dest)
    if product is None:
        return None, err
    return snapshot_row(nm, product), None


def _products_from_search_payload(payload):
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        prods = data.get("products")
        if prods:
            return prods
    return payload.get("products") or []


def find_nm_rank(session, nm, query, dest, max_pages=5, pause_between_pages=(0.7, 1.4)):
    target = int(nm)
    encoded = urllib.parse.quote(query, safe="")
    global_idx = 0
    for page in range(1, max_pages + 1):
        url = (
            f"https://search.wb.ru/exactmatch/ru/common/v4/search"
            f"?appType=1&curr=rub&dest={dest}&query={encoded}"
            f"&resultset=catalog&limit=100&page={page}&sort=popular&spp=30"
        )
        data, err = fetch_json(session, url, timeout=20, attempts=3)
        if err == "bad_request":
            return None, "bad_request"
        if data is None:
            return None, err
        prods = _products_from_search_payload(data)
        if not prods:
            break
        for p in prods:
            global_idx += 1
            pid = p.get("id")
            if pid is None:
                continue
            try:
                if int(pid) == target:
                    return global_idx, None
            except (TypeError, ValueError):
                continue
        if len(prods) < 100:
            break
        time.sleep(random.uniform(*pause_between_pages))
    return None, None
