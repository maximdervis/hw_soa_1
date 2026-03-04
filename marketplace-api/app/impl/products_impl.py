"""Реализация Products API."""
from typing import Optional

from app.database import get_db
from app import repositories as repo
from app.handlers import _api_error
from generated.openapi_server.apis.products_api_base import BaseProductsApi
from generated.openapi_server.models.extra_models import TokenModel
from generated.openapi_server.models.product_create import ProductCreate
from generated.openapi_server.models.product_update import ProductUpdate
from generated.openapi_server.models.product_response import ProductResponse
from generated.openapi_server.models.product_page import ProductPage
from generated.openapi_server.models.product_status import ProductStatus
from generated.openapi_server.models.user_role import UserRole


def _seller_can_edit(product_seller_id: Optional[int], user_id: int, role: UserRole) -> bool:
    return role == UserRole.ADMIN or (role == UserRole.SELLER and product_seller_id == user_id)


class ProductsImpl(BaseProductsApi):
    async def list_products(self, page, size, status, category, token=None):
        page, size = page or 0, size or 20
        with get_db() as conn:
            cur = conn.cursor()
            rows, total = repo.product_list(cur, page, size, status, category)
        return ProductPage(
            content=[ProductResponse(**r) for r in rows],
            total_elements=total,
            page=page,
            size=size,
        )

    async def create_product(self, product_create: ProductCreate, token: TokenModel = None):
        uid, role = int(token.sub), token.role
        seller_id = uid if role == UserRole.SELLER else None
        with get_db() as conn:
            cur = conn.cursor()
            r = repo.product_create(
                cur, product_create.name, product_create.description, product_create.price, product_create.stock,
                product_create.category, product_create.status.value, seller_id,
            )
        return ProductResponse(**r)

    async def get_product(self, id, token: TokenModel = None):
        with get_db() as conn:
            cur = conn.cursor()
            r = repo.product_get(cur, id)
        if not r:
            return _api_error("PRODUCT_NOT_FOUND", "Товар не найден", 404)
        return ProductResponse(**r)

    async def update_product(self, id, product_update: ProductUpdate, token: TokenModel = None):
        uid, role = int(token.sub), token.role
        with get_db() as conn:
            cur = conn.cursor()
            existing = repo.product_get(cur, id)
        if not existing:
            return _api_error("PRODUCT_NOT_FOUND", "Товар не найден", 404)
        if not _seller_can_edit(existing.get("seller_id"), uid, role):
            return _api_error("ACCESS_DENIED", "Недостаточно прав", 403)
        updates = product_update.model_dump(exclude_unset=True)
        if "status" in updates:
            updates["status"] = updates["status"].value
        with get_db() as conn:
            cur = conn.cursor()
            r = repo.product_update(cur, id, **updates)
        return ProductResponse(**r)

    async def delete_product(self, id, token: TokenModel = None):
        uid, role = int(token.sub), token.role
        with get_db() as conn:
            cur = conn.cursor()
            existing = repo.product_get(cur, id)
        if not existing:
            return _api_error("PRODUCT_NOT_FOUND", "Товар не найден", 404)
        if not _seller_can_edit(existing.get("seller_id"), uid, role):
            return _api_error("ACCESS_DENIED", "Недостаточно прав", 403)
        with get_db() as conn:
            cur = conn.cursor()
            repo.product_archive(cur, id)
        return None
