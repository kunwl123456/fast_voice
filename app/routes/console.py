from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_admin, require_console_user
from app.models import ApiKey, CreditTransaction, Project, User
from app.services.billing import get_or_create_account, recharge
from app.services.bootstrap import ensure_user_default_project
from app.core.security import (
    create_access_token,
    encrypt_api_secret,
    generate_api_key,
    generate_api_secret,
    hash_password,
    verify_password
)
from app.schemas import (
    ApiKeyOut,
    ChangePasswordIn,
    CreditAccountOut,
    CreditTxOut,
    LoginIn,
    MeOut,
    RechargeIn,
    RegisterIn,
    RenameIn,
    TokenOut,
)

router = APIRouter(prefix="/console", tags=["console"])


@router.post("/auth/register", response_model=MeOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    existed = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existed:
        raise HTTPException(status_code=409, detail="email_exists")
    u = User(email=payload.email, password_hash=hash_password(payload.password), display_name=payload.display_name)
    db.add(u)
    await db.flush()
    await ensure_user_default_project(db, u)
    return MeOut(id=u.id, email=u.email, display_name=u.display_name, is_admin=u.is_admin)


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    u = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(subject=f"user:{u.id}")
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(require_console_user)):
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin)


@router.post("/me/rename", response_model=MeOut)
async def rename(payload: RenameIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    user.display_name = payload.display_name
    db.add(user)
    await db.flush()
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin)


@router.post("/me/change-password")
async def change_password(payload: ChangePasswordIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="wrong_old_password")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    return {"ok": True}


async def _default_project(db: AsyncSession, user: User) -> Project:
    return await ensure_user_default_project(db, user)


@router.post("/projects/default/api-keys/rotate", response_model=ApiKeyOut)
async def rotate_api_key(db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    proj = await _default_project(db, user)
    secret = generate_api_secret()
    api = ApiKey(
        project_id=proj.id,
        api_key=generate_api_key(),
        api_secret_ciphertext=encrypt_api_secret(secret),
        is_active=True,
    )
    db.add(api)
    await db.flush()
    # V1：为了简化，直接把该项目除最新外全禁用
    keys = (await db.execute(select(ApiKey).where(ApiKey.project_id == proj.id))).scalars().all()
    for k in keys:
        if k.id != api.id:
            k.is_active = False
            db.add(k)
    return ApiKeyOut(api_key=api.api_key, api_secret=secret)


@router.get("/projects/default/credits", response_model=CreditAccountOut)
async def credits(db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    proj = await _default_project(db, user)
    acc = await get_or_create_account(db, proj.id)
    return CreditAccountOut(project_id=proj.id, balance=acc.balance)


@router.get("/projects/default/credits/transactions", response_model=list[CreditTxOut])
async def credit_transactions(db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    proj = await _default_project(db, user)
    acc = await get_or_create_account(db, proj.id)
    txs = (await db.execute(
        select(CreditTransaction).where(CreditTransaction.account_id == acc.id).order_by(desc(CreditTransaction.id)).limit(200)
    )).scalars().all()
    return [
        CreditTxOut(
            id=t.id,
            tx_type=t.tx_type.value,
            amount=t.amount,
            ref_type=t.ref_type,
            ref_id=t.ref_id,
            note=t.note,
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]


@router.post("/admin/credits/recharge")
async def recharge_credits(payload: RechargeIn, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    await recharge(db=db, project_id=payload.project_id, amount=payload.amount, note=payload.note)
    return {"ok": True}


