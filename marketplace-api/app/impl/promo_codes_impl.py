"""Реализация Promo Codes API."""
from app.auth_context import get_request_token
from app.database import get_db
from app import repositories as repo
from app.handlers import _api_error
from openapi_server.apis.promo_codes_api_base import BasePromoCodesApi
from openapi_server.models.extra_models import TokenModel
from openapi_server.models.promo_code_response import PromoCodeResponse


class PromoCodesImpl(BasePromoCodesApi):
    async def create_promo_code(self, promo_code_create, token: TokenModel = None):
        token = token or get_request_token()
        if token is None:
            return _api_error("TOKEN_INVALID", "Требуется авторизация", 401)
        with get_db() as conn:
            cur = conn.cursor()
            r = repo.promo_code_create(cur, promo_code_create.model_dump())
        return PromoCodeResponse(**r)
