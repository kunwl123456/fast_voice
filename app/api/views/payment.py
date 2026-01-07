"""支付管理相关路由"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User, StripePayment, PaymentStatus
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.responses import success_response
from app.routers import payment_router as router
from app.core.deps import get_db, require_console
from app.core.schemas import (
    Response,
    CreatePaymentIntentIn,
    CreatePaymentIntentOut,
    PaymentStatusOut,
    PaymentHistoryOut,
    StripeConfigOut,
)
from app.api.controller.payment import (
    create_payment_intent,
    get_payment_status,
    get_payment_history,
    get_stripe_config,
)


@router.get("/config", summary="获取 Stripe 配置", response_model=Response[StripeConfigOut])
async def get_config():
    """
    获取 Stripe 公开配置信息

    ### 功能说明
    - 返回 Stripe 公钥（用于前端初始化）
    - 不需要登录即可访问
    """
    config = get_stripe_config()
    return success_response("获取成功", config.model_dump())


@router.post(
    "/create-intent",
    summary="创建支付意图",
    response_model=Response[CreatePaymentIntentOut],
)
async def create_intent(
    payload: CreatePaymentIntentIn,
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    创建 Stripe 支付意图

    ### 功能说明
    - 创建支付订单并返回客户端密钥
    - 前端使用返回的 client_secret 完成支付

    ### 支付类型
    1. **积分充值** (credit_recharge)
       - 需要提供 `credits_amount`（充值的积分数量）
       - 示例：充值 10000 积分，支付 $10

    2. **订阅支付** (subscription)
       - 需要提供 `subscription_plan`（pro/enterprise）
       - 需要提供 `subscription_months`（订阅月数，1-12）
       - 示例：订阅 Pro 计划 3 个月

    ### 请求示例

    **积分充值：**
    ```json
    {
      "payment_type": "credit_recharge",
      "amount": 10.00,
      "credits_amount": 10000
    }
    ```

    **订阅支付：**
    ```json
    {
      "payment_type": "subscription",
      "amount": 29.99,
      "subscription_plan": "pro",
      "subscription_months": 1
    }
    ```
    """
    result = await create_payment_intent(db, user, payload)
    return success_response("创建支付意图成功", result.model_dump())


@router.get(
    "/{payment_id}/status",
    summary="查询支付状态",
    response_model=Response[PaymentStatusOut],
)
async def get_status(
    payment_id: str,
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    查询支付订单状态

    ### 功能说明
    - 查询指定支付订单的当前状态
    - 只能查询自己的支付订单

    ### 支付状态
    - `pending`: 待支付
    - `processing`: 处理中
    - `succeeded`: 支付成功
    - `failed`: 支付失败
    - `canceled`: 已取消
    - `refunded`: 已退款
    """
    result = await get_payment_status(db, user, payment_id)
    return success_response("获取成功", result.model_dump())


@router.get(
    "",
    summary="获取支付历史",
    response_model=Response[list[PaymentHistoryOut]],
)
async def get_history(
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的支付历史记录

    ### 功能说明
    - 返回最近 50 条支付记录
    - 按创建时间倒序排列
    """
    result = await get_payment_history(db, user)
    return success_response("获取成功", [r.model_dump() for r in result])


@router.get("/return", summary="支付完成返回页面", response_class=HTMLResponse)
async def payment_return(request: Request):
    """
    支付完成后的返回页面
    
    ### 功能说明
    - 用户完成支付后，Stripe 会重定向到此页面
    - 显示支付结果并提示用户操作
    - 支持支付宝、微信等重定向支付方式
    
    ### URL 参数
    - `payment_intent`: Stripe PaymentIntent ID
    - `payment_intent_client_secret`: 客户端密钥
    - `redirect_status`: 支付状态（succeeded/processing/failed）
    """
    # 获取 URL 参数
    payment_intent = request.query_params.get("payment_intent")
    redirect_status = request.query_params.get("redirect_status", "unknown")
    
    # 根据状态显示不同的消息
    if redirect_status == "succeeded":
        status_message = "✅ 支付成功！积分将在几秒内到账。"
        status_color = "#10b981"
    elif redirect_status == "processing":
        status_message = "⏳ 支付处理中，请稍候..."
        status_color = "#f59e0b"
    elif redirect_status == "failed":
        status_message = "❌ 支付失败，请重试。"
        status_color = "#ef4444"
    else:
        status_message = "❓ 未知状态"
        status_color = "#6b7280"
    
    # 返回简单的 HTML 页面
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>支付结果 - FastVoice</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                border-radius: 16px;
                padding: 48px;
                max-width: 500px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                text-align: center;
            }}
            .status {{
                font-size: 48px;
                margin-bottom: 24px;
            }}
            h1 {{
                color: {status_color};
                margin: 0 0 16px 0;
                font-size: 24px;
            }}
            p {{
                color: #6b7280;
                margin: 0 0 32px 0;
                font-size: 16px;
                line-height: 1.6;
            }}
            .payment-id {{
                background: #f3f4f6;
                padding: 12px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                color: #374151;
                margin: 24px 0;
                word-break: break-all;
            }}
            .button {{
                display: inline-block;
                background: {status_color};
                color: white;
                padding: 12px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                transition: opacity 0.2s;
            }}
            .button:hover {{
                opacity: 0.9;
            }}
            .countdown {{
                margin-top: 24px;
                color: #9ca3af;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">
                {'✅' if redirect_status == 'succeeded' else '⏳' if redirect_status == 'processing' else '❌'}
            </div>
            <h1>{status_message}</h1>
            <p>
                {'您的积分将自动充值到账户。' if redirect_status == 'succeeded' else 
                 '支付正在处理中，完成后积分会自动到账。' if redirect_status == 'processing' else 
                 '支付未完成，如有疑问请联系客服。'}
            </p>
            {f'<div class="payment-id">Payment ID: {payment_intent}</div>' if payment_intent else ''}
            <a href="/" class="button">返回首页</a>
            <div class="countdown" id="countdown">3 秒后自动跳转...</div>
        </div>
        <script>
            let seconds = 3;
            const countdownEl = document.getElementById('countdown');
            const timer = setInterval(() => {{
                seconds--;
                if (seconds > 0) {{
                    countdownEl.textContent = seconds + ' 秒后自动跳转...';
                }} else {{
                    clearInterval(timer);
                    window.location.href = '/';
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.post("/{payment_id}/test-success", summary="【测试】模拟支付成功", include_in_schema=False)
async def test_payment_success(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    """
    测试接口：直接模拟支付成功（仅用于开发测试）
    
    ### 功能
    - 查找对应的支付记录
    - 直接调用 webhook 处理逻辑
    - 更新支付状态并充值积分
    
    ### 注意
    - 此接口仅用于测试环境
    - 生产环境应该删除或禁用
    """
    from app.api.services.stripe_service import StripeService
    
    # 查找支付记录
    stmt = select(StripePayment).where(
        StripePayment.uuid == payment_id,
        StripePayment.user_id == user.id
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise NotFoundException("支付记录不存在")
    
    if payment.status != PaymentStatus.pending:
        raise BadRequestException(f"支付状态已经是 {payment.status}，无法模拟")
    
    # 模拟 PaymentIntent 对象
    class MockPaymentIntent:
        def __init__(self, pi_id, metadata_dict):
            self.id = pi_id
            self.metadata = metadata_dict
    
    mock_pi = MockPaymentIntent(
        payment.stripe_payment_intent_id,
        {
            "user_id": str(payment.user_id),
            "user_email": user.email,
            "payment_type": payment.payment_type.value,
            "credits_amount": str(payment.credits_amount) if payment.credits_amount else "",
            "subscription_plan": payment.subscription_plan.value if payment.subscription_plan else "",
            "subscription_months": str(payment.subscription_months) if payment.subscription_months else "",
        }
    )
    
    # 调用 webhook 处理逻辑
    await StripeService.handle_payment_succeeded(db, mock_pi)
    
    # 重新查询更新后的状态
    await db.refresh(payment)
    
    return success_response("模拟支付成功", {
        "payment_id": payment.uuid,
        "status": payment.status.value,
        "credits_amount": payment.credits_amount,
        "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
    })

