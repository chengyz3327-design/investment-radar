"""
认证工具 - JWT / 密码哈希 / FastAPI 依赖注入
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS, TRIAL_DAYS
)
from src.models import User, get_db

# Bearer token 提取
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def compute_vip_status(user: User) -> dict:
    """根据用户数据计算 VIP 状态"""
    now = datetime.now(timezone.utc)

    # 试用期计算
    trial_end = user.trial_started_at.replace(tzinfo=timezone.utc) + timedelta(days=TRIAL_DAYS)
    is_trial = now < trial_end
    trial_days_left = max(0, (trial_end - now).days) if is_trial else 0

    # VIP 有效性
    if user.vip_level == 2:
        is_vip_active = True  # 终身会员
    elif user.vip_level == 1 and user.vip_expires_at:
        expires = user.vip_expires_at.replace(tzinfo=timezone.utc)
        is_vip_active = now < expires
    else:
        is_vip_active = False

    has_pro_access = is_vip_active or is_trial

    return {
        "has_pro_access": has_pro_access,
        "is_trial": is_trial and not is_vip_active,
        "trial_days_left": trial_days_left if not is_vip_active else -1,
        "is_vip_active": is_vip_active,
    }


def user_to_dict(user: User) -> dict:
    """将 User 对象转换为前端需要的字典"""
    vip_status = compute_vip_status(user)
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "vip_level": user.vip_level,
        "vip_expires_at": user.vip_expires_at.isoformat() if user.vip_expires_at else None,
        "created_at": user.created_at.isoformat(),
        "has_wechat": bool(user.wechat_openid),
        "has_github": bool(user.github_id),
        **vip_status,
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """强制认证：无有效 token 则 401"""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的登录凭证")
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """可选认证：无 token 或无效 token 返回 None"""
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        return None
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    return result.scalar_one_or_none()
