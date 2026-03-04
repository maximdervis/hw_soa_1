"""Реализация Promo Codes API."""
from app.database import get_db
from app import repositories as repo
from generated.openapi_server.apis.promo_codes_api_base import BasePromoCodesApi
from generated.openapi_server.models.extra_models import TokenModel
from generated.openapi_server.models.promo_code_response import PromoCodeResponse


class PromoCodesImpl(BasePromoCodesApi):
    async def create_promo_code(self, promo_code_create, token: TokenModel = None):
        with get_db() as conn:
            cur = conn.cursor()
            r = repo.promo_code_create(cur, promo_code_create.model_dump())
        return PromoCodeResponse(**r)
