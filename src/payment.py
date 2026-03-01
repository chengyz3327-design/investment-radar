"""
支付模块 - 支持支付宝/微信支付
"""
import hashlib
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta

from src.config import (
    PAYMENT_MODE,
    ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY, ALIPAY_PUBLIC_KEY, ALIPAY_NOTIFY_URL,
    WECHAT_APP_ID, WECHAT_MCH_ID, WECHAT_API_KEY, WECHAT_NOTIFY_URL,
)

logger = logging.getLogger(__name__)


def is_sandbox_mode() -> bool:
    """是否为沙盒/测试模式"""
    return PAYMENT_MODE != "production"


def is_payment_configured(method: str) -> bool:
    """检查支付方式是否已配置"""
    if method == "alipay":
        return bool(ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY)
    elif method == "wechat":
        return bool(WECHAT_APP_ID and WECHAT_MCH_ID and WECHAT_API_KEY)
    return False


def generate_order_no() -> str:
    """生成订单号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = uuid.uuid4().hex[:8].upper()
    return f"IR{timestamp}{random_part}"


def create_payment_request(
    order_no: str,
    amount: int,
    subject: str,
    method: str = "alipay",
) -> dict:
    """
    创建支付请求
    
    Args:
        order_no: 订单号
        amount: 金额（分）
        subject: 商品描述
        method: 支付方式 (alipay / wechat)
    
    Returns:
        支付信息字典，包含 qr_code / pay_url 等
    """
    if is_sandbox_mode():
        # 沙盒模式：返回模拟支付信息
        return {
            "success": True,
            "sandbox": True,
            "order_no": order_no,
            "method": method,
            "amount": amount,
            "amount_yuan": f"¥{amount / 100:.2f}",
            "subject": subject,
            "qr_code": None,  # 沙盒模式无二维码
            "pay_url": f"/payment/sandbox/{order_no}",  # 模拟支付页面
            "expire_time": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            "message": "沙盒模式：点击模拟支付完成订单",
        }
    
    # 生产模式：调用真实支付接口
    if method == "alipay":
        return _create_alipay_request(order_no, amount, subject)
    elif method == "wechat":
        return _create_wechat_request(order_no, amount, subject)
    else:
        return {"success": False, "error": "不支持的支付方式"}


def _create_alipay_request(order_no: str, amount: int, subject: str) -> dict:
    """创建支付宝支付请求"""
    if not is_payment_configured("alipay"):
        return {"success": False, "error": "支付宝未配置"}
    
    # TODO: 集成支付宝 SDK
    # 使用 alipay-sdk-python 或直接调用 API
    # 生成支付链接或二维码
    
    return {
        "success": False,
        "error": "支付宝接口待接入",
        "message": "请联系管理员配置支付宝商户信息",
    }


def _create_wechat_request(order_no: str, amount: int, subject: str) -> dict:
    """创建微信支付请求"""
    if not is_payment_configured("wechat"):
        return {"success": False, "error": "微信支付未配置"}
    
    # TODO: 集成微信支付 SDK
    # 使用 wechatpay-python 或直接调用 API
    # 生成支付二维码 (Native 支付)
    
    return {
        "success": False,
        "error": "微信支付接口待接入",
        "message": "请联系管理员配置微信支付商户信息",
    }


def verify_payment_callback(method: str, data: dict) -> dict:
    """
    验证支付回调
    
    Args:
        method: 支付方式
        data: 回调数据
    
    Returns:
        验证结果，包含 valid, order_no, trade_no, amount 等
    """
    if is_sandbox_mode():
        # 沙盒模式：简单验证
        return {
            "valid": True,
            "order_no": data.get("order_no"),
            "trade_no": data.get("trade_no", f"SANDBOX_{int(time.time())}"),
            "amount": data.get("amount", 0),
        }
    
    if method == "alipay":
        return _verify_alipay_callback(data)
    elif method == "wechat":
        return _verify_wechat_callback(data)
    
    return {"valid": False, "error": "不支持的支付方式"}


def _verify_alipay_callback(data: dict) -> dict:
    """验证支付宝回调签名"""
    # TODO: 实现支付宝签名验证
    return {"valid": False, "error": "支付宝验签待实现"}


def _verify_wechat_callback(data: dict) -> dict:
    """验证微信支付回调签名"""
    # TODO: 实现微信支付签名验证
    return {"valid": False, "error": "微信支付验签待实现"}


# VIP 套餐配置
VIP_PLANS = {
    "monthly": {
        "name": "月度会员",
        "price": 2900,  # ¥29
        "days": 30,
        "vip_level": 1,
    },
    "yearly": {
        "name": "年度会员",
        "price": 19900,  # ¥199
        "days": 365,
        "vip_level": 1,
    },
    "lifetime": {
        "name": "终身会员",
        "price": 39900,  # ¥399
        "days": 36500,  # ~100年
        "vip_level": 2,
    },
}


def get_plan_info(plan_type: str) -> dict:
    """获取套餐信息"""
    plan = VIP_PLANS.get(plan_type)
    if not plan:
        return None
    return {
        "plan_type": plan_type,
        "name": plan["name"],
        "price": plan["price"],
        "price_yuan": f"¥{plan['price'] / 100:.0f}",
        "days": plan["days"],
        "vip_level": plan["vip_level"],
    }
