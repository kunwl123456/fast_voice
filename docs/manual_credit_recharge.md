# 手动充值积分操作文档

## 📋 概述

本文档说明如何为指定用户手动充值积分。适用于以下场景：
- 用户反馈问题补偿
- 促销活动赠送
- 测试账号充值
- 特殊情况调整

---

## 方法一：直接数据库操作（推荐）

### 适用场景
- 一次性快速充值
- 不需要通过 API
- 直接访问数据库权限

### 操作步骤

#### 步骤 1：连接数据库

```bash
docker exec -it fast-voice-pg psql -U postgres -d fast_voice
```

#### 步骤 2：查询用户信息

```sql
-- 根据邮箱查询用户 UUID 和基本信息
SELECT uuid, email, display_name FROM users WHERE email = '用户邮箱';
```

**示例：**
```sql
SELECT uuid, email, display_name FROM users WHERE email = 'wc@autogame.ai';
```

**输出示例：**
```
                 uuid                 |     email      | display_name 
--------------------------------------+----------------+--------------
 a81d8969-b42a-4f03-9297-9326c3a85d8c | wc@autogame.ai | 王超
```

#### 步骤 3：查看当前积分余额

```sql
SELECT u.email, u.display_name, ca.balance 
FROM users u 
JOIN credit_accounts ca ON u.id = ca.user_id 
WHERE u.email = '用户邮箱';
```

#### 步骤 4：充值积分

```sql
-- 增加积分（将 10000 替换为实际充值金额）
UPDATE credit_accounts 
SET balance = balance + 10000 
WHERE user_id = (SELECT id FROM users WHERE email = '用户邮箱');
```

#### 步骤 5：记录充值流水（推荐）

```sql
-- 记录充值流水，用于审计追踪
INSERT INTO credit_transactions (account_id, tx_type, amount, ref_type, ref_id, note, created_at)
SELECT 
    ca.id,
    'recharge',
    10000,  -- 充值金额，需与步骤4保持一致
    'admin_manual',
    'manual_recharge_' || EXTRACT(EPOCH FROM NOW())::TEXT,
    '管理员手动充值 - 备注信息',  -- 可自定义备注
    NOW()
FROM credit_accounts ca
JOIN users u ON ca.user_id = u.id
WHERE u.email = '用户邮箱';
```

#### 步骤 6：验证充值结果

```sql
SELECT u.email, u.display_name, ca.balance 
FROM users u 
JOIN credit_accounts ca ON u.id = ca.user_id 
WHERE u.email = '用户邮箱';
```

#### 步骤 7：退出数据库

```sql
\q
```

### 完整示例（复制即用）

```sql
-- 1. 查看当前积分余额
SELECT u.email, u.display_name, ca.balance 
FROM users u 
JOIN credit_accounts ca ON u.id = ca.user_id 
WHERE u.email = 'wc@autogame.ai';

-- 2. 充值 10000 积分
UPDATE credit_accounts 
SET balance = balance + 10000 
WHERE user_id = (SELECT id FROM users WHERE email = 'wc@autogame.ai');

-- 3. 记录充值流水
INSERT INTO credit_transactions (account_id, tx_type, amount, ref_type, ref_id, note, created_at)
SELECT 
    ca.id,
    'recharge',
    10000,
    'admin_manual',
    'manual_recharge_' || EXTRACT(EPOCH FROM NOW())::TEXT,
    '管理员手动充值 - 王超',
    NOW()
FROM credit_accounts ca
JOIN users u ON ca.user_id = u.id
WHERE u.email = 'wc@autogame.ai';

-- 4. 验证充值结果
SELECT u.email, u.display_name, ca.balance 
FROM users u 
JOIN credit_accounts ca ON u.id = ca.user_id 
WHERE u.email = 'wc@autogame.ai';
```

---

## 方法二：通过 API 接口充值

### 适用场景
- 需要完整的审计日志
- 通过程序自动化充值
- 需要权限控制

### 操作步骤

#### 步骤 1：查询用户 UUID

通过数据库或 API 获取用户的 UUID：

```bash
docker exec -it fast-voice-pg psql -U postgres -d fast_voice -c \
  "SELECT uuid FROM users WHERE email = '用户邮箱';"
```

#### 步骤 2：管理员登录获取 Token

```bash
curl -X POST http://localhost:8123/console/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@autogame.ai",
    "password": "Nank$$CA#RKdU78tt"
  }'
```

**响应示例：**
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": { ... }
  }
}
```

保存返回的 `access_token`。

#### 步骤 3：调用充值接口

```bash
curl -X POST http://localhost:8123/console/credits/admin/recharge \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <管理员的access_token>" \
  -d '{
    "user_id": "<用户的UUID>",
    "amount": 10000,
    "note": "管理员手动充值"
  }'
```

**请求参数说明：**
- `user_id`: 用户的 UUID（从步骤1获取）
- `amount`: 充值金额（必须为正整数）
- `note`: 备注说明（可选）

**响应示例：**
```json
{
  "code": 0,
  "message": "充值成功",
  "data": {
    "user_id": "a81d8969-b42a-4f03-9297-9326c3a85d8c",
    "amount": 10000
  }
}
```

#### 步骤 4：验证充值结果

用户可以通过控制台查看积分余额：

```bash
curl -X GET http://localhost:8123/console/credits/balance \
  -H "Authorization: Bearer <用户的access_token>"
```

---

## 📊 积分配置说明

### 当前计费标准

- **单价：** 1 积分/字节（UTF-8 编码）
- **配置位置：** `app/core/config.py` - `credit_price_per_utf8_byte`
- **环境变量：** `CREDIT_PRICE_PER_UTF8_BYTE`

### 订阅计划默认积分

配置文件：`app/core/constants.py`

| 订阅计划 | 每月赠送积分 | 月度请求配额 | 克隆位限制 |
|---------|-------------|-------------|-----------|
| 免费版（free） | 1,000 | 100 | 3 |
| 专业版（pro） | 10,000 | 5,000 | 20 |
| 企业版（enterprise） | 100,000 | 500,000 | 无限 |

### 积分消费示例

假设文本：`"你好，这是一段测试文本"`
- UTF-8 字节数：约 36 字节
- 消耗积分：36 积分

---

## ⚠️ 注意事项

1. **充值金额必须为正整数**
   - ✅ 正确：1000, 10000, 50000
   - ❌ 错误：-1000, 0, 1000.5

2. **建议记录充值流水**
   - 方便后续审计和追踪
   - 可以通过 `credit_transactions` 表查询历史记录

3. **数据库操作需谨慎**
   - 建议先在测试环境验证
   - 操作前先备份数据（如有必要）

4. **API 接口需要管理员权限**
   - 只有 `is_admin = true` 的用户才能调用充值接口
   - 默认管理员账号：`admin@autogame.ai`

---

## 🔍 常用查询命令

### 查询用户积分余额

```sql
SELECT 
    u.email,
    u.display_name,
    u.subscription_plan,
    ca.balance as current_balance
FROM users u
JOIN credit_accounts ca ON u.id = ca.user_id
WHERE u.email = '用户邮箱';
```

### 查询用户积分流水

```sql
SELECT 
    ct.created_at,
    ct.tx_type,
    ct.amount,
    ct.ref_type,
    ct.note
FROM credit_transactions ct
JOIN credit_accounts ca ON ct.account_id = ca.id
JOIN users u ON ca.user_id = u.id
WHERE u.email = '用户邮箱'
ORDER BY ct.created_at DESC
LIMIT 20;
```

### 查询所有用户积分统计

```sql
SELECT 
    u.email,
    u.display_name,
    u.subscription_plan,
    ca.balance,
    u.created_at as register_date
FROM users u
JOIN credit_accounts ca ON u.id = ca.user_id
ORDER BY ca.balance DESC;
```

### 查询积分消费 Top 10 用户

```sql
SELECT 
    u.email,
    u.display_name,
    SUM(CASE WHEN ct.tx_type = 'consume' THEN ABS(ct.amount) ELSE 0 END) as total_consumed
FROM users u
JOIN credit_accounts ca ON u.id = ca.user_id
JOIN credit_transactions ct ON ct.account_id = ca.id
GROUP BY u.id, u.email, u.display_name
ORDER BY total_consumed DESC
LIMIT 10;
```

---

## 📞 技术支持

如有问题，请联系系统管理员或查看以下文档：
- API 文档：`docs/api_reference.md`
- 数据库 Schema：`scripts/schema.sql`
- 配置说明：`README.md`

---

**文档版本：** v1.0  
**最后更新：** 2026-01-12  
**维护者：** 系统管理员
