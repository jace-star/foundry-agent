"""认证模块 — 密码、Redis Session、API Key、FastAPI 依赖的聚合出口。"""

from src.core.auth.user import (
    create_session,
    delete_session,
    get_current_user,
    get_current_user_or_api_key,
    hash_password,
    verify_password,
)
from src.core.auth.api_key import (
    decrypt_key,
    delete_key_record,
    encrypt_key,
    generate_api_key,
    hash_key,
    list_key_records,
    read_key_record,
    save_key_record,
    validate_api_key,
)

__all__ = [
    # deps (password + session + dependencies)
    "create_session",
    "delete_session",
    "get_current_user",
    "get_current_user_or_api_key",
    "hash_password",
    "verify_password",
    # api_key
    "decrypt_key",
    "delete_key_record",
    "encrypt_key",
    "generate_api_key",
    "hash_key",
    "list_key_records",
    "read_key_record",
    "save_key_record",
    "validate_api_key",
]
