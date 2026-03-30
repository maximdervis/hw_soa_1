"""Orders API implementation."""
from app.auth_context import get_request_token
from app.database import get_db
from app import repositories as repo
from app.order_service import create_order as svc_create_order, update_order as svc_update_order, cancel_order as svc_cancel_order
from app.exceptions import ApiException
from app.handlers import _api_error
from openapi_server.apis.orders_api_base import BaseOrdersApi
from openapi_server.models.extra_models import TokenModel
from openapi_server.models.order_response import OrderResponse
from openapi_server.models.order_item_response import OrderItemResponse
from openapi_server.models.user_role import UserRole


def _dict_to_order_response(d: dict) -> OrderResponse:
    return OrderResponse(
        id=d["id"], user_id=d["user_id"], status=d["status"],
        items=[OrderItemResponse(**i) for i in d["items"]],
        total_amount=d["total_amount"], discount_amount=d["discount_amount"],
        created_at=d["created_at"], updated_at=d["updated_at"],
    )


class OrdersImpl(BaseOrdersApi):
    async def create_order(self, order_create, token: TokenModel = None):
        token = token or get_request_token()
        if token is None:
            return _api_error("TOKEN_INVALID", "Authorization required", 401)
        if token.role == UserRole.SELLER:
            return _api_error("ACCESS_DENIED", "Insufficient permissions", 403)
        uid = int(token.sub)
        try:
            with get_db() as conn:
                return _dict_to_order_response(svc_create_order(conn, uid, order_create))
        except ApiException:
            raise

    async def get_order(self, id, token: TokenModel = None):
        token = token or get_request_token()
        if token is None:
            return _api_error("TOKEN_INVALID", "Authorization required", 401)
        if token.role == UserRole.SELLER:
            return _api_error("ACCESS_DENIED", "Insufficient permissions", 403)
        uid, role = int(token.sub), token.role
        with get_db() as conn:
            cur = conn.cursor()
            order = repo.order_get(cur, id)
        if not order:
            return _api_error("ORDER_NOT_FOUND", "Order not found", 404)
        if role == UserRole.USER and order["user_id"] != uid:
            return _api_error("ORDER_OWNERSHIP_VIOLATION", "Order belongs to another user", 403)
        with get_db() as conn:
            cur = conn.cursor()
            items = repo.order_items_get(cur, id)
        return OrderResponse(
            id=order["id"],
            user_id=order["user_id"],
            status=order["status"],
            items=[OrderItemResponse(id=i["id"], product_id=i["product_id"], quantity=i["quantity"], price_at_order=float(i["price_at_order"])) for i in items],
            total_amount=float(order["total_amount"]),
            discount_amount=float(order["discount_amount"]),
            created_at=order["created_at"],
            updated_at=order["updated_at"],
        )

    async def update_order(self, id, order_update, token: TokenModel = None):
        token = token or get_request_token()
        if token is None:
            return _api_error("TOKEN_INVALID", "Authorization required", 401)
        if token.role == UserRole.SELLER:
            return _api_error("ACCESS_DENIED", "Insufficient permissions", 403)
        uid = int(token.sub)
        try:
            with get_db() as conn:
                return _dict_to_order_response(svc_update_order(conn, id, uid, order_update))
        except ApiException:
            raise

    async def cancel_order(self, id, token: TokenModel = None):
        token = token or get_request_token()
        if token is None:
            return _api_error("TOKEN_INVALID", "Authorization required", 401)
        if token.role == UserRole.SELLER:
            return _api_error("ACCESS_DENIED", "Insufficient permissions", 403)
        uid = int(token.sub)
        try:
            with get_db() as conn:
                svc_cancel_order(conn, id, uid)
        except ApiException:
            raise
        return None
