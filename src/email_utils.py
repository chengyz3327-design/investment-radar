"""
邮件工具 - 发送验证码邮件
支持 Resend HTTP API（推荐）和 SMTP 两种方式
"""
import random
import string
import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from src.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME,
    RESEND_API_KEY,
)

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def generate_verify_code(length: int = 6) -> str:
    """生成纯数字验证码"""
    return "".join(random.choices(string.digits, k=length))


def smtp_configured() -> bool:
    """检查 SMTP 是否已配置"""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def resend_configured() -> bool:
    """检查 Resend API 是否已配置"""
    return bool(RESEND_API_KEY)


def email_configured() -> bool:
    """检查是否有任何邮件发送方式已配置"""
    return resend_configured() or smtp_configured()


async def send_verify_email(to_email: str, code: str) -> bool:
    """发送验证码邮件，返回是否成功"""
    if not email_configured():
        logger.warning("邮件未配置，跳过发送 (验证码: %s -> %s)", code, to_email)
        return True  # 开发模式：未配置时直接返回成功

    subject = f"【投资避雷】邮箱验证码: {code}"
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
    text_body = f"您的投资避雷邮箱验证码是：{code}（10分钟内有效）"

    try:
        await _send_email(to_email, subject, html_body, text_body)
        logger.info("验证码邮件已发送: %s", to_email)
        return True
    except Exception as e:
        logger.error("邮件发送失败 (%s): %s", to_email, e)
        return False


async def send_reset_email(to_email: str, code: str) -> bool:
    """发送密码重置验证码邮件"""
    if not email_configured():
        logger.warning("邮件未配置，跳过发送 (重置码: %s -> %s)", code, to_email)
        return True

    subject = f"【投资避雷】密码重置验证码: {code}"
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
    text_body = f"您的投资避雷密码重置验证码是：{code}（10分钟内有效）"

    try:
        await _send_email(to_email, subject, html_body, text_body)
        logger.info("重置密码邮件已发送: %s", to_email)
        return True
    except Exception as e:
        logger.error("邮件发送失败 (%s): %s", to_email, e)
        return False


# ====================== 发送后端 ======================

async def _send_email(to: str, subject: str, html: str, text: str):
    """统一发送入口：优先 Resend HTTP API，回退 SMTP"""
    if resend_configured():
        await _send_resend(to, subject, html, text)
    elif smtp_configured():
        msg = EmailMessage()
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        await _send_smtp(msg)
    else:
        raise RuntimeError("无可用的邮件发送配置")


async def _send_resend(to: str, subject: str, html: str, text: str):
    """通过 Resend HTTP API 发送邮件"""
    from_addr = SMTP_USER if SMTP_USER else "onboarding@resend.dev"
    payload = {
        "from": f"{SMTP_FROM_NAME} <{from_addr}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    logger.info("Resend 发送: to=%s, from=%s", to, from_addr)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.error("Resend API 错误: %d %s", resp.status_code, resp.text)
            resp.raise_for_status()
    logger.info("Resend 发送成功")


async def _send_smtp(msg: EmailMessage):
    """发送邮件，自动选择 TLS 模式，465 失败自动回退 587"""
    port = SMTP_PORT
    logger.info("SMTP 发送: host=%s, port=%d, user=%s", SMTP_HOST, port, SMTP_USER)

    # 尝试顺序：配置端口优先，失败则回退另一个端口
    ports_to_try = [port]
    if port == 465:
        ports_to_try.append(587)
    elif port == 587:
        ports_to_try.append(465)

    last_error = None
    for p in ports_to_try:
        try:
            if p == 465:
                await aiosmtplib.send(
                    msg,
                    hostname=SMTP_HOST,
                    port=p,
                    username=SMTP_USER,
                    password=SMTP_PASSWORD,
                    use_tls=True,
                    timeout=10,
                )
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=SMTP_HOST,
                    port=p,
                    username=SMTP_USER,
                    password=SMTP_PASSWORD,
                    start_tls=True,
                    timeout=10,
                )
            logger.info("SMTP 发送成功 (port=%d)", p)
            return
        except Exception as e:
            last_error = e
            logger.warning("SMTP port %d 失败: %s: %s", p, type(e).__name__, e)

    logger.error("SMTP 所有端口均失败")
    raise last_error


async def smtp_test() -> dict:
    """邮件发送诊断"""
    import asyncio
    result = {
        "resend_configured": resend_configured(),
        "smtp_configured": smtp_configured(),
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_user": SMTP_USER[:4] + "****" if SMTP_USER else "",
    }

    # 优先测试 Resend
    if resend_configured():
        result["resend_key"] = RESEND_API_KEY[:8] + "****"
        result["status"] = "resend_ready"
        return result

    if not smtp_configured():
        result["status"] = "not_configured"
        return result

    # 测试 SMTP 两个端口
    for p in [587, 465]:
        try:
            smtp = aiosmtplib.SMTP(
                hostname=SMTP_HOST,
                port=p,
                start_tls=p != 465,
                use_tls=p == 465,
                timeout=10,
            )
            await smtp.connect()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.quit()
            result["status"] = "smtp_ok"
            result["working_port"] = p
            return result
        except asyncio.TimeoutError:
            result[f"port_{p}"] = "timeout"
        except Exception as e:
            result[f"port_{p}"] = f"{type(e).__name__}: {e}"

    result["status"] = "smtp_all_failed"
    result["hint"] = "SMTP 端口被屏蔽，请配置 RESEND_API_KEY 使用 HTTP 发送"
    return result
