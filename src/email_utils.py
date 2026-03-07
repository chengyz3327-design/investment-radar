"""
邮件工具 - 发送验证码邮件
"""
import random
import string
import logging
from email.message import EmailMessage

import aiosmtplib

from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME

logger = logging.getLogger(__name__)


def generate_verify_code(length: int = 6) -> str:
    """生成纯数字验证码"""
    return "".join(random.choices(string.digits, k=length))


def smtp_configured() -> bool:
    """检查 SMTP 是否已配置"""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


async def send_verify_email(to_email: str, code: str) -> bool:
    """发送验证码邮件，返回是否成功"""
    if not smtp_configured():
        logger.warning("SMTP 未配置，跳过邮件发送 (验证码: %s -> %s)", code, to_email)
        return True  # 开发模式：未配置 SMTP 时直接返回成功

    msg = EmailMessage()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = f"【投资避雷】邮箱验证码: {code}"

    html_body = f"""
    <div style="max-width:480px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;padding:32px 24px;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px;">
        <span style="font-size:28px;">&#9889;</span>
        <h2 style="margin:8px 0 0;color:#1e293b;font-size:22px;">投资避雷</h2>
        <p style="color:#64748b;font-size:14px;margin:4px 0 0;">机构级量化风控引擎</p>
      </div>
      <div style="background:#fff;border-radius:8px;padding:24px;border:1px solid #e2e8f0;">
        <p style="color:#334155;font-size:15px;margin:0 0 16px;">您的邮箱验证码：</p>
        <div style="text-align:center;margin:20px 0;">
          <span style="display:inline-block;font-size:32px;font-weight:700;letter-spacing:8px;color:#3b82f6;background:#eff6ff;padding:12px 28px;border-radius:8px;border:2px dashed #93c5fd;">
            {code}
          </span>
        </div>
        <p style="color:#64748b;font-size:13px;margin:16px 0 0;text-align:center;">验证码 10 分钟内有效，请勿泄露给他人</p>
      </div>
      <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px;">如非本人操作，请忽略此邮件</p>
    </div>
    """

    msg.set_content(f"您的投资避雷邮箱验证码是：{code}（10分钟内有效）")
    msg.add_alternative(html_body, subtype="html")

    try:
        await _send_smtp(msg)
        logger.info("验证码邮件已发送: %s", to_email)
        return True
    except Exception as e:
        logger.error("邮件发送失败 (%s): %s", to_email, e)
        return False


async def send_reset_email(to_email: str, code: str) -> bool:
    """发送密码重置验证码邮件"""
    if not smtp_configured():
        logger.warning("SMTP 未配置，跳过邮件发送 (重置码: %s -> %s)", code, to_email)
        return True

    msg = EmailMessage()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = f"【投资避雷】密码重置验证码: {code}"

    html_body = f"""
    <div style="max-width:480px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fef2f2;padding:32px 24px;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px;">
        <span style="font-size:28px;">&#128274;</span>
        <h2 style="margin:8px 0 0;color:#1e293b;font-size:22px;">密码重置</h2>
        <p style="color:#64748b;font-size:14px;margin:4px 0 0;">投资避雷 - 安全中心</p>
      </div>
      <div style="background:#fff;border-radius:8px;padding:24px;border:1px solid #fecaca;">
        <p style="color:#334155;font-size:15px;margin:0 0 16px;">您正在重置密码，验证码：</p>
        <div style="text-align:center;margin:20px 0;">
          <span style="display:inline-block;font-size:32px;font-weight:700;letter-spacing:8px;color:#dc2626;background:#fef2f2;padding:12px 28px;border-radius:8px;border:2px dashed #fca5a5;">
            {code}
          </span>
        </div>
        <p style="color:#64748b;font-size:13px;margin:16px 0 0;text-align:center;">验证码 10 分钟内有效，请勿泄露给他人</p>
      </div>
      <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px;">如非本人操作，请检查账号安全</p>
    </div>
    """

    msg.set_content(f"您的投资避雷密码重置验证码是：{code}（10分钟内有效）")
    msg.add_alternative(html_body, subtype="html")

    try:
        await _send_smtp(msg)
        logger.info("重置密码邮件已发送: %s", to_email)
        return True
    except Exception as e:
        logger.error("邮件发送失败 (%s): %s", to_email, e)
        return False


async def _send_smtp(msg: EmailMessage):
    """发送邮件，自动选择 TLS 模式"""
    port = SMTP_PORT
    if port == 465:
        # 端口 465: 隐式 SSL/TLS
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=port,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=True,
            timeout=15,
        )
    else:
        # 端口 587 或其他: STARTTLS
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=port,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
            timeout=15,
        )
