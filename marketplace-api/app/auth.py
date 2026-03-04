"""JWT и проверка прав."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.app_config import settings
from generated.openapi_server.models.user_role import UserRole

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    exp_min = settings.access_token_minutes
    expires = datetime.now(timezone.utc) + timedelta(minutes=exp_min)
    payload = {"sub": str(user_id), "role": role, "exp": expires, "type": "access"}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, exp_min * 60


def create_refresh_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    payload = {"sub": str(user_id), "exp": expires, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> tuple[Optional[dict], Optional[str]]:
    """Возвращает (payload, None) при успехе или (None, error_code)."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"]), None
    except jwt.ExpiredSignatureError:
        return None, "TOKEN_EXPIRED"
    except jwt.InvalidTokenError:
        return None, "TOKEN_INVALID"


def get_current_user_id(payload: dict) -> int:
    return int(payload["sub"])


def get_current_user_role(payload: dict) -> UserRole:
    return UserRole(payload.get("role", "USER"))
