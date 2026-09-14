from functools import lru_cache
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（agent/）
BASE_DIR = Path(__file__).resolve().parent.parent
# 当前工作目录，用于定位 .env 文件
CWD = Path(os.getcwd())


def _bootstrap_env_files() -> None:
    """按优先级从低到高加载多层 .env 文件到进程环境变量。

    加载顺序（后者覆盖前者）：
      1. .env                — 基础默认值
      2. .env.local          — 本地开发覆盖（不入版本控制）
      3. .env.{ENV}          — 当前环境配置（如 .env.development）
      4. .env.{ENV}.local    — 当前环境本地覆盖
    """
    env_bootstrap = os.getenv("ENV", "development").strip() or "development"
    env_files = [
        ".env",
        ".env.local",
        f".env.{env_bootstrap}",
        f".env.{env_bootstrap}.local",
    ]

    for env_file_name in env_files:
        path = CWD / env_file_name
        if not path.exists():
            continue

        data = dotenv_values(path)
        for key, value in data.items():
            if value is not None:
                os.environ[key] = value


# 启动时立即加载环境变量，确保后续 Settings 初始化能读到值
_bootstrap_env_files()


class EnvSettings(BaseSettings):
    """所有环境配置的基类，忽略未声明的额外字段。"""
    model_config = SettingsConfigDict(extra="ignore")

class AppSettings(EnvSettings):
    """应用基础配置。"""

    host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    port: int = Field(default=9110, validation_alias="APP_PORT")

class StorageSettings(EnvSettings):
    """对象存储配置（OpenDAL），支持本地文件系统（fs）和 S3 两种后端。"""

    # 存储类型："fs" 使用本地文件系统，"s3" 使用 S3 兼容服务
    storage_type: str = Field(default="s3", validation_alias="OPENDAL_STORAGE_TYPE")
    # 本地文件系统存储根目录，仅 storage_type=fs 时生效
    fs_root: Path = Field(
        default=BASE_DIR / "data",
        validation_alias="OPENDAL_FS_ROOT",
    )
    # S3 Bucket 名称
    bucket: str = Field(default="", validation_alias="OPENDAL_S3_BUCKET")
    # S3 服务地址（如 http://localhost:9003）
    endpoint: str = Field(default="", validation_alias="OPENDAL_S3_ENDPOINT")
    # S3 区域
    region: str = Field(default="us-east-1", validation_alias="OPENDAL_S3_REGION")
    # S3 Access Key ID
    access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    # S3 Secret Access Key
    secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")


class OpenAISettings(EnvSettings):
    """OpenAI-compatible 模型服务配置。"""

    # 模型服务地址（兼容 OpenAI API 格式）
    base_url: str = Field(
        default="http://172.18.179.2:20014/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    # 模型名称
    model: str = Field(default="qwen3.6-35b", validation_alias="OPENAI_MODEL")
    # API Key，本地无鉴权服务可使用占位值
    api_key: str = Field(default="not-needed", validation_alias="OPENAI_API_KEY")
    # 请求超时时间（秒）
    timeout_seconds: int = Field(
        default=60,
        validation_alias="OPENAI_TIMEOUT_SECONDS",
    )
    # 最大输出 token 数；不填则不传，由模型默认
    max_tokens: int | None = Field(
        default=None,
        validation_alias="OPENAI_MAX_TOKENS",
    )


class LangfuseSettings(EnvSettings):
    """Langfuse 追踪配置，留空时自动禁用追踪。"""

    public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias="LANGFUSE_HOST",
    )


class DatabaseSettings(EnvSettings):
    """数据库配置。

    支持两种配置方式（优先级从高到低）：
      1. DATABASE_URL — 完整连接字符串（如 postgresql://... 或 mysql://...）
      2. DB_DRIVER + DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME — 独立字段拼接
    """

    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    driver: str = Field(default="postgresql", validation_alias="DB_DRIVER")
    host: str = Field(default="localhost", validation_alias="DB_HOST")
    port: int = Field(default=5432, validation_alias="DB_PORT")
    user: str = Field(default="agent", validation_alias="DB_USER")
    password: str = Field(default="agent", validation_alias="DB_PASSWORD")
    name: str = Field(default="agent", validation_alias="DB_NAME")

    @property
    def url(self) -> str:
        if self.database_url:
            return self.database_url
        driver = self.driver.strip().lower()
        if driver in {"postgres", "postgresql"}:
            scheme = "postgresql"
        elif driver in {"mysql", "mariadb"}:
            scheme = "mysql"
        else:
            raise ValueError(
                f"不支持的 DB_DRIVER={self.driver!r}，仅支持 postgresql 或 mysql"
            )
        return f"{scheme}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(EnvSettings):
    """Redis 配置。"""

    host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    db: int = Field(default=0, validation_alias="REDIS_DB")

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class AuthSettings(EnvSettings):
    """用户登录配置。"""

    # 系统管理员账号 — 启动时若数据库中不存在该用户则自动创建
    admin_account: str = Field(default="", validation_alias="ADMIN_ACCOUNT")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    # 登录 session 滑动过期时间（秒）
    session_ttl_seconds: int = Field(default=7200, validation_alias="SESSION_TTL_SECONDS")


class Settings(BaseModel):
    """全局配置聚合，通过 get_settings() 获取单例。"""

    app: AppSettings
    storage: StorageSettings
    openai: OpenAISettings
    langfuse: LangfuseSettings
    database: DatabaseSettings
    redis: RedisSettings
    auth: AuthSettings


def load_app_settings() -> AppSettings:
    return AppSettings()


def load_storage_settings() -> StorageSettings:
    return StorageSettings()


def load_openai_settings() -> OpenAISettings:
    return OpenAISettings()


def load_langfuse_settings() -> LangfuseSettings:
    return LangfuseSettings()


def load_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def load_redis_settings() -> RedisSettings:
    return RedisSettings()


def load_auth_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例，首次调用时从环境变量加载，之后缓存复用。"""
    return Settings(
        app=load_app_settings(),
        storage=load_storage_settings(),
        openai=load_openai_settings(),
        langfuse=load_langfuse_settings(),
        database=load_database_settings(),
        redis=load_redis_settings(),
        auth=load_auth_settings(),
    )
