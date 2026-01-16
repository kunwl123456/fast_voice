from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    运行配置（环境变量驱动）。
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=None,  # 禁用自动加载 .env，由外部控制
    )

    # 异步驱动的数据库连接字符串
    # - Postgres: postgresql+asyncpg://...
    database_url: str

    redis_url: str | None = None
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # JWT 配置
    jwt_secret: str
    jwt_issuer: str = "fast-voice"
    jwt_access_token_minutes: int = 60 * 24

    # 管理员账户
    admin_email: str
    admin_password: str
    pro_email: str
    pro_password: str

    # 每字符消耗的积分数
    credit_price_per_utf8_byte: int = 1
    # TTS的最大字符数限制
    max_text_utf8_bytes: int = 6000

    # 音频文件上传限制
    max_audio_file_size_mb: int = 32  # 最大 32MB
    max_audio_file_size_bytes: int = 32 * 1024 * 1024  # 33554432 字节
    supported_audio_formats: list[str] = [".mp3", ".wav", ".m4a"]

    # 测试用特殊邀请码（绕过数据库验证）
    # 通过环境变量 TEST_INVITE_CODE 设置
    test_invite_code: str | None = None

    auto_create_db: bool = True
    admin_bootstrap: bool = True
    data_dir: str = "./data"

    # SQLAlchemy 连接池配置
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800

    # 支付页面配置
    payment_success_url: str
    payment_cancel_url: str

    # 支付中台配置
    payment_gateway_url: str | None = None  # 支付中台 API 地址
    payment_gateway_app_id: str | None = None  # 支付中台应用标识
    payment_callback_url: str | None = (
        None  # 支付完成回调地址（支付中台调用此地址通知结果）
    )
    payment_callback_secret: str | None = (
        None  # 支付中台回调签名密钥（用于验证回调合法性）
    )


settings = Settings()
