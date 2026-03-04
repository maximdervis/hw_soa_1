"""Реализация Auth API."""
from typing import Optional

from fastapi.responses import JSONResponse

from app.database import get_db
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app import repositories as repo
from app.handlers import _api_error
from generated.openapi_server.apis.auth_api_base import BaseAuthApi
from generated.openapi_server.models.register_request import RegisterRequest
from generated.openapi_server.models.login_request import LoginRequest
from generated.openapi_server.models.refresh_request import RefreshRequest
from generated.openapi_server.models.token_pair import TokenPair
from generated.openapi_server.models.user_response import UserResponse
from generated.openapi_server.models.user_role import UserRole


class AuthImpl(BaseAuthApi):
    async def register(self, register_request: RegisterRequest) -> UserResponse:
        with get_db() as conn:
            cur = conn.cursor()
            if repo.user_by_email(cur, register_request.email):
                return _api_error("VALIDATION_ERROR", "Email уже зарегистрирован", 400)
            user = repo.user_create(cur, register_request.email, hash_password(register_request.password), register_request.role.value)
        return UserResponse(id=user["id"], email=user["email"], role=UserRole(user["role"]))

    async def login(self, login_request: LoginRequest) -> TokenPair:
        with get_db() as conn:
            cur = conn.cursor()
            user = repo.user_by_email(cur, login_request.email)
        if not user or not verify_password(login_request.password, user["password_hash"]):
            return JSONResponse(401, content={"error_code": "TOKEN_INVALID", "message": "Invalid credentials", "details": None})
        access, exp = create_access_token(user["id"], user["role"])
        refresh = create_refresh_token(user["id"])
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=exp)

    async def refresh_token(self, refresh_request: Optional[RefreshRequest]) -> TokenPair:
        if not refresh_request:
            return JSONResponse(401, content={"error_code": "REFRESH_TOKEN_INVALID", "message": "Missing refresh token", "details": None})
        payload, _ = decode_token(refresh_request.refresh_token)
        if not payload or payload.get("type") != "refresh":
            return JSONResponse(401, content={"error_code": "REFRESH_TOKEN_INVALID", "message": "Invalid refresh token", "details": None})
        uid = int(payload["sub"])
        with get_db() as conn:
            cur = conn.cursor()
            user = repo.user_get(cur, uid)
        if not user:
            return JSONResponse(401, content={"error_code": "REFRESH_TOKEN_INVALID", "message": "User not found", "details": None})
        access, exp = create_access_token(uid, user["role"])
        new_refresh = create_refresh_token(uid)
        return TokenPair(access_token=access, refresh_token=new_refresh, expires_in=exp)
