"""Контекст текущего запроса: токен из Authorization (для impl, когда генератор не передаёт его)."""
from contextvars import ContextVar
from types import SimpleNamespace
from typing import Optional

from openapi_server.models.user_role import UserRole

# Объект с .sub (str) и .role (UserRole) — совместим с тем, что ожидает impl
_request_token_ctx: ContextVar[Optional[SimpleNamespace]] = ContextVar("request_token", default=None)


def set_request_token(sub: str, role: str) -> None:
    _request_token_ctx.set(SimpleNamespace(sub=sub, role=UserRole(role)))


def get_request_token() -> Optional[SimpleNamespace]:
    return _request_token_ctx.get()
