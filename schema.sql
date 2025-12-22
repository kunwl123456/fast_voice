-- Fast Voice 数据库建表脚本
-- 时区: Asia/Shanghai
-- 生成时间: 2025-12-22

-- 设置时区
SET TIME ZONE 'Asia/Shanghai';

-- 创建枚举类型：任务状态
CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');

-- 创建枚举类型：交易类型
CREATE TYPE tx_type AS ENUM ('recharge', 'consume', 'refund');

-- 表：users
-- 用途：Console 用户账号（登录/改名/改密码），并拥有一个或多个 Project
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL DEFAULT '',
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_users_email ON users(email);

-- 表：projects
-- 用途：OpenAPI 的调用主体（B 端按 project 计费/限流/额度）
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    owner_user_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(120) NOT NULL DEFAULT 'default',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_projects_owner_user_id ON projects(owner_user_id);

-- 表：api_keys
-- 用途：OpenAPI 鉴权凭证（api_key 公开，api_secret 仅用于签名，服务端加密存储）
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    api_key VARCHAR(128) NOT NULL UNIQUE,
    api_secret_ciphertext TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_api_keys_project_id ON api_keys(project_id);
CREATE INDEX idx_api_keys_api_key ON api_keys(api_key);

-- 表：credit_accounts
-- 用途：项目积分账户（余额）
CREATE TABLE credit_accounts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL UNIQUE REFERENCES projects(id),
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_credit_accounts_project_id ON credit_accounts(project_id);

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
CREATE TABLE voices (
    id SERIAL PRIMARY KEY,
    owner_project_id INTEGER NOT NULL REFERENCES projects(id),
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255) NOT NULL DEFAULT '',
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    preview_audio_path VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
    CONSTRAINT uq_voice_owner_name UNIQUE (owner_project_id, name)
);

-- 创建索引
CREATE INDEX idx_voices_owner_project_id ON voices(owner_project_id);
CREATE INDEX idx_voices_is_public ON voices(is_public);

-- 表：tts_jobs
-- 用途：TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款
CREATE TABLE tts_jobs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    voice_id INTEGER NOT NULL REFERENCES voices(id),
    text TEXT NOT NULL,
    text_utf8_bytes INTEGER NOT NULL,
    cost_credits INTEGER NOT NULL,
    status job_status NOT NULL DEFAULT 'queued',
    error VARCHAR(255) NOT NULL DEFAULT '',
    output_audio_path VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_tts_jobs_project_id ON tts_jobs(project_id);
CREATE INDEX idx_tts_jobs_voice_id ON tts_jobs(voice_id);
CREATE INDEX idx_tts_jobs_status ON tts_jobs(status);

-- 表：clone_jobs
-- 用途：音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）
CREATE TABLE clone_jobs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    voice_name VARCHAR(120) NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    status job_status NOT NULL DEFAULT 'queued',
    error VARCHAR(255) NOT NULL DEFAULT '',
    dataset_dir VARCHAR(255) NOT NULL DEFAULT '',
    result_voice_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
);

-- 创建索引
CREATE INDEX idx_clone_jobs_project_id ON clone_jobs(project_id);
CREATE INDEX idx_clone_jobs_status ON clone_jobs(status);

-- 注释说明
COMMENT ON TABLE users IS 'Console 用户账号（登录/改名/改密码），并拥有一个或多个 Project';
COMMENT ON TABLE projects IS 'OpenAPI 的调用主体（B 端按 project 计费/限流/额度）';
COMMENT ON TABLE api_keys IS 'OpenAPI 鉴权凭证（api_key 公开，api_secret 仅用于签名，服务端加密存储）';
COMMENT ON TABLE credit_accounts IS '项目积分账户（余额）';
COMMENT ON TABLE credit_transactions IS '积分流水（记账/对账/追踪扣费原因）';
COMMENT ON TABLE voices IS '音色实体（克隆结果）。公开音色即进入"声音大厅"';
COMMENT ON TABLE tts_jobs IS 'TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款';
COMMENT ON TABLE clone_jobs IS '音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）';

-- 列注释
COMMENT ON COLUMN users.email IS '登录邮箱';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash';
COMMENT ON COLUMN users.display_name IS '展示名';
COMMENT ON COLUMN users.is_admin IS '管理员：可调账';
COMMENT ON COLUMN users.created_at IS '创建时间';

COMMENT ON COLUMN projects.owner_user_id IS '所属用户';
COMMENT ON COLUMN projects.name IS '项目名';

COMMENT ON COLUMN api_keys.api_key IS '公开 key（请求头 X-API-Key）';
COMMENT ON COLUMN api_keys.api_secret_ciphertext IS 'Fernet 加密后的 secret';
COMMENT ON COLUMN api_keys.is_active IS '是否启用';

COMMENT ON COLUMN credit_accounts.project_id IS '1 project : 1 account';
COMMENT ON COLUMN credit_accounts.balance IS '当前余额（积分）';
COMMENT ON COLUMN credit_accounts.updated_at IS '最近更新时间';

COMMENT ON COLUMN credit_transactions.account_id IS '归属账户';
COMMENT ON COLUMN credit_transactions.tx_type IS '类型：recharge(充值), consume(消费), refund(退款)';
COMMENT ON COLUMN credit_transactions.amount IS '+ 入账 / - 扣费';
COMMENT ON COLUMN credit_transactions.ref_type IS '关联对象类型（tts/clone/admin）';
COMMENT ON COLUMN credit_transactions.ref_id IS '关联对象 id（job id）';
COMMENT ON COLUMN credit_transactions.note IS '备注';

COMMENT ON COLUMN voices.owner_project_id IS '拥有者（project）';
COMMENT ON COLUMN voices.name IS '音色名称';
COMMENT ON COLUMN voices.description IS '描述';
COMMENT ON COLUMN voices.is_public IS '是否公开';
COMMENT ON COLUMN voices.preview_audio_path IS '本地预览音频路径';

COMMENT ON COLUMN tts_jobs.project_id IS '调用方（project）';
COMMENT ON COLUMN tts_jobs.voice_id IS '使用的音色';
COMMENT ON COLUMN tts_jobs.text IS '输入文本';
COMMENT ON COLUMN tts_jobs.text_utf8_bytes IS '输入文本 UTF-8 字节数（计费依据）';
COMMENT ON COLUMN tts_jobs.cost_credits IS '扣费积分（= bytes * price）';
COMMENT ON COLUMN tts_jobs.status IS '状态：queued(已入队), running(处理中), succeeded(成功), failed(失败)';
COMMENT ON COLUMN tts_jobs.error IS '错误码（失败时）';
COMMENT ON COLUMN tts_jobs.output_audio_path IS '产出音频本地路径';

COMMENT ON COLUMN clone_jobs.project_id IS '调用方（project）';
COMMENT ON COLUMN clone_jobs.voice_name IS '目标音色名';
COMMENT ON COLUMN clone_jobs.is_public IS '产出音色是否公开';
COMMENT ON COLUMN clone_jobs.status IS '状态：queued(已入队), running(处理中), succeeded(成功), failed(失败)';
COMMENT ON COLUMN clone_jobs.dataset_dir IS '本地数据集目录（上传文件落这里）';
COMMENT ON COLUMN clone_jobs.result_voice_id IS '成功后关联 voices.id';

