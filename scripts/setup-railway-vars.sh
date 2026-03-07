#!/usr/bin/env bash
# ============================================================
# Railway SMTP 环境变量配置脚本
# 使用前请确保: railway login && railway link
# ============================================================
set -e

echo "=== 设置 Railway SMTP 环境变量 ==="

railway variables set SMTP_HOST="smtp.gmail.com"
railway variables set SMTP_PORT="587"
railway variables set SMTP_USER="chengyz3327@gmail.com"
railway variables set SMTP_PASSWORD="qdfscdyzqncehwcj"
railway variables set SMTP_FROM_NAME="投资避雷"
railway variables set PAYMENT_MODE="sandbox"

echo "=== 环境变量设置完成 ==="
echo ""
echo "验证变量:"
railway variables

echo ""
echo "触发重新部署:"
railway up --detach
