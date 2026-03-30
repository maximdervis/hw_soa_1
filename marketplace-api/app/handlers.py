"""Shared API helpers used by impl."""
from typing import Any

from fastapi.responses import JSONResponse


def _api_error(error_code: str, message: str, status_code: int, details: Any = None):
    return JSONResponse(status_code=status_code, content={"error_code": error_code, "message": message, "details": details})
