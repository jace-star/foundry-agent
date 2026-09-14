"""统一认证身份模型。

供 get_current_user_or_api_key 返回，下游通过 principal.type 区分来源。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.models.api_key import ApiKeySummary
from src.models.user import UserPublic


class AuthPrincipal(BaseModel):
    """统一的认证身份，标识请求来源（用户 or API Key）。"""

    type: Literal["user", "api_key"]
    user: UserPublic | None = None
    api_key: ApiKeySummary | None = None
