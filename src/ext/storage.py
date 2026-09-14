"""
统一存储抽象层 —— 基于 OpenDAL 提供本地文件系统 (fs) 和 S3 兼容存储的统一访问接口。

使用方式:
    from src.ext.storage import get_storage_operator

    op = get_storage_operator()
    op.write("reports/2024/q1.pdf", pdf_bytes)
    data = op.read("reports/2024/q1.pdf")

存储类型通过环境变量 OPENDAL_STORAGE_TYPE 切换（"fs" 或 "s3"），
具体配置见 StorageSettings。
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import opendal

from src.config import StorageSettings, get_settings


class StorageConfigError(RuntimeError):
    """存储配置校验失败时抛出。"""
    pass


@lru_cache
def get_storage_operator() -> opendal.Operator:
    """创建并缓存 OpenDAL Operator（全局单例，进程生命周期内复用）。"""
    storage = get_settings().storage
    storage_type = storage.storage_type.lower()

    if storage_type == "fs":
        return opendal.Operator("fs", root=_prepare_fs_root(storage.fs_root))

    if storage_type == "s3":
        return _create_s3_operator(storage)

    raise StorageConfigError("OPENDAL_STORAGE_TYPE 仅支持 fs 或 s3。")


def _prepare_fs_root(fs_root: Path) -> str:
    """将用户配置的 fs_root 展开为绝对路径并确保存在。"""
    root = fs_root.expanduser()
    if not root.is_absolute():
        root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return str(root)


def _create_s3_operator(storage: StorageSettings) -> opendal.Operator:
    """校验 S3 配置并创建 Operator。"""
    endpoint = _normalize_s3_endpoint(storage.endpoint)
    if not endpoint:
        raise StorageConfigError("OPENDAL_S3_ENDPOINT 不能为空。")
    if not storage.bucket:
        raise StorageConfigError("OPENDAL_S3_BUCKET 不能为空。")
    if not storage.access_key_id:
        raise StorageConfigError("AWS_ACCESS_KEY_ID 不能为空。")
    if not storage.secret_access_key:
        raise StorageConfigError("AWS_SECRET_ACCESS_KEY 不能为空。")

    return opendal.Operator(
        "s3",
        root="/",
        bucket=storage.bucket,
        endpoint=endpoint,
        region=storage.region,
        access_key_id=storage.access_key_id,
        secret_access_key=storage.secret_access_key,
    )


def _normalize_s3_endpoint(endpoint: str) -> str:
    """校验 endpoint 协议，仅允许 http/https 或无协议裸地址。"""
    value = endpoint.strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return value
    if parsed.scheme:
        raise StorageConfigError("OPENDAL_S3_ENDPOINT 仅支持 http 或 https。")
    return value
