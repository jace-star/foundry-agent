"""全局异常响应处理。"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

def register_exception_handlers(app: FastAPI) -> None:
    """注册统一的异常处理器。"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return _json_error(exc.status_code, _format_detail(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _json_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "请求参数错误。",
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        """Pydantic 模型校验错误（如 ORM -> Schema 转换失败）。"""
        logger.exception("Pydantic 校验异常: {}", exc)
        return _json_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "服务器内部错误。",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常: {}", exc)
        return _json_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "服务器内部错误。",
        )


def _json_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": message},
    )


def _format_detail(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return str(detail)
