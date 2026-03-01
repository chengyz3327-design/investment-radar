"""
配置文件
"""
import os
import secrets
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"

# 数据库配置
DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR}/investment_radar.db"

# JWT 认证配置
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 168  # 7天

# 试用期配置
TRIAL_DAYS = 7

# 邮箱验证配置
EMAIL_VERIFY_CODE_EXPIRE_MINUTES = 10
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "投资避雷")

# 支付配置
PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "sandbox")  # sandbox / production

# 支付宝配置
ALIPAY_APP_ID = os.environ.get("ALIPAY_APP_ID", "")
ALIPAY_PRIVATE_KEY = os.environ.get("ALIPAY_PRIVATE_KEY", "")
ALIPAY_PUBLIC_KEY = os.environ.get("ALIPAY_PUBLIC_KEY", "")
ALIPAY_NOTIFY_URL = os.environ.get("ALIPAY_NOTIFY_URL", "")

# 微信支付配置
WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
WECHAT_MCH_ID = os.environ.get("WECHAT_MCH_ID", "")
WECHAT_API_KEY = os.environ.get("WECHAT_API_KEY", "")
WECHAT_NOTIFY_URL = os.environ.get("WECHAT_NOTIFY_URL", "")

# OAuth 第三方登录配置
# 微信开放平台 (网站应用)
WECHAT_OAUTH_APP_ID = os.environ.get("WECHAT_OAUTH_APP_ID", "")
WECHAT_OAUTH_APP_SECRET = os.environ.get("WECHAT_OAUTH_APP_SECRET", "")
WECHAT_OAUTH_REDIRECT_URI = os.environ.get("WECHAT_OAUTH_REDIRECT_URI", "")

# GitHub OAuth
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "")

# 风险评分权重配置
RISK_WEIGHTS = {
    # 财务风险 (45%)
    "continuous_loss": 0.18,           # 扣非净利润连续亏损
    "negative_cashflow": 0.12,         # 经营现金流持续为负
    "high_goodwill": 0.05,             # 商誉/净资产比例过高
    "audit_opinion": 0.05,             # 审计意见非标
    "receivables_growth": 0.05,        # 应收账款异常增长

    # 股权风险 (15%)
    "pledge_ratio": 0.10,              # 大股东质押比例
    "shareholder_reduce": 0.05,        # 股东减持

    # 合规风险 (15%)
    "st_status": 0.15,                 # ST/*ST状态

    # 市场风险 (10%)
    "price_drop": 0.10,                # 股价跌幅
}

# 风险阈值配置
RISK_THRESHOLDS = {
    "goodwill_ratio": 0.30,            # 商誉占净资产超过30%为高风险
    "pledge_ratio": 0.50,              # 质押比例超过50%为高风险
    "pledge_ratio_critical": 0.80,     # 质押比例超过80%为极高风险
    "receivables_growth": 0.50,        # 应收账款增长超过50%为异常
    "price_drop_warning": 30,          # 较高点跌幅超过30%为警惕
    "price_drop_danger": 50,           # 较高点跌幅超过50%为危险
}
