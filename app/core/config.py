from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    运行配置（环境变量驱动）。

    说明：
    - V1 默认支持 Postgres（生产）与 SQLite（本地/测试）。
    - 连接池参数仅对非 SQLite 生效（SQLite 用 StaticPool/NullPool 更合理）。
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Web API 用异步驱动（推荐）：
    # - Postgres: postgresql+asyncpg://...
    # - SQLite:   sqlite+aiosqlite:///...
    database_url: str = "sqlite+aiosqlite:///./fast_voice.db"
    # Celery/同步脚本用同步驱动（与 database_url 指向同一数据库）：
    # - Postgres: postgresql+psycopg://...
    # - SQLite:   sqlite+pysqlite:///...
    database_url_sync: str | None = None
    redis_url: str | None = None

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    jwt_secret: str = "dev-secret"
    jwt_issuer: str = "fast-voice"
    jwt_access_token_minutes: int = 60 * 24
    admin_email: str = "admin@autogame.ai"
    admin_password: str = "123456"

    # Fernet key (base64 urlsafe 32-byte)，用于加密存储 api_secret
    api_secret_enc_key: str = ""

    signature_time_window_seconds: int = 300
    credit_price_per_utf8_byte: int = 1
    max_text_utf8_bytes: int = 4000

    auto_create_db: bool = True
    admin_bootstrap: bool = True
    data_dir: str = "./data"

    # SQLAlchemy 连接池（仅对非 SQLite 生效）
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800


settings = Settings()


