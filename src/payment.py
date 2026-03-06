"""
支付模块 - 支持支付宝/微信支付
"""
import json
import hashlib
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta

from src.config import (
    PAYMENT_MODE,
    ALIPAY_APP_ID, ALIPAY_PRIVATE_KEY, ALIPAY_PUBLIC_KEY, ALIPAY_NOTIFY_URL,
    WECHAT_APP_ID, WECHAT_MCH_ID, WECHAT_API_KEY, WECHAT_NOTIFY_URL,
    WECHAT_CERT_SERIAL_NO, WECHAT_APIV3_KEY, WECHAT_PRIVATE_KEY,
)

logger = logging.getLogger(__name__)

# ---- 微信支付 V3 实例（延迟初始化） ----
_wxpay = None


def _get_wxpay():
    """获取微信支付实例（单例）"""
    global _wxpay
    if _wxpay is not None:
        return _wxpay
    if not is_payment_configured("wechat"):
        return None
    try:
        from wechatpayv3 import WeChatPay, WeChatPayType
        _wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=WECHAT_MCH_ID,
            private_key=WECHAT_PRIVATE_KEY,
            cert_serial_no=WECHAT_CERT_SERIAL_NO,
            apiv3_key=WECHAT_APIV3_KEY,
            appid=WECHAT_APP_ID,
            notify_url=WECHAT_NOTIFY_URL,
        )
        logger.info("微信支付 V3 SDK 初始化成功")
        return _wxpay
    except Exception as e:
        logger.error(f"微信支付 SDK 初始化失败: {e}")
        return None


def is_sandbox_mode() -> bool:
    """是否为沙盒/测试模式"""
    return PAYMENT_MODE != "production"


def is_payment_configured(method: str) -> bool:
    """检查支付方式是否已配置"""
    if method == "alipay":
        return bool(ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY)
    elif method == "wechat":
        return bool(
            WECHAT_APP_ID and WECHAT_MCH_ID
            and WECHAT_PRIVATE_KEY and WECHAT_CERT_SERIAL_NO
            and WECHAT_APIV3_KEY
        )
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
    return {
        "success": False,
        "error": "支付宝接口待接入",
        "message": "请联系管理员配置支付宝商户信息",
    }


def _create_wechat_request(order_no: str, amount: int, subject: str) -> dict:
    """创建微信支付请求（Native 扫码支付）"""
    wxpay = _get_wxpay()
    if not wxpay:
        return {
            "success": False,
            "error": "微信支付未配置",
            "message": "请配置微信支付商户信息后重试",
        }

    try:
        code, message = wxpay.pay(
            description=subject,
            out_trade_no=order_no,
            amount={"total": amount, "currency": "CNY"},
        )
        result = json.loads(message)
        if code == 200 and "code_url" in result:
            return {
                "success": True,
                "sandbox": False,
                "order_no": order_no,
                "method": "wechat",
                "amount": amount,
                "amount_yuan": f"¥{amount / 100:.2f}",
                "subject": subject,
                "code_url": result["code_url"],
                "expire_time": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            }
        else:
            logger.error(f"微信支付下单失败: code={code}, message={message}")
            return {
                "success": False,
                "error": "微信支付下单失败",
                "message": result.get("message", "请稍后重试"),
            }
    except Exception as e:
        logger.error(f"微信支付异常: {e}")
        return {
            "success": False,
            "error": "微信支付异常",
            "message": str(e),
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


def decrypt_wechat_callback(headers: dict, body: str) -> dict:
    """
    解密微信支付回调通知

    Args:
        headers: HTTP 请求头（包含签名信息）
        body: HTTP 请求体原始字符串

    Returns:
        解密后的通知数据，或错误信息
    """
    wxpay = _get_wxpay()
    if not wxpay:
        return {"valid": False, "error": "微信支付未初始化"}

    try:
        result = wxpay.decrypt_callback(headers, body)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            trade_state = data.get("trade_state", "")
            if trade_state == "SUCCESS":
                return {
                    "valid": True,
                    "order_no": data.get("out_trade_no"),
                    "trade_no": data.get("transaction_id"),
                    "amount": data.get("amount", {}).get("total", 0),
                }
            else:
                return {
                    "valid": False,
                    "error": f"交易状态: {trade_state}",
                    "order_no": data.get("out_trade_no"),
                }
        return {"valid": False, "error": "回调解密失败"}
    except Exception as e:
        logger.error(f"微信回调解密异常: {e}")
        return {"valid": False, "error": str(e)}


def _verify_wechat_callback(data: dict) -> dict:
    """验证微信支付回调（旧接口兼容）"""
    return {"valid": False, "error": "请使用 decrypt_wechat_callback"}


def query_wechat_order(order_no: str) -> dict:
    """
    主动查询微信支付订单状态

    Args:
        order_no: 商户订单号

    Returns:
        订单状态信息
    """
    wxpay = _get_wxpay()
    if not wxpay:
        return {"success": False, "error": "微信支付未初始化"}

    try:
        code, message = wxpay.query(out_trade_no=order_no)
        if code == 200:
            data = json.loads(message)
            return {
                "success": True,
                "trade_state": data.get("trade_state"),
                "order_no": data.get("out_trade_no"),
                "trade_no": data.get("transaction_id"),
                "amount": data.get("amount", {}).get("total", 0),
            }
        return {"success": False, "error": f"查询失败: {message}"}
    except Exception as e:
        logger.error(f"微信订单查询异常: {e}")
        return {"success": False, "error": str(e)}


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
