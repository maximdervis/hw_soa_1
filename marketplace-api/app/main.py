"""Точка входа: FastAPI + сгенерированные роуты из OpenAPI."""
import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth import decode_token
from app.auth_context import set_request_token
from app.exceptions import ApiException

# Регистрация реализаций до импорта роутеров (Base*Api.subclasses)
import app.impl.auth_impl  # noqa: F401
import app.impl.products_impl  # noqa: F401
import app.impl.orders_impl  # noqa: F401
import app.impl.promo_codes_impl  # noqa: F401

from generated.openapi_server.apis.auth_api import router as AuthApiRouter
from generated.openapi_server.apis.orders_api import router as OrdersApiRouter
from generated.openapi_server.apis.products_api import router as ProductsApiRouter
from generated.openapi_server.apis.promo_codes_api import router as PromoCodesApiRouter

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

app = FastAPI(title="Marketplace API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(AuthApiRouter, prefix="/api/v1")
app.include_router(ProductsApiRouter, prefix="/api/v1")
app.include_router(OrdersApiRouter, prefix="/api/v1")
app.include_router(PromoCodesApiRouter, prefix="/api/v1")


def _mask_body(body: dict) -> dict:
    if not body:
        return {}
    out = dict(body)
    for key in ("password", "refresh_token"):
        if key in out and out[key]:
            out[key] = "***"
    return out


@app.middleware("http")
async def request_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request_id_ctx.set(rid)
    start = time.perf_counter()
    body_bytes = b""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        body_bytes = await request.body()

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    # Токен в контекст для impl (генератор не передаёт token в вызовы)
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        payload, _ = decode_token(auth[7:].strip())
        if payload and payload.get("type") == "access":
            set_request_token(payload["sub"], payload.get("role", "USER"))

    req = Request(request.scope, receive) if body_bytes else request
    response = await call_next(req)
    duration_ms = round((time.perf_counter() - start) * 1000)
    user_id = None
    if auth and auth.startswith("Bearer "):
        payload, _ = decode_token(auth[7:].strip())
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
    log_entry = {
        "request_id": rid,
        "method": request.method,
        "endpoint": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "user_id": user_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if body_bytes:
        try:
            log_entry["body"] = _mask_body(json.loads(body_bytes))
        except Exception:
            pass
    logging.info(json.dumps(log_entry))
    response.headers["X-Request-Id"] = rid
    return response


@app.exception_handler(ApiException)
def handle_api_exception(_request: Request, exc: ApiException):
    status_map = {
        "PRODUCT_NOT_FOUND": 404,
        "ORDER_NOT_FOUND": 404,
        "PRODUCT_INACTIVE": 409,
        "ORDER_HAS_ACTIVE": 409,
        "INVALID_STATE_TRANSITION": 409,
        "INSUFFICIENT_STOCK": 409,
        "PROMO_CODE_INVALID": 422,
        "PROMO_CODE_MIN_AMOUNT": 422,
        "ORDER_OWNERSHIP_VIOLATION": 403,
        "ORDER_LIMIT_EXCEEDED": 429,
        "ACCESS_DENIED": 403,
    }
    code = status_map.get(exc.error_code, 400)
    return JSONResponse(
        status_code=code,
        content={"error_code": exc.error_code, "message": exc.message, "details": exc.details},
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(_request: Request, exc: RequestValidationError):
    details = {"errors": [{"loc": str(e["loc"]), "msg": e.get("msg", "")} for e in exc.errors()]}
    return JSONResponse(
        status_code=400,
        content={"error_code": "VALIDATION_ERROR", "message": "Ошибка валидации входных данных", "details": details},
    )


@app.exception_handler(Exception)
def handle_unhandled(_request: Request, exc: Exception):
    logging.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "service": "marketplace-api"}
