from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.error_codes import AccountError
from app.api.services.billing import recharge
from app.core.exceptions import NotFoundException


async def recharge_user_credits(
    db: AsyncSession, user_uuid: str, amount: int, note: str
) -> dict:
    """
    管理员为用户充值积分

    ### 参数
    - db: 数据库会话
    - user_uuid: 目标用户的 UUID
    - amount: 充值金额
    - note: 备注说明

    ### 返回
    - 充值结果字典

    ### 异常
    - NotFoundException: 用户不存在
    """
    recharge_user = (
        await db.execute(select(User).where(User.uuid == user_uuid))
    ).scalar_one_or_none()

    if not recharge_user:
        raise NotFoundException(error=AccountError.USER_NOT_FOUND)

    await recharge(db=db, user_id=recharge_user.id, amount=amount, note=note)

    return {"user_id": user_uuid, "amount": amount}
