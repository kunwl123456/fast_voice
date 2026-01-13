from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.deps import require_console, get_db
from app.core.responses import success_response
from app.routers import orders_router as router
from app.api.controller.orders import (
    create_refund as create_refund_controller,
    cancel_order as cancel_order_controller,
)
from app.core.schemas import (
    Response,
    CreateRefundIn,
    OrderDetailOut,
    RefundOut,
)

# @router.post(
#     "/create",
#     summary="创建订单",
#     response_model=Response[CreateOrderOut],
# )
# async def create_order(
#     payload: CreateOrderIn,
#     user: User = Depends(require_console),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     创建业务订单
#
#     ### 功能说明
#     - 创建积分充值或订阅购买订单
#     - 返回支付所需的信息（client_secret 等，视支付渠道而定）
#
#     ### 订单类型
#
#     1. **积分充值** (credit_recharge)
#        - product_id: 积分包商品编码（字符串：credit_1000, credit_5000, credit_10000, credit_50000, credit_100000）
#        - quantity: 购买份数（默认1）
#
#     2. **订阅购买** (subscription)
#        - product_id: 订阅计划代码（字符串：pro, enterprise）
#        - quantity: 订阅月数（1-12）
#
#     ### 请求示例
#
#     **积分充值：**
#     ```json
#     {
#       "order_type": "credit_recharge",
#       "product_id": "credit_10000",
#       "quantity": 1,
#       "payment_method": "stripe"
#     }
#     ```
#
#     **订阅购买：**
#     ```json
#     {
#       "order_type": "subscription",
#       "product_id": "pro",
#       "quantity": 3,
#       "payment_method": "wechatpay"
#     }
#     ```
#
#     ### 支付流程
#     1. 调用此接口创建订单
#     2. 使用返回的 `client_secret` 和 `publishable_key` 初始化 Stripe.js
#     3. 调用 `stripe.confirmPayment()` 完成支付
#     4. 轮询 `GET /console/orders/{order_id}` 等待订单状态变为 `fulfilled`
#     """
#     result = await create_order_controller(db, user, payload)
#     return success_response("创建订单成功", result.model_dump())


@router.post(
    "/{order_id}/cancel",
    summary="取消订单",
    response_model=Response[OrderDetailOut],
)
async def cancel_order(
    order_id: str,
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    取消订单

    ### 功能说明
    - 取消待支付的订单
    - 只有 `pending` 状态的订单可以取消
    - 已支付的订单请使用退款接口

    ### 注意事项
    - 取消后订单状态变为 `cancelled`
    - 取消操作不可逆
    """
    result = await cancel_order_controller(db, user, order_id)
    return success_response("取消成功", result.model_dump())


@router.post(
    "/refund",
    summary="创建退款",
    response_model=Response[RefundOut],
)
async def create_refund(
    payload: CreateRefundIn,
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    创建退款

    ### 功能说明
    - 对已支付或已完成的订单发起退款
    - 支持全额退款和部分退款
    - 退款会调用支付网关接口处理

    ### 订单状态要求
    - 只有 `paid`（已支付）或 `fulfilled`（已完成）状态的订单可以退款
    - `pending`（待支付）状态的订单请使用取消订单接口

    ### 请求示例

    **全额退款：**
    ```json
    {
      "order_id": "550e8400-e29b-41d4-a716-446655440000",
      "reason": "用户申请退款"
    }
    ```

    **部分退款：**
    ```json
    {
      "order_id": "550e8400-e29b-41d4-a716-446655440000",
      "refund_amount": 500,
      "reason": "部分退款"
    }
    ```

    ### 注意事项
    - 退款金额单位为最小货币单位（如：USD为分，1美元 = 100分）
    - 退款金额不能超过订单金额
    - 退款成功后订单状态变为 `refunded`
    - 退款操作不可逆
    - 实际到账时间取决于支付渠道（通常3-7个工作日）
    """
    result = await create_refund_controller(db, user, payload)
    return success_response("退款申请成功", result.model_dump())
