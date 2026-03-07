#!/bin/bash
# Railway SMTP 环境变量配置脚本
# 用法: 先登录 Railway CLI (railway login)，然后运行此脚本
#
# 前提条件:
#   1. 安装 Railway CLI: npm install -g @railway/cli
#   2. 登录: railway login
#   3. 链接项目: railway link (选择 investment-radar 项目)
#   4. 运行: bash scripts/setup-railway-smtp.sh

set -e

echo "=== 投资避雷 - Railway SMTP 配置 ==="
echo ""

# Gmail SMTP 配置
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="465"
SMTP_USER="chengyz3327@gmail.com"
SMTP_PASSWORD="qdfscdyzqncehwcj"
SMTP_FROM_NAME="投资避雷"

echo "配置 SMTP_HOST=$SMTP_HOST"
railway variables set SMTP_HOST="$SMTP_HOST"

echo "配置 SMTP_PORT=$SMTP_PORT"
railway variables set SMTP_PORT="$SMTP_PORT"

echo "配置 SMTP_USER=$SMTP_USER"
railway variables set SMTP_USER="$SMTP_USER"

echo "配置 SMTP_PASSWORD=********"
railway variables set SMTP_PASSWORD="$SMTP_PASSWORD"

echo "配置 SMTP_FROM_NAME=$SMTP_FROM_NAME"
railway variables set SMTP_FROM_NAME="$SMTP_FROM_NAME"

echo ""
echo "=== 配置完成！Railway 将自动重新部署 ==="
echo "部署完成后，注册验证码邮件即可正常发送。"
