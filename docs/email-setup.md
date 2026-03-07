# 邮件发送配置指南

投资避雷支持两种邮件发送方式，按优先级自动选择：

1. **Resend HTTP API**（推荐） - 适用于 Railway 等屏蔽 SMTP 端口的云平台
2. **SMTP** - 适用于允许 SMTP 出站连接的环境

## 方式一：Resend HTTP API（推荐）

Railway 等 PaaS 平台屏蔽了 SMTP 端口（465/587），必须使用 HTTP API 发送邮件。

### 步骤

1. 访问 https://resend.com/signup 注册账号（支持 GitHub 登录）
2. 进入 https://resend.com/api-keys ，点击 "Create API Key"
3. 复制生成的 key（格式：`re_xxxxxxxx`）
4. 在 Railway 控制台的 Variables 中添加：

```
RESEND_API_KEY=re_your_key_here
```

### 发送域名配置（可选）

默认使用 `onboarding@resend.dev` 测试域名发送。如需使用自定义域名：

1. 进入 https://resend.com/domains
2. 添加域名并按提示配置 DNS（SPF、DKIM、DMARC）
3. 同时设置 `SMTP_USER` 为你的发件地址，代码会自动使用它作为 From 地址

### 免费额度

- 100 封/天，3000 封/月
- 足够中小应用的验证码场景

## 方式二：SMTP

适用于本地开发或允许 SMTP 出站的服务器。

### Gmail SMTP

1. 开启两步验证：https://myaccount.google.com/security
2. 生成应用专用密码：https://myaccount.google.com/apppasswords
3. 设置环境变量：

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_FROM_NAME=投资避雷
```

### QQ / 网易邮箱

```
# QQ邮箱
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your-qq@qq.com
SMTP_PASSWORD=your-authorization-code

# 网易邮箱
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=your-email@163.com
SMTP_PASSWORD=your-authorization-code
```

## 诊断

部署后访问 `/debug/smtp` 端点可查看当前邮件配置状态：

```bash
curl https://your-domain.up.railway.app/debug/smtp
```

返回示例：
```json
{
  "resend_configured": true,
  "status": "resend_ready"
}
```

## 优先级逻辑

代码自动按以下顺序选择发送方式：

1. 如果 `RESEND_API_KEY` 已设置 -> 使用 Resend HTTP API
2. 如果 SMTP 已配置 -> 尝试 SMTP（自动在 465/587 端口间回退）
3. 都未配置 -> 开发模式，跳过发送并返回成功
