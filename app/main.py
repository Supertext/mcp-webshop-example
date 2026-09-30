from __future__ import annotations

import datetime
import fnmatch
import json
import pathlib
import secrets
import urllib.parse
import uuid

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.analytics import connect, init_db, locale_funnel, revenue_by_locale, top_paths
from app.analytics import record as record_event
from app.catalog import CATEGORIES, PRODUCTS, in_category
from app.i18n import (
    CATALOGS,
    DEFAULT_LOCALE,
    TARGET_LOCALES,
    render_notice,
    render_string,
    state_counts,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEGAL_SLUGS = ("terms", "returns", "warranty", "privacy", "shipping")

app = FastAPI(title="Firn")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "app" / "templates")

templates.env.filters["product_key"] = lambda sku, suffix: f"product.{sku}.{suffix}"


class LocaleMiddleware(BaseHTTPMiddleware):
    """Strip a known locale prefix from the path so routes stay locale-free."""

    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        locale = DEFAULT_LOCALE
        for candidate in TARGET_LOCALES:
            if path == f"/{candidate}" or path.startswith(f"/{candidate}/"):
                locale = candidate
                path = path[len(candidate) + 1 :] or "/"
                request.scope["path"] = path
                break
        request.state.locale = locale
        return await call_next(request)


app.add_middleware(LocaleMiddleware)


def locale_prefix(request: Request) -> str:
    return "" if request.state.locale == DEFAULT_LOCALE else f"/{request.state.locale}"


def page(request: Request, template: str, **context) -> HTMLResponse:
    CATALOGS.refresh()
    locale = request.state.locale
    trust = request.query_params.get("trust") == "1"

    def t(key: str):
        return render_string(CATALOGS, key, locale, trust)

    def notice(key: str):
        return render_notice(CATALOGS, key, locale)

    prefix = locale_prefix(request)
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={
            "t": t,
            "notice": notice,
            "locale": locale,
            "locales": (DEFAULT_LOCALE, *TARGET_LOCALES),
            "trust": trust,
            "prefix": prefix,
            "path": request.scope["path"],
            "catalog_version": CATALOGS.version,
            "categories": CATEGORIES,
            "products": PRODUCTS,
            **context,
        },
    )


@app.get("/_health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # The first product leads as the spotlight; the rest fill the grid below it,
    # so nothing appears twice.
    spotlight, *featured = (
        PRODUCTS[s] for s in ("arv-tx3", "arv-ab30", "clb-vf1", "clb-k2")
    )
    return page(request, "home.html", spotlight=spotlight, featured=featured)


@app.get("/c/{category}", response_class=HTMLResponse)
def category(request: Request, category: str):
    if category not in CATEGORIES:
        raise HTTPException(status_code=404)
    return page(request, "category.html", category=category, items=in_category(category))


@app.get("/p/{sku}", response_class=HTMLResponse)
def product(request: Request, sku: str):
    if sku not in PRODUCTS:
        raise HTTPException(status_code=404)
    return page(request, "product.html", product=PRODUCTS[sku])


@app.get("/guide/avalanche-basics", response_class=HTMLResponse)
def guide(request: Request):
    # The guide is about avalanche safety, so the sidebar shows that kit.
    return page(request, "article.html", related=in_category("avalanche-safety")[:3])


@app.get("/legal/{slug}", response_class=HTMLResponse)
def legal(request: Request, slug: str):
    if slug not in LEGAL_SLUGS:
        raise HTTPException(status_code=404)
    return page(request, "legal.html", slug=slug, legal_slugs=LEGAL_SLUGS)


CART_COOKIE = "firn_cart"
ORDERS: dict[str, dict] = {}
SHIPPING_CHF = {"standard": 0, "express": 18}


def read_cart(request: Request) -> dict[str, int]:
    """Parse the cart cookie. It is client-controlled input: never trust its shape."""
    try:
        cart = json.loads(urllib.parse.unquote(request.cookies.get(CART_COOKIE) or ""))
        return {
            s: q
            for s, q in cart.items()
            if s in PRODUCTS and isinstance(q, int) and not isinstance(q, bool) and q > 0
        }
    except (ValueError, TypeError, AttributeError, RecursionError):
        return {}


def write_cart(response, cart: dict[str, int]) -> None:
    response.set_cookie(
        CART_COOKIE, urllib.parse.quote(json.dumps(cart)), httponly=True, samesite="lax"
    )


def cart_total(cart: dict[str, int]) -> int:
    return sum(PRODUCTS[sku].price_chf * qty for sku, qty in cart.items())


@app.post("/cart/add")
def cart_add(request: Request, sku: str = Form(...)):
    if sku not in PRODUCTS:
        raise HTTPException(status_code=404)
    cart = read_cart(request)
    cart[sku] = cart.get(sku, 0) + 1
    prefix = locale_prefix(request)
    response = RedirectResponse(url=f"{prefix}/cart", status_code=303)
    write_cart(response, cart)
    return response


@app.post("/cart/remove")
def cart_remove(request: Request, sku: str = Form(...)):
    cart = read_cart(request)
    cart.pop(sku, None)
    prefix = locale_prefix(request)
    response = RedirectResponse(url=f"{prefix}/cart", status_code=303)
    write_cart(response, cart)
    return response


@app.get("/cart", response_class=HTMLResponse)
def cart_view(request: Request):
    cart = read_cart(request)
    return page(request, "cart.html", cart=cart, total=cart_total(cart))


@app.get("/checkout", response_class=HTMLResponse)
def checkout_view(request: Request):
    cart = read_cart(request)
    return page(request, "checkout.html", cart=cart, total=cart_total(cart),
                shipping=SHIPPING_CHF)


@app.post("/checkout")
def checkout_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    address: str = Form(...),
    postcode: str = Form(...),
    city: str = Form(...),
    shipping: str = Form("standard"),
):
    cart = read_cart(request)
    prefix = locale_prefix(request)
    if not cart:
        return RedirectResponse(url=f"{prefix}/cart", status_code=303)

    order_id = secrets.token_hex(4)
    ORDERS[order_id] = {
        "id": order_id,
        "cart": cart,
        "total": cart_total(cart) + SHIPPING_CHF.get(shipping, 0),
        "name": name,
        "locale": request.state.locale,
    }
    response = RedirectResponse(url=f"{prefix}/order/{order_id}", status_code=303)
    write_cart(response, {})
    return response


@app.get("/order/{order_id}", response_class=HTMLResponse)
def order_view(request: Request, order_id: str):
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404)
    return page(request, "order.html", order=order)


def keys_for_path(path: str) -> list[str]:
    CATALOGS.refresh()
    keys = []
    for key, meta in CATALOGS.source["strings"].items():
        for pattern in meta["surfaces"]:
            if pattern == "*" or fnmatch.fnmatch(path, pattern):
                keys.append(key)
                break
    return keys


@app.get("/_state")
def state(request: Request, path: str = "/", locale: str = DEFAULT_LOCALE):
    CATALOGS.refresh()
    counts = state_counts(CATALOGS, keys_for_path(path), locale)
    return Response(
        status_code=204,
        headers={
            "X-Catalog-Version": CATALOGS.version,
            "X-State-Counts": json.dumps(counts),
            "Cache-Control": "no-store",
        },
    )


SESSION_COOKIE = "firn_sid"
init_db(connect())  # ensure the schema exists at startup


@app.middleware("http")
async def track(request: Request, call_next):
    response = await call_next(request)
    path = request.scope["path"]
    if request.method == "GET" and not path.startswith(("/static", "/_", "/admin")):
        session_id = request.cookies.get(SESSION_COOKIE) or uuid.uuid4().hex
        conn = connect()
        try:
            record_event(
                conn,
                ts=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
                session_id=session_id,
                locale=getattr(request.state, "locale", DEFAULT_LOCALE),
                path=path,
                event_type="page_view",
                referrer="direct",
                device="desktop",
            )
        finally:
            conn.close()
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")
    return response


@app.get("/admin/analytics", response_class=HTMLResponse)
def analytics_dashboard(request: Request):
    conn = connect()  # per-request short-lived connection, per ruling C2
    try:
        paths = top_paths(conn, limit=12)
        max_views = max((r["views"] for r in paths), default=1)
        return page(
            request,
            "analytics.html",
            paths=paths,
            max_views=max_views,
            funnel=locale_funnel(conn),
            revenue=revenue_by_locale(conn),
        )
    finally:
        conn.close()
