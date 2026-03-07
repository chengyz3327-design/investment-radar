"""
FastAPI 服务 - 投资避雷 API
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Depends, Request

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
import uvicorn

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data_fetcher import DataFetcher
from src.risk_scorer import RiskScorer
from src.models import init_db, get_db, User, Order, Favorite, ScanHistory
from src.payment import (
    is_sandbox_mode, generate_order_no, create_payment_request,
    verify_payment_callback, get_plan_info, VIP_PLANS,
    decrypt_wechat_callback, query_wechat_order,
)
from src.oauth import (
    get_available_oauth_providers, get_wechat_auth_url, get_github_auth_url,
    get_wechat_user_info, get_github_user_info,
    is_wechat_oauth_configured, is_github_oauth_configured,
)
from src.report_gen import generate_report_image, generate_report_base64
from src.stock_search import search_stocks as pinyin_search, get_hot_stocks
from src.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_optional_user, compute_vip_status, user_to_dict,
)
from src.email_utils import generate_verify_code, send_verify_email, send_reset_email, smtp_configured, smtp_test, email_configured
from src.config import EMAIL_VERIFY_CODE_EXPIRE_MINUTES, PAYMENT_MODE

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="投资避雷 API",
    description="股票风险扫描服务 - 避开雷区，守护本金",
    version="2.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 初始化服务
data_fetcher = DataFetcher()
risk_scorer = RiskScorer()


# ====================== Startup ======================

@app.on_event("startup")
async def on_startup():
    await init_db()


# ====================== Pydantic 模型 ======================

class ScanRequest(BaseModel):
    stock_code: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度至少6位")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateOrderRequest(BaseModel):
    plan_type: str  # monthly / yearly / lifetime
    payment_method: Optional[str] = "wechat"  # wechat / alipay


class SendVerifyCodeRequest(BaseModel):
    """可选：未登录时用邮箱发送（注册前验证场景暂不需要）"""
    pass


class VerifyEmailRequest(BaseModel):
    code: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_length(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度至少6位")
        return v


# ====================== 公开端点 ======================

@app.get("/")
async def root():
    """返回前端页面"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"name": "投资避雷 API", "version": "2.0.0"}


@app.get("/privacy")
async def privacy_page():
    """隐私政策页面"""
    f = STATIC_DIR / "privacy.html"
    if f.exists():
        return FileResponse(str(f))
    raise HTTPException(status_code=404)


@app.get("/terms")
async def terms_page():
    """用户协议页面"""
    f = STATIC_DIR / "terms.html"
    if f.exists():
        return FileResponse(str(f))
    raise HTTPException(status_code=404)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "investment-radar"}


@app.get("/debug/smtp")
async def debug_smtp():
    """SMTP 连接诊断"""
    return await smtp_test()


@app.get("/search")
async def search_stocks_api(q: str = "", limit: int = 10):
    """搜索股票 - 支持代码、名称、拼音模糊匹配"""
    q = q.strip()
    if not q:
        return {"results": get_hot_stocks()[:limit], "hot": True}
    try:
        stock_list = data_fetcher._get_stock_list()
        results = pinyin_search(q, stock_list, limit=min(limit, 20))
        return {"results": results, "hot": False}
    except Exception as e:
        return {"results": [], "error": str(e)}


# ====================== 认证端点 ======================

@app.post("/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    email = req.email.strip().lower()
    # 检查邮箱是否已注册
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    nickname = req.nickname or email.split("@")[0]
    now = datetime.now(timezone.utc)
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        nickname=nickname,
        created_at=now,
        trial_started_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_to_dict(user),
    }


@app.post("/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    email = req.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_to_dict(user),
    }


# ====================== 用户端点（需认证） ======================

@app.get("/user/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取用户资料和 VIP 状态"""
    return {"user": user_to_dict(current_user)}


@app.post("/user/orders")
async def create_order(
    req: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建支付订单"""
    plan = get_plan_info(req.plan_type)
    if not plan:
        raise HTTPException(status_code=400, detail="无效的套餐类型")

    order_no = generate_order_no()
    order = Order(
        user_id=current_user.id,
        plan_type=req.plan_type,
        amount=plan["price"],
        status="pending",
        trade_no=order_no,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 创建支付请求
    payment_method = req.payment_method or "wechat"
    payment = create_payment_request(
        order_no=order_no,
        amount=plan["price"],
        subject=f"投资避雷 - {plan['name']}",
        method=payment_method,
    )

    return {
        "order_id": order.id,
        "order_no": order_no,
        "plan": plan,
        "payment": payment,
        "sandbox": is_sandbox_mode(),
    }


@app.get("/user/orders")
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看订单历史"""
    result = await db.execute(
        select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return {
        "orders": [
            {
                "id": o.id,
                "plan_type": o.plan_type,
                "amount": o.amount,
                "status": o.status,
                "created_at": o.created_at.isoformat(),
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            }
            for o in orders
        ]
    }


@app.get("/user/orders/{order_no}")
async def get_order(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询订单状态"""
    result = await db.execute(
        select(Order).where(
            Order.trade_no == order_no,
            Order.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return {
        "order_id": order.id,
        "order_no": order.trade_no,
        "plan_type": order.plan_type,
        "amount": order.amount,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


@app.post("/payment/sandbox/{order_no}")
async def sandbox_payment(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """沙盒模式模拟支付（仅开发测试用）"""
    if not is_sandbox_mode():
        raise HTTPException(status_code=403, detail="生产环境不支持模拟支付")

    result = await db.execute(
        select(Order).where(
            Order.trade_no == order_no,
            Order.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == "paid":
        return {"message": "订单已支付", "status": "paid"}

    # 模拟支付成功，激活 VIP
    plan = get_plan_info(order.plan_type)
    if not plan:
        raise HTTPException(status_code=400, detail="套餐信息异常")

    now = datetime.now(timezone.utc)

    # 更新订单状态
    order.status = "paid"
    order.paid_at = now
    order.payment_method = "sandbox"

    # 激活 VIP
    current_user.vip_level = plan["vip_level"]
    if current_user.vip_expires_at and current_user.vip_expires_at > now:
        # 叠加时间
        current_user.vip_expires_at = current_user.vip_expires_at + timedelta(days=plan["days"])
    else:
        current_user.vip_expires_at = now + timedelta(days=plan["days"])

    await db.commit()

    return {
        "message": "支付成功，VIP 已激活！",
        "status": "paid",
        "vip_level": current_user.vip_level,
        "vip_expires_at": current_user.vip_expires_at.isoformat(),
        "user": user_to_dict(current_user),
    }


@app.get("/payment/plans")
async def list_plans():
    """获取所有套餐信息"""
    plans = []
    for plan_type, plan in VIP_PLANS.items():
        plans.append({
            "plan_type": plan_type,
            "name": plan["name"],
            "price": plan["price"],
            "price_yuan": f"¥{plan['price'] / 100:.0f}",
            "days": plan["days"],
        })
    return {"plans": plans, "sandbox": is_sandbox_mode()}


@app.post("/payment/wechat/notify")
async def wechat_payment_notify(request: Request, db: AsyncSession = Depends(get_db)):
    """微信支付回调通知"""
    headers = dict(request.headers)
    body = (await request.body()).decode("utf-8")

    result = decrypt_wechat_callback(headers, body)
    if not result.get("valid"):
        logger.warning(f"微信回调验证失败: {result.get('error')}")
        return {"code": "FAIL", "message": result.get("error", "验签失败")}

    order_no = result["order_no"]
    trade_no = result["trade_no"]

    # 查找订单
    stmt = select(Order).where(Order.trade_no == order_no)
    r = await db.execute(stmt)
    order = r.scalar_one_or_none()
    if not order:
        logger.error(f"微信回调: 订单不存在 {order_no}")
        return {"code": "SUCCESS", "message": "OK"}

    if order.status == "paid":
        return {"code": "SUCCESS", "message": "OK"}

    # 更新订单
    plan = get_plan_info(order.plan_type)
    if not plan:
        return {"code": "SUCCESS", "message": "OK"}

    now = datetime.now(timezone.utc)
    order.status = "paid"
    order.paid_at = now
    order.payment_method = "wechat"

    # 查找用户并激活 VIP
    user_r = await db.execute(select(User).where(User.id == order.user_id))
    user = user_r.scalar_one_or_none()
    if user:
        user.vip_level = plan["vip_level"]
        if user.vip_expires_at and user.vip_expires_at > now:
            user.vip_expires_at = user.vip_expires_at + timedelta(days=plan["days"])
        else:
            user.vip_expires_at = now + timedelta(days=plan["days"])

    await db.commit()
    logger.info(f"微信支付成功: order={order_no}, trade={trade_no}")
    return {"code": "SUCCESS", "message": "OK"}


@app.get("/payment/order-status/{order_no}")
async def check_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询订单支付状态（前端轮询用）"""
    result = await db.execute(
        select(Order).where(
            Order.trade_no == order_no,
            Order.user_id == current_user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == "paid":
        return {
            "status": "paid",
            "user": user_to_dict(current_user),
        }

    # 如果本地未支付，主动查询微信（生产模式）
    if not is_sandbox_mode() and order.payment_method != "sandbox":
        wx_result = query_wechat_order(order_no)
        if wx_result.get("success") and wx_result.get("trade_state") == "SUCCESS":
            plan = get_plan_info(order.plan_type)
            if plan:
                now = datetime.now(timezone.utc)
                order.status = "paid"
                order.paid_at = now
                order.payment_method = "wechat"
                current_user.vip_level = plan["vip_level"]
                if current_user.vip_expires_at and current_user.vip_expires_at > now:
                    current_user.vip_expires_at += timedelta(days=plan["days"])
                else:
                    current_user.vip_expires_at = now + timedelta(days=plan["days"])
                await db.commit()
                return {
                    "status": "paid",
                    "user": user_to_dict(current_user),
                }

    return {"status": order.status}


# ====================== 用户设置端点 ======================

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_length(cls, v):
        if len(v) < 6:
            raise ValueError("新密码长度至少6位")
        return v


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None


@app.post("/user/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    current_user.password_hash = hash_password(req.new_password)
    await db.commit()

    return {"message": "密码修改成功"}


@app.put("/user/profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户资料"""
    if req.nickname is not None:
        nickname = req.nickname.strip()
        if len(nickname) < 1:
            raise HTTPException(status_code=400, detail="昵称不能为空")
        if len(nickname) > 20:
            raise HTTPException(status_code=400, detail="昵称最长20个字符")
        current_user.nickname = nickname

    await db.commit()
    await db.refresh(current_user)

    return {"message": "资料已更新", "user": user_to_dict(current_user)}


# ====================== 邮箱验证端点 ======================

@app.post("/auth/send-verify-code")
async def send_verify_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送邮箱验证码（需登录）"""
    if current_user.email_verified:
        return {"message": "邮箱已验证", "already_verified": True}

    # 频率限制：60秒内不能重复发送
    now = datetime.now(timezone.utc)
    if current_user.email_verify_code_at:
        code_at = current_user.email_verify_code_at.replace(tzinfo=timezone.utc)
        if (now - code_at).total_seconds() < 60:
            raise HTTPException(status_code=429, detail="发送过于频繁，请 60 秒后再试")

    code = generate_verify_code()
    current_user.email_verify_code = code
    current_user.email_verify_code_at = now
    await db.commit()

    ok = await send_verify_email(current_user.email, code)
    if not ok:
        if PAYMENT_MODE == "sandbox":
            # 沙盒模式：邮件发送失败时直接返回验证码，方便测试
            return {
                "message": "邮件发送失败，沙盒模式下直接返回验证码",
                "code": code,
                "sandbox": True,
            }
        raise HTTPException(status_code=500, detail="邮件发送失败，请稍后重试")

    resp = {
        "message": "验证码已发送至 " + current_user.email,
        "smtp_configured": smtp_configured(),
    }
    if PAYMENT_MODE == "sandbox":
        resp["code"] = code
        resp["sandbox"] = True
    return resp


@app.post("/auth/verify-email")
async def verify_email(
    req: VerifyEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """验证邮箱验证码"""
    if current_user.email_verified:
        return {"message": "邮箱已验证", "user": user_to_dict(current_user)}

    if not current_user.email_verify_code or not current_user.email_verify_code_at:
        raise HTTPException(status_code=400, detail="请先发送验证码")

    # 检查过期
    now = datetime.now(timezone.utc)
    code_at = current_user.email_verify_code_at.replace(tzinfo=timezone.utc)
    if (now - code_at).total_seconds() > EMAIL_VERIFY_CODE_EXPIRE_MINUTES * 60:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新发送")

    # 检查验证码
    if req.code.strip() != current_user.email_verify_code:
        raise HTTPException(status_code=400, detail="验证码错误")

    current_user.email_verified = True
    current_user.email_verify_code = None
    current_user.email_verify_code_at = None
    await db.commit()
    await db.refresh(current_user)

    return {"message": "邮箱验证成功", "user": user_to_dict(current_user)}


# ====================== 密码重置端点 ======================

@app.post("/auth/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送密码重置验证码（无需登录）"""
    email = req.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # 无论用户是否存在都返回成功（防止邮箱枚举攻击）
    if not user:
        return {"message": "如果该邮箱已注册，验证码将发送至邮箱"}

    # 频率限制：60秒内不能重复发送
    now = datetime.now(timezone.utc)
    if user.reset_code_at:
        code_at = user.reset_code_at.replace(tzinfo=timezone.utc)
        if (now - code_at).total_seconds() < 60:
            raise HTTPException(status_code=429, detail="发送过于频繁，请 60 秒后再试")

    code = generate_verify_code()
    user.reset_code = code
    user.reset_code_at = now
    await db.commit()

    await send_reset_email(email, code)

    return {"message": "如果该邮箱已注册，验证码将发送至邮箱"}


@app.post("/auth/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """验证码重置密码"""
    email = req.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    if not user.reset_code or not user.reset_code_at:
        raise HTTPException(status_code=400, detail="请先发送验证码")

    # 检查过期
    now = datetime.now(timezone.utc)
    code_at = user.reset_code_at.replace(tzinfo=timezone.utc)
    if (now - code_at).total_seconds() > EMAIL_VERIFY_CODE_EXPIRE_MINUTES * 60:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新发送")

    # 检查验证码
    if req.code.strip() != user.reset_code:
        raise HTTPException(status_code=400, detail="验证码错误")

    # 重置密码
    user.password_hash = hash_password(req.new_password)
    user.reset_code = None
    user.reset_code_at = None
    await db.commit()

    return {"message": "密码重置成功，请使用新密码登录"}


# ====================== OAuth 第三方登录端点 ======================

@app.get("/auth/oauth/providers")
async def list_oauth_providers():
    """获取可用的第三方登录提供商"""
    return {"providers": get_available_oauth_providers()}


@app.get("/auth/oauth/{provider}/url")
async def get_oauth_url(provider: str, redirect: str = ""):
    """获取第三方登录授权 URL"""
    import secrets
    state = secrets.token_urlsafe(16)
    
    if provider == "wechat":
        if not is_wechat_oauth_configured():
            raise HTTPException(status_code=400, detail="微信登录未配置")
        url = get_wechat_auth_url(state)
    elif provider == "github":
        if not is_github_oauth_configured():
            raise HTTPException(status_code=400, detail="GitHub登录未配置")
        url = get_github_auth_url(state)
    else:
        raise HTTPException(status_code=400, detail="不支持的登录方式")
    
    return {"url": url, "state": state}


@app.post("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """处理第三方登录回调"""
    # 获取用户信息
    if provider == "wechat":
        user_info = await get_wechat_user_info(code)
        if "error" in user_info:
            raise HTTPException(status_code=400, detail=user_info["error"])
        openid_field = "wechat_openid"
        openid_value = user_info["openid"]
    elif provider == "github":
        user_info = await get_github_user_info(code)
        if "error" in user_info:
            raise HTTPException(status_code=400, detail=user_info["error"])
        openid_field = "github_id"
        openid_value = user_info["openid"]
    else:
        raise HTTPException(status_code=400, detail="不支持的登录方式")
    
    # 查找已绑定的用户
    result = await db.execute(
        select(User).where(getattr(User, openid_field) == openid_value)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # 已绑定用户，直接登录
        token = create_access_token(user.id)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user_to_dict(user),
            "is_new": False,
        }
    
    # 新用户，自动注册
    nickname = user_info.get("nickname", "")
    avatar = user_info.get("avatar", "")
    email = user_info.get("email", "")
    
    # 如果有邮箱，检查是否已存在
    if email:
        existing = await db.execute(select(User).where(User.email == email))
        existing_user = existing.scalar_one_or_none()
        if existing_user:
            # 邮箱已存在，绑定到现有账户
            setattr(existing_user, openid_field, openid_value)
            if avatar and not existing_user.avatar_url:
                existing_user.avatar_url = avatar
            await db.commit()
            token = create_access_token(existing_user.id)
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": user_to_dict(existing_user),
                "is_new": False,
                "bound": True,
            }
    
    # 创建新用户
    # 生成临时邮箱（如果没有）
    if not email:
        email = f"{provider}_{openid_value[:8]}@oauth.local"
    
    new_user = User(
        email=email,
        password_hash="",  # OAuth 用户无密码
        nickname=nickname or f"{provider}用户",
        avatar_url=avatar,
        email_verified=bool(user_info.get("email")),  # 如果有邮箱则视为已验证
    )
    setattr(new_user, openid_field, openid_value)
    if provider == "wechat" and user_info.get("unionid"):
        new_user.wechat_unionid = user_info["unionid"]
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    token = create_access_token(new_user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_to_dict(new_user),
        "is_new": True,
    }


# ====================== 收藏功能端点 ======================

class FavoriteRequest(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None


@app.get("/user/favorites")
async def list_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户收藏列表"""
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == current_user.id).order_by(Favorite.created_at.desc())
    )
    favorites = result.scalars().all()
    return {
        "favorites": [
            {
                "id": f.id,
                "stock_code": f.stock_code,
                "stock_name": f.stock_name,
                "created_at": f.created_at.isoformat(),
            }
            for f in favorites
        ]
    }


@app.post("/user/favorites")
async def add_favorite(
    req: FavoriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加收藏"""
    stock_code = req.stock_code.strip().zfill(6)
    # 检查是否已收藏
    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.stock_code == stock_code
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "已收藏", "already_exists": True}

    fav = Favorite(
        user_id=current_user.id,
        stock_code=stock_code,
        stock_name=req.stock_name,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)

    return {
        "message": "收藏成功",
        "favorite": {
            "id": fav.id,
            "stock_code": fav.stock_code,
            "stock_name": fav.stock_name,
            "created_at": fav.created_at.isoformat(),
        }
    }


@app.delete("/user/favorites/{stock_code}")
async def remove_favorite(
    stock_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消收藏"""
    stock_code = stock_code.strip().zfill(6)
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.stock_code == stock_code
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        return {"message": "未找到收藏"}

    await db.delete(fav)
    await db.commit()
    return {"message": "已取消收藏"}


# ====================== 扫描历史端点 ======================

@app.get("/user/scan-history")
async def list_scan_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    """获取用户扫描历史"""
    result = await db.execute(
        select(ScanHistory)
        .where(ScanHistory.user_id == current_user.id)
        .order_by(ScanHistory.scanned_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    return {
        "history": [
            {
                "id": h.id,
                "stock_code": h.stock_code,
                "stock_name": h.stock_name,
                "total_score": h.total_score,
                "risk_level": h.risk_level,
                "scanned_at": h.scanned_at.isoformat(),
            }
            for h in history
        ]
    }


@app.delete("/user/scan-history")
async def clear_scan_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空扫描历史"""
    await db.execute(
        ScanHistory.__table__.delete().where(ScanHistory.user_id == current_user.id)
    )
    await db.commit()
    return {"message": "历史已清空"}


# ====================== VIP 数据过滤 ======================

def filter_vip_data(report_dict: dict, has_pro_access: bool) -> dict:
    """非 PRO 用户：锁定 momentum 和 smart_money 数据"""
    if has_pro_access:
        return report_dict
    quant = report_dict.get("quant_analysis")
    if quant and isinstance(quant, dict):
        if "momentum" in quant:
            quant["momentum"] = {"locked": True}
        if "smart_money" in quant:
            quant["smart_money"] = {"locked": True}
    return report_dict


# ====================== 扫描端点（支持可选认证） ======================

@app.get("/scan/{stock_code}")
async def scan_stock(
    stock_code: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """扫描股票风险"""
    try:
        stock_code = stock_code.strip().zfill(6)
        data = data_fetcher.get_all_data(stock_code)

        if not data.get("basic_info") and not data.get("price_info"):
            raise HTTPException(
                status_code=404,
                detail=f"未找到股票 {stock_code}，请检查代码是否正确"
            )

        report = risk_scorer.calculate_risk(data)
        report_dict = report.to_dict()

        # VIP 过滤
        has_pro = False
        if current_user:
            vip_status = compute_vip_status(current_user)
            has_pro = vip_status["has_pro_access"]

            # 保存扫描历史
            history = ScanHistory(
                user_id=current_user.id,
                stock_code=stock_code,
                stock_name=report_dict.get("stock_name"),
                total_score=int(report_dict.get("total_score", 0)),
                risk_level=report_dict.get("risk_level"),
            )
            db.add(history)
            await db.commit()

        report_dict = filter_vip_data(report_dict, has_pro)

        return {"success": True, "data": report_dict}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan")
async def scan_stock_post(
    request: ScanRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """POST方式扫描股票"""
    return await scan_stock(request.stock_code, current_user, db)


@app.get("/batch-scan")
async def batch_scan(
    codes: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """批量扫描股票"""
    code_list = [c.strip().zfill(6) for c in codes.split(",") if c.strip()]

    if len(code_list) > 10:
        raise HTTPException(status_code=400, detail="单次最多扫描10只股票")

    has_pro = False
    if current_user:
        vip_status = compute_vip_status(current_user)
        has_pro = vip_status["has_pro_access"]

    results = []
    for code in code_list:
        try:
            data = data_fetcher.get_all_data(code)
            if data.get("basic_info") or data.get("price_info"):
                report = risk_scorer.calculate_risk(data)
                report_dict = filter_vip_data(report.to_dict(), has_pro)
                results.append({"code": code, "success": True, "data": report_dict})

                # 保存扫描历史
                if current_user:
                    history = ScanHistory(
                        user_id=current_user.id,
                        stock_code=code,
                        stock_name=report_dict.get("stock_name"),
                        total_score=int(report_dict.get("total_score", 0)),
                        risk_level=report_dict.get("risk_level"),
                    )
                    db.add(history)
            else:
                results.append({"code": code, "success": False, "error": "未找到股票"})
        except Exception as e:
            results.append({"code": code, "success": False, "error": str(e)})

    if current_user:
        await db.commit()

    return {"success": True, "results": results}


# ====================== 报告导出端点 ======================

@app.get("/report/{stock_code}/image")
async def get_report_image(
    stock_code: str,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """生成扫描报告图片"""
    try:
        stock_code = stock_code.strip().zfill(6)
        data = data_fetcher.get_all_data(stock_code)

        if not data.get("basic_info") and not data.get("price_info"):
            raise HTTPException(status_code=404, detail=f"未找到股票 {stock_code}")

        report = risk_scorer.calculate_risk(data)
        report_dict = report.to_dict()

        # 生成图片
        img_bytes = generate_report_image(report_dict)

        return Response(
            content=img_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="report_{stock_code}.png"',
                "Cache-Control": "max-age=300",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/{stock_code}/base64")
async def get_report_base64(
    stock_code: str,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """生成扫描报告图片 (Base64)"""
    try:
        stock_code = stock_code.strip().zfill(6)
        data = data_fetcher.get_all_data(stock_code)

        if not data.get("basic_info") and not data.get("price_info"):
            raise HTTPException(status_code=404, detail=f"未找到股票 {stock_code}")

        report = risk_scorer.calculate_risk(data)
        report_dict = report.to_dict()

        # 生成图片 Base64
        img_base64 = generate_report_base64(report_dict)

        return {
            "success": True,
            "stock_code": stock_code,
            "stock_name": report_dict.get("stock_name"),
            "image": f"data:image/png;base64,{img_base64}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
