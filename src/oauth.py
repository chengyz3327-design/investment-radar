"""
OAuth 第三方登录模块
支持: 微信、GitHub
"""
import httpx
import logging
from urllib.parse import urlencode

from src.config import (
    WECHAT_OAUTH_APP_ID, WECHAT_OAUTH_APP_SECRET, WECHAT_OAUTH_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI,
)

logger = logging.getLogger(__name__)


def is_wechat_oauth_configured() -> bool:
    """检查微信 OAuth 是否已配置"""
    return bool(WECHAT_OAUTH_APP_ID and WECHAT_OAUTH_APP_SECRET)


def is_github_oauth_configured() -> bool:
    """检查 GitHub OAuth 是否已配置"""
    return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)


def get_wechat_auth_url(state: str = "") -> str:
    """
    获取微信授权页面 URL
    
    Args:
        state: 状态参数，用于防止 CSRF
    
    Returns:
        授权页面 URL
    """
    if not is_wechat_oauth_configured():
        return ""
    
    params = {
        "appid": WECHAT_OAUTH_APP_ID,
        "redirect_uri": WECHAT_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    return f"https://open.weixin.qq.com/connect/qrconnect?{urlencode(params)}#wechat_redirect"


async def get_wechat_user_info(code: str) -> dict:
    """
    使用授权码获取微信用户信息
    
    Args:
        code: 微信返回的授权码
    
    Returns:
        用户信息字典，包含 openid, nickname, headimgurl 等
    """
    if not is_wechat_oauth_configured():
        return {"error": "微信登录未配置"}
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. 获取 access_token
            token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
            token_params = {
                "appid": WECHAT_OAUTH_APP_ID,
                "secret": WECHAT_OAUTH_APP_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }
            token_resp = await client.get(token_url, params=token_params)
            token_data = token_resp.json()
            
            if "errcode" in token_data:
                logger.error("微信获取token失败: %s", token_data)
                return {"error": token_data.get("errmsg", "获取token失败")}
            
            access_token = token_data["access_token"]
            openid = token_data["openid"]
            
            # 2. 获取用户信息
            userinfo_url = "https://api.weixin.qq.com/sns/userinfo"
            userinfo_params = {
                "access_token": access_token,
                "openid": openid,
            }
            userinfo_resp = await client.get(userinfo_url, params=userinfo_params)
            userinfo = userinfo_resp.json()
            
            if "errcode" in userinfo:
                logger.error("微信获取用户信息失败: %s", userinfo)
                return {"error": userinfo.get("errmsg", "获取用户信息失败")}
            
            return {
                "provider": "wechat",
                "openid": openid,
                "unionid": userinfo.get("unionid"),
                "nickname": userinfo.get("nickname", ""),
                "avatar": userinfo.get("headimgurl", ""),
                "sex": userinfo.get("sex", 0),  # 0:未知 1:男 2:女
            }
    except Exception as e:
        logger.error("微信OAuth异常: %s", e)
        return {"error": str(e)}


def get_github_auth_url(state: str = "") -> str:
    """
    获取 GitHub 授权页面 URL
    """
    if not is_github_oauth_configured():
        return ""
    
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def get_github_user_info(code: str) -> dict:
    """
    使用授权码获取 GitHub 用户信息
    """
    if not is_github_oauth_configured():
        return {"error": "GitHub登录未配置"}
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. 获取 access_token
            token_url = "https://github.com/login/oauth/access_token"
            token_data = {
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            }
            token_resp = await client.post(
                token_url, 
                data=token_data,
                headers={"Accept": "application/json"}
            )
            token_json = token_resp.json()
            
            if "error" in token_json:
                return {"error": token_json.get("error_description", "获取token失败")}
            
            access_token = token_json["access_token"]
            
            # 2. 获取用户信息
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
            )
            user_data = user_resp.json()
            
            # 3. 获取邮箱
            email = user_data.get("email")
            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    }
                )
                emails = emails_resp.json()
                for e in emails:
                    if e.get("primary"):
                        email = e.get("email")
                        break
            
            return {
                "provider": "github",
                "openid": str(user_data["id"]),
                "nickname": user_data.get("name") or user_data.get("login", ""),
                "avatar": user_data.get("avatar_url", ""),
                "email": email,
            }
    except Exception as e:
        logger.error("GitHub OAuth异常: %s", e)
        return {"error": str(e)}


def get_available_oauth_providers() -> list:
    """获取已配置的 OAuth 提供商列表"""
    providers = []
    if is_wechat_oauth_configured():
        providers.append({"id": "wechat", "name": "微信登录"})
    if is_github_oauth_configured():
        providers.append({"id": "github", "name": "GitHub"})
    return providers
