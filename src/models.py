"""
数据库模型 - User / Order
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, create_engine
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import DATABASE_URL, DATA_DIR

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    trial_started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    vip_level = Column(Integer, nullable=False, default=0)  # 0=普通, 1=PRO, 2=终身
    vip_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # 邮箱验证
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verify_code = Column(String(8), nullable=True)
    email_verify_code_at = Column(DateTime, nullable=True)

    # 密码重置
    reset_code = Column(String(8), nullable=True)
    reset_code_at = Column(DateTime, nullable=True)

    # OAuth 第三方登录绑定
    wechat_openid = Column(String(64), unique=True, nullable=True, index=True)
    wechat_unionid = Column(String(64), nullable=True)
    github_id = Column(String(64), unique=True, nullable=True, index=True)
    avatar_url = Column(String(512), nullable=True)

    orders = relationship("Order", back_populates="user", lazy="selectin")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_type = Column(String(20), nullable=False)  # monthly / yearly / lifetime
    amount = Column(Integer, nullable=False)  # 金额（分）
    status = Column(String(20), nullable=False, default="pending")  # pending/paid/failed/refunded
    payment_method = Column(String(20), nullable=True)  # wechat / alipay
    trade_no = Column(String(64), nullable=True)  # 第三方支付流水号
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")


class Favorite(Base):
    """用户收藏的股票"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="favorites")


class ScanHistory(Base):
    """用户扫描历史"""
    __tablename__ = "scan_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(64), nullable=True)
    total_score = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=True)
    scanned_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="scan_history")


# 异步引擎与会话
_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """初始化数据库（创建所有表）"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
