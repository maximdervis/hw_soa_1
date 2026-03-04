"""Бизнес-логика заказов (создание, обновление, отмена)."""
from datetime import datetime, timezone

from app.app_config import settings
from app import repositories as repo
from app.exceptions import ApiException
from openapi_server.models.order_create import OrderCreate
from openapi_server.models.order_update import OrderUpdate


def _apply_promo_discount(total: float, promo: dict) -> float:
    ptype = promo["discount_type"]
    val = float(promo["discount_value"])
    if ptype == "PERCENTAGE":
        discount = total * val / 100
        if discount > total * 0.7:
            discount = total * 0.7
        return total - discount
    else:  # FIXED_AMOUNT
        return max(0, total - min(val, total))


def create_order(conn, user_id: int, body: OrderCreate) -> dict:
    cur = conn.cursor()

    # 1. Rate limit CREATE_ORDER
    last_op = repo.last_user_operation(cur, user_id, "CREATE_ORDER")
    if last_op:
        delta_min = (datetime.now(timezone.utc) - last_op["created_at"].replace(tzinfo=timezone.utc)).total_seconds() / 60
        if delta_min < settings.order_rate_limit_minutes:
            raise ApiException("ORDER_LIMIT_EXCEEDED", "Превышен лимит частоты создания заказа")

    # 2. No active order
    if repo.active_order_for_user(cur, user_id):
        raise ApiException("ORDER_HAS_ACTIVE", "У пользователя уже есть активный заказ")

    # 3. Check products exist and ACTIVE, and stock
    total_amount = 0.0
    items_with_price = []
    insufficient = []
    for it in body.items:
        prod = repo.product_get(cur, it.product_id)
        if not prod:
            raise ApiException("PRODUCT_NOT_FOUND", "Товар не найден")
        if prod["status"] != "ACTIVE":
            raise ApiException("PRODUCT_INACTIVE", "Товар неактивен")
        if prod["stock"] < it.quantity:
            insufficient.append({"product_id": it.product_id, "requested": it.quantity, "available": prod["stock"]})
        else:
            price = float(prod["price"])
            total_amount += price * it.quantity
            items_with_price.append((it.product_id, it.quantity, price))
    if insufficient:
        raise ApiException("INSUFFICIENT_STOCK", "Недостаточно товара на складе", {"items": insufficient})

    # 4. Reserve stock
    for product_id, qty, _ in items_with_price:
        if not repo.product_decrement_stock(cur, product_id, qty):
            raise ApiException("INSUFFICIENT_STOCK", "Недостаточно товара на складе")

    discount_amount = 0.0
    promo_code_id = None
    if body.promo_code:
        promo = repo.promo_by_code(cur, body.promo_code)
        if not promo or not promo["active"] or promo["current_uses"] >= promo["max_uses"]:
            raise ApiException("PROMO_CODE_INVALID", "Промокод недействителен")
        now = datetime.now(timezone.utc)
        vf = promo["valid_from"] if promo["valid_from"].tzinfo else promo["valid_from"].replace(tzinfo=timezone.utc)
        vu = promo["valid_until"] if promo["valid_until"].tzinfo else promo["valid_until"].replace(tzinfo=timezone.utc)
        if now < vf or now > vu:
            raise ApiException("PROMO_CODE_INVALID", "Промокод недействителен")
        if total_amount < float(promo["min_order_amount"]):
            raise ApiException("PROMO_CODE_MIN_AMOUNT", "Сумма заказа ниже минимальной для промокода")
        new_total = _apply_promo_discount(total_amount, promo)
        discount_amount = total_amount - new_total
        total_amount = new_total
        promo_code_id = promo["id"]
        repo.promo_increment_uses(cur, promo["id"])

    # 5. Create order and items
    order = repo.order_create(cur, user_id, total_amount, discount_amount, promo_code_id)
    for product_id, qty, price in items_with_price:
        repo.order_items_insert(cur, order["id"], product_id, qty, price)

    repo.user_operation_log(cur, user_id, "CREATE_ORDER")

    # Load full order for response
    return _order_response(cur, order["id"])


def _order_response(cur, order_id: int) -> dict:
    order = repo.order_get(cur, order_id)
    items = repo.order_items_get(cur, order_id)
    return {
        "id": order["id"],
        "user_id": order["user_id"],
        "status": order["status"],
        "items": [{"id": i["id"], "product_id": i["product_id"], "quantity": i["quantity"], "price_at_order": float(i["price_at_order"])} for i in items],
        "total_amount": float(order["total_amount"]),
        "discount_amount": float(order["discount_amount"]),
        "created_at": order["created_at"],
        "updated_at": order["updated_at"],
    }


def update_order(conn, order_id: int, user_id: int, body: OrderUpdate) -> dict:
    cur = conn.cursor()
    order = repo.order_get(cur, order_id)
    if not order:
        raise ApiException("ORDER_NOT_FOUND", "Заказ не найден")
    if order["user_id"] != user_id:
        raise ApiException("ORDER_OWNERSHIP_VIOLATION", "Заказ принадлежит другому пользователю")
    if order["status"] != "CREATED":
        raise ApiException("INVALID_STATE_TRANSITION", "Недопустимый переход состояния заказа")

    last_op = repo.last_user_operation(cur, user_id, "UPDATE_ORDER")
    if last_op:
        delta_min = (datetime.now(timezone.utc) - last_op["created_at"].replace(tzinfo=timezone.utc)).total_seconds() / 60
        if delta_min < settings.order_rate_limit_minutes:
            raise ApiException("ORDER_LIMIT_EXCEEDED", "Превышен лимит частоты обновления заказа")

    old_items = repo.order_items_get(cur, order_id)
    for i in old_items:
        repo.product_increment_stock(cur, i["product_id"], i["quantity"])

    total_amount = 0.0
    items_with_price = []
    for it in body.items:
        prod = repo.product_get(cur, it.product_id)
        if not prod:
            raise ApiException("PRODUCT_NOT_FOUND", "Товар не найден")
        if prod["status"] != "ACTIVE":
            raise ApiException("PRODUCT_INACTIVE", "Товар неактивен")
        if prod["stock"] < it.quantity:
            raise ApiException("INSUFFICIENT_STOCK", "Недостаточно товара на складе")
        price = float(prod["price"])
        total_amount += price * it.quantity
        items_with_price.append((it.product_id, it.quantity, price))

    for product_id, qty, _ in items_with_price:
        repo.product_decrement_stock(cur, product_id, qty)

    discount_amount = 0.0
    promo_code_id = order.get("promo_code_id")
    if promo_code_id:
        cur.execute("SELECT * FROM promo_codes WHERE id = %s", (promo_code_id,))
        promo = cur.fetchone()
        if promo and promo["active"] and total_amount >= float(promo["min_order_amount"]):
            discounted = _apply_promo_discount(total_amount, dict(promo))
            discount_amount = total_amount - discounted
            total_amount = discounted
        else:
            repo.promo_decrement_uses(cur, promo_code_id)
            promo_code_id = None

    cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
    for product_id, qty, price in items_with_price:
        repo.order_items_insert(cur, order_id, product_id, qty, price)
    repo.order_update_items(cur, order_id, total_amount, discount_amount, promo_code_id)
    repo.user_operation_log(cur, user_id, "UPDATE_ORDER")
    return _order_response(cur, order_id)


def cancel_order(conn, order_id: int, user_id: int) -> None:
    cur = conn.cursor()
    order = repo.order_get(cur, order_id)
    if not order:
        raise ApiException("ORDER_NOT_FOUND", "Заказ не найден")
    if order["user_id"] != user_id:
        raise ApiException("ORDER_OWNERSHIP_VIOLATION", "Заказ принадлежит другому пользователю")
    if order["status"] not in ("CREATED", "PAYMENT_PENDING"):
        raise ApiException("INVALID_STATE_TRANSITION", "Недопустимый переход состояния заказа")
    for i in repo.order_items_get(cur, order_id):
        repo.product_increment_stock(cur, i["product_id"], i["quantity"])
    if order.get("promo_code_id"):
        repo.promo_decrement_uses(cur, order["promo_code_id"])
    repo.order_cancel(cur, order_id)
