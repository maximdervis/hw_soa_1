"""Репозитории для работы с БД."""
from decimal import Decimal
from typing import Optional

from openapi_server.models.product_status import ProductStatus


def product_list(
    cur,
    page: int,
    size: int,
    status: Optional[ProductStatus] = None,
    category: Optional[str] = None,
):
    conditions, params = [], []
    if status is not None:
        conditions.append("p.status = %s")
        params.append(status.value)
    if category is not None:
        conditions.append("p.category = %s")
        params.append(category)
    where = (" AND " + " AND ".join(conditions)) if conditions else ""
    params.extend([size, page * size])
    cur.execute(
        f"""
        SELECT COUNT(*) OVER () AS total, p.id, p.name, p.description, p.price, p.stock,
               p.category, p.status, p.created_at, p.updated_at
        FROM products p
        WHERE 1=1 {where}
        ORDER BY p.id
        LIMIT %s OFFSET %s
        """,
        params,
    )
    rows = cur.fetchall()
    total = rows[0]["total"] if rows else 0
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "price": float(r["price"]),
            "stock": r["stock"],
            "category": r["category"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ], total


def product_get(cur, id: int):
    cur.execute(
        "SELECT id, name, description, price, stock, category, status, seller_id, created_at, updated_at FROM products WHERE id = %s",
        (id,),
    )
    r = cur.fetchone()
    if not r:
        return None
    return {**r, "price": float(r["price"])}


def product_create(cur, name: str, description: Optional[str], price: float, stock: int, category: str, status: str, seller_id: Optional[int]):
    cur.execute(
        """INSERT INTO products (name, description, price, stock, category, status, seller_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, name, description, price, stock, category, status, created_at, updated_at""",
        (name, description, Decimal(str(price)), stock, category, status, seller_id),
    )
    r = cur.fetchone()
    return {**r, "price": float(r["price"])}


def product_update(cur, id: int, **kwargs):
    allowed = {"name", "description", "price", "stock", "category", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return product_get(cur, id)
    if "price" in updates:
        updates["price"] = Decimal(str(updates["price"]))
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    params = list(updates.values()) + [id]
    cur.execute(
        f"UPDATE products SET {set_clause} WHERE id = %s RETURNING id, name, description, price, stock, category, status, created_at, updated_at",
        params,
    )
    r = cur.fetchone()
    return {**r, "price": float(r["price"])} if r else None


def product_archive(cur, id: int):
    cur.execute("UPDATE products SET status = 'ARCHIVED' WHERE id = %s RETURNING id", (id,))
    return cur.fetchone() is not None


def product_decrement_stock(cur, product_id: int, quantity: int):
    cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s RETURNING id", (quantity, product_id, quantity))
    return cur.fetchone() is not None


def product_increment_stock(cur, product_id: int, quantity: int):
    cur.execute("UPDATE products SET stock = stock + %s WHERE id = %s", (quantity, product_id))


def user_by_email(cur, email: str):
    cur.execute("SELECT id, email, password_hash, role FROM users WHERE email = %s", (email,))
    return cur.fetchone()


def user_create(cur, email: str, password_hash: str, role: str):
    cur.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING id, email, role",
        (email, password_hash, role),
    )
    return cur.fetchone()


def user_get(cur, id: int):
    cur.execute("SELECT id, email, role FROM users WHERE id = %s", (id,))
    return cur.fetchone()


def order_get(cur, id: int):
    cur.execute(
        """SELECT id, user_id, status, promo_code_id, total_amount, discount_amount, created_at, updated_at
           FROM orders WHERE id = %s""",
        (id,),
    )
    return cur.fetchone()


def order_items_get(cur, order_id: int):
    cur.execute(
        "SELECT id, product_id, quantity, price_at_order FROM order_items WHERE order_id = %s",
        (order_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def order_create(cur, user_id: int, total_amount: float, discount_amount: float, promo_code_id: Optional[int]):
    cur.execute(
        """INSERT INTO orders (user_id, status, promo_code_id, total_amount, discount_amount)
           VALUES (%s, 'CREATED', %s, %s, %s) RETURNING id, user_id, status, total_amount, discount_amount, created_at, updated_at""",
        (user_id, promo_code_id, Decimal(str(total_amount)), Decimal(str(discount_amount))),
    )
    return cur.fetchone()


def order_items_insert(cur, order_id: int, product_id: int, quantity: int, price_at_order: float):
    cur.execute(
        "INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES (%s, %s, %s, %s)",
        (order_id, product_id, quantity, Decimal(str(price_at_order))),
    )


def order_update_items(cur, order_id: int, total_amount: float, discount_amount: float, promo_code_id: Optional[int]):
    cur.execute(
        "UPDATE orders SET total_amount = %s, discount_amount = %s, promo_code_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (Decimal(str(total_amount)), Decimal(str(discount_amount)), promo_code_id, order_id),
    )


def order_cancel(cur, order_id: int):
    cur.execute("UPDATE orders SET status = 'CANCELED' WHERE id = %s", (order_id,))


def last_user_operation(cur, user_id: int, operation_type: str):
    cur.execute(
        "SELECT created_at FROM user_operations WHERE user_id = %s AND operation_type = %s ORDER BY created_at DESC LIMIT 1",
        (user_id, operation_type),
    )
    return cur.fetchone()


def user_operation_log(cur, user_id: int, operation_type: str):
    cur.execute("INSERT INTO user_operations (user_id, operation_type) VALUES (%s, %s)", (user_id, operation_type))


def active_order_for_user(cur, user_id: int):
    cur.execute(
        "SELECT id FROM orders WHERE user_id = %s AND status IN ('CREATED', 'PAYMENT_PENDING') LIMIT 1",
        (user_id,),
    )
    return cur.fetchone()


def promo_by_code(cur, code: str):
    cur.execute(
        """SELECT id, code, discount_type, discount_value, min_order_amount, max_uses, current_uses, valid_from, valid_until, active
           FROM promo_codes WHERE code = %s""",
        (code,),
    )
    return cur.fetchone()


def promo_increment_uses(cur, promo_id: int):
    cur.execute("UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = %s", (promo_id,))


def promo_decrement_uses(cur, promo_id: int):
    cur.execute("UPDATE promo_codes SET current_uses = current_uses - 1 WHERE id = %s AND current_uses > 0", (promo_id,))


def promo_code_create(cur, data: dict):
    cur.execute(
        """INSERT INTO promo_codes (code, discount_type, discount_value, min_order_amount, max_uses, valid_from, valid_until)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, code, discount_type, discount_value, min_order_amount, max_uses, current_uses, valid_from, valid_until, active""",
        (
            data["code"],
            data["discount_type"],
            Decimal(str(data["discount_value"])),
            Decimal(str(data["min_order_amount"])),
            data["max_uses"],
            data["valid_from"],
            data["valid_until"],
        ),
    )
    r = cur.fetchone()
    return {**r, "discount_value": float(r["discount_value"]), "min_order_amount": float(r["min_order_amount"])} if r else None
