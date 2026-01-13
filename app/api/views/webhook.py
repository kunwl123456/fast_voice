"""Webhook 处理器"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.routers import webhook_router as router
from app.api.controller.subscription import handle_subscription_callback
from app.core.responses import success_response, error_response, CommonError


@router.post("/payment", summary="支付网关回调")
async def payment_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    is_success = await handle_subscription_callback(db, payload)
    await db.commit()
    if is_success:
        return success_response()
    else:
        return error_response(CommonError.INTERNAL_ERROR)
