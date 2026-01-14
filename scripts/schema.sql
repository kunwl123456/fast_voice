-- Fast Voice 数据库建表脚本
-- 时区: Asia/Shanghai
-- 更新时间: 2025-12-23

-- 设置时区
SET TIME ZONE 'Asia/Shanghai';

-- 创建枚举类型：任务状态
CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');

-- 创建枚举类型：交易类型
CREATE TYPE tx_type AS ENUM ('recharge', 'consume', 'refund', 'subscription');

-- 创建枚举类型：订阅计划
CREATE TYPE subscription_plan AS ENUM ('free', 'pro', 'enterprise');

-- 表：users
-- 用途：用户账号（登录/改名/改密码），直接拥有API Key、积分账户等资源
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL DEFAULT '',
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    avatar_url VARCHAR(512) DEFAULT '' NOT NULL;
    subscription_plan subscription_plan NOT NULL DEFAULT 'free',
    subscription_ends_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_plan ON users(subscription_plan);

-- 表：api_keys
-- 用途：OpenAPI 鉴权凭证
-- 权限：仅企业版用户可创建
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    api_key VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_api_key ON api_keys(api_key);

-- 表：credit_accounts
-- 用途：用户积分账户（余额）
CREATE TABLE credit_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_credit_accounts_user_id ON credit_accounts(user_id);

-- 表：credit_transactions
-- 用途：积分流水（记账/对账/追踪扣费原因）
CREATE TABLE credit_transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES credit_accounts(id),
    tx_type tx_type NOT NULL,
    amount INTEGER NOT NULL,
    ref_type VARCHAR(50) NOT NULL DEFAULT '',
    ref_id VARCHAR(100) NOT NULL DEFAULT '',
    note VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_credit_transactions_account_id ON credit_transactions(account_id);
CREATE INDEX idx_credit_transactions_tx_type ON credit_transactions(tx_type);

-- 表：voices
-- 用途：音色实体（克隆结果）。公开音色即进入"声音大厅"
-- 注意：允许同一用户创建多个同名音色，通过 uuid 作为唯一标识
CREATE TABLE voices (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    owner_user_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255) NOT NULL DEFAULT '',
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    preview_audio_path VARCHAR(255) NOT NULL DEFAULT '',
    clone_job_uuid VARCHAR(36) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_voices_uuid ON voices(uuid);
CREATE INDEX idx_voices_owner_user_id ON voices(owner_user_id);
CREATE INDEX idx_voices_is_public ON voices(is_public);
CREATE INDEX idx_voices_clone_job_uuid ON voices(clone_job_uuid);

-- 表：tts_jobs
-- 用途：TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款
CREATE TABLE tts_jobs (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    voice_uuid VARCHAR(36) REFERENCES voices(uuid) ON DELETE SET NULL,
    voice_name VARCHAR(120) NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    text_utf8_bytes INTEGER NOT NULL,
    cost_credits INTEGER NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    speed_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    temperature DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    top_k INTEGER NOT NULL DEFAULT 5,
    top_p DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    webhook_url VARCHAR(512) NOT NULL DEFAULT '',
    status job_status NOT NULL DEFAULT 'queued',
    error VARCHAR(255) NOT NULL DEFAULT '',
    output_audio_path VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_tts_jobs_uuid ON tts_jobs(uuid);
CREATE INDEX idx_tts_jobs_user_id ON tts_jobs(user_id);
CREATE INDEX idx_tts_jobs_voice_uuid ON tts_jobs(voice_uuid);
CREATE INDEX idx_tts_jobs_status ON tts_jobs(status);

-- 表：clone_jobs
-- 用途：音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）
CREATE TABLE clone_jobs (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    voice_name VARCHAR(120) NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    status job_status NOT NULL DEFAULT 'queued',
    error VARCHAR(255) NOT NULL DEFAULT '',
    dataset_dir VARCHAR(255) NOT NULL DEFAULT '',
    result_voice_uuid VARCHAR(36),
    external_request_id VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_clone_jobs_uuid ON clone_jobs(uuid);
CREATE INDEX idx_clone_jobs_user_id ON clone_jobs(user_id);
CREATE INDEX idx_clone_jobs_status ON clone_jobs(status);

-- 表：api_request_logs
-- 用途：记录API请求日志，用于Dashboard展示和分析
CREATE TABLE api_request_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    api_key_id INTEGER NOT NULL REFERENCES api_keys(id),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    response_size INTEGER NOT NULL DEFAULT 0,
    error_message VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_api_request_logs_user_id ON api_request_logs(user_id);
CREATE INDEX idx_api_request_logs_api_key_id ON api_request_logs(api_key_id);
CREATE INDEX idx_api_request_logs_status_code ON api_request_logs(status_code);
CREATE INDEX idx_api_request_logs_created_at ON api_request_logs(created_at);

-- 注释说明
COMMENT ON TABLE users IS '用户账号（登录/改名/改密码），直接拥有API Key、积分账户等资源';
COMMENT ON TABLE api_keys IS 'OpenAPI 鉴权凭证（api_key 以 sk- 开头，仅企业版用户可创建）';
COMMENT ON TABLE credit_accounts IS '用户积分账户（余额）';
COMMENT ON TABLE credit_transactions IS '积分流水（记账/对账/追踪扣费原因）';
COMMENT ON TABLE voices IS '音色实体（克隆结果）。公开音色即进入"声音大厅"';
COMMENT ON TABLE tts_jobs IS 'TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款';
COMMENT ON TABLE clone_jobs IS '音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）';
COMMENT ON TABLE api_request_logs IS 'API请求日志，用于Dashboard展示和分析';

-- 列注释
COMMENT ON COLUMN users.email IS '登录邮箱';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash';
COMMENT ON COLUMN users.display_name IS '展示名';
COMMENT ON COLUMN users.is_admin IS '管理员：可调账';
COMMENT ON COLUMN users.avatar_url IS '用户头像URL链接';
COMMENT ON COLUMN users.subscription_plan IS '订阅计划：free(免费版), pro(专业版), enterprise(企业版)';
COMMENT ON COLUMN users.subscription_ends_at IS '订阅到期时间（免费版为null）';
COMMENT ON COLUMN users.created_at IS '创建时间';

COMMENT ON COLUMN api_keys.user_id IS '所属用户';
COMMENT ON COLUMN api_keys.api_key IS 'API Key（以 sk- 开头，用于 Bearer Token）';
COMMENT ON COLUMN api_keys.name IS '密钥名称（用于展示）';
COMMENT ON COLUMN api_keys.is_active IS '是否启用';
COMMENT ON COLUMN api_keys.expires_at IS '有效期（为空表示永久有效）';

COMMENT ON COLUMN credit_accounts.user_id IS '1 user : 1 account';
COMMENT ON COLUMN credit_accounts.balance IS '当前余额（积分）';
COMMENT ON COLUMN credit_accounts.updated_at IS '最近更新时间';

COMMENT ON COLUMN credit_transactions.account_id IS '归属账户';
COMMENT ON COLUMN credit_transactions.tx_type IS '类型：recharge(充值), consume(消费), refund(退款), subscription(订阅赠送)';
COMMENT ON COLUMN credit_transactions.amount IS '+ 入账 / - 扣费';
COMMENT ON COLUMN credit_transactions.ref_type IS '关联对象类型（tts/clone/admin/subscription）';
COMMENT ON COLUMN credit_transactions.ref_id IS '关联对象 id（job id）';
COMMENT ON COLUMN credit_transactions.note IS '备注';

COMMENT ON COLUMN voices.owner_user_id IS '拥有者（用户）';
COMMENT ON COLUMN voices.name IS '音色名称';
COMMENT ON COLUMN voices.description IS '描述';
COMMENT ON COLUMN voices.is_public IS '是否公开';
COMMENT ON COLUMN voices.preview_audio_path IS '本地预览音频路径';

COMMENT ON COLUMN tts_jobs.user_id IS '调用方（用户）';
COMMENT ON COLUMN tts_jobs.voice_id IS '使用的音色';
COMMENT ON COLUMN tts_jobs.text IS '输入文本';
COMMENT ON COLUMN tts_jobs.text_utf8_bytes IS '输入文本 UTF-8 字节数（计费依据）';
COMMENT ON COLUMN tts_jobs.cost_credits IS '扣费积分（= bytes * price）';
COMMENT ON COLUMN tts_jobs.webhook_url IS 'Webhook 回调地址（任务完成时调用，可选）';
COMMENT ON COLUMN tts_jobs.status IS '状态：queued(已入队), running(处理中), succeeded(成功), failed(失败)';
COMMENT ON COLUMN tts_jobs.error IS '错误码（失败时）';
COMMENT ON COLUMN tts_jobs.output_audio_path IS '产出音频本地路径';

COMMENT ON COLUMN clone_jobs.user_id IS '调用方（用户）';
COMMENT ON COLUMN clone_jobs.voice_name IS '目标音色名';
COMMENT ON COLUMN clone_jobs.is_public IS '产出音色是否公开';
COMMENT ON COLUMN clone_jobs.status IS '状态：queued(已入队), running(处理中), succeeded(成功), failed(失败)';
COMMENT ON COLUMN clone_jobs.dataset_dir IS '本地数据集目录（上传文件落这里）';
COMMENT ON COLUMN clone_jobs.result_voice_id IS '成功后关联 voices.id';

COMMENT ON COLUMN api_request_logs.user_id IS '调用用户';
COMMENT ON COLUMN api_request_logs.api_key_id IS '使用的API Key';
COMMENT ON COLUMN api_request_logs.endpoint IS '请求端点，如 /v1/completions';
COMMENT ON COLUMN api_request_logs.method IS 'HTTP方法：GET/POST/PUT/DELETE';
COMMENT ON COLUMN api_request_logs.status_code IS 'HTTP状态码';
COMMENT ON COLUMN api_request_logs.latency_ms IS '请求延迟（毫秒）';
COMMENT ON COLUMN api_request_logs.response_size IS '响应大小（字节）';
COMMENT ON COLUMN api_request_logs.error_message IS '错误信息';

-- 订阅计划说明
COMMENT ON TYPE subscription_plan IS '订阅计划类型：
- free: 免费版（每月1000积分，100次请求，3个克隆位，无API访问，不可商业使用）
- pro: 专业版（每月10000积分，5000次请求，20个克隆位，无API访问，可商业使用）
- enterprise: 企业版（每月100000积分，500000次请求，无限克隆位，提供API访问，可商业使用）';
