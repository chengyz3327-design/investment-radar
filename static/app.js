/* ============ 投资避雷 - 前端逻辑 ============ */

const API_BASE = "";
let _fromBatch = false; // 记录是否从批量扫描进入

// ---- 认证状态管理 ----
let _authState = {
  token: localStorage.getItem("auth_token") || null,
  user: null,
  loaded: false,
};

/** 带认证的 fetch 封装 */
async function apiFetch(url, opts = {}) {
  const headers = opts.headers || {};
  if (_authState.token) {
    headers["Authorization"] = "Bearer " + _authState.token;
  }
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  opts.headers = headers;
  return fetch(url, opts);
}

/** 初始化认证 — 页面加载时调用 */
async function initAuth() {
  updateNavUser();
  if (!_authState.token) { _authState.loaded = true; return; }
  try {
    const resp = await apiFetch(`${API_BASE}/user/profile`);
    if (resp.ok) {
      const json = await resp.json();
      _authState.user = json.user;
      // 加载服务端数据
      loadServerFavorites();
      loadServerHistory();
    } else {
      // token 无效，清除
      _authState.token = null;
      localStorage.removeItem("auth_token");
    }
  } catch (_) {
    _authState.token = null;
    localStorage.removeItem("auth_token");
  }
  _authState.loaded = true;
  updateNavUser();
}

/** 更新导航栏用户区域 */
function updateNavUser() {
  const loginBtn = document.getElementById("nav-login-btn");
  const userInfo = document.getElementById("nav-user-info");
  if (!loginBtn || !userInfo) return;

  if (_authState.user) {
    loginBtn.style.display = "none";
    userInfo.style.display = "flex";
    // 头像
    const avatar = document.getElementById("nav-avatar");
    if (avatar) avatar.textContent = (_authState.user.nickname || "U").charAt(0).toUpperCase();
    // 菜单信息
    const nn = document.getElementById("menu-nickname");
    const em = document.getElementById("menu-email");
    if (nn) nn.textContent = _authState.user.nickname || "";
    if (em) em.textContent = _authState.user.email || "";
    // 邮箱验证提示
    const verifyHint = document.getElementById("menu-verify-hint");
    if (verifyHint) {
      verifyHint.style.display = _authState.user.email_verified ? "none" : "block";
    }
    // 试用徽章
    const badge = document.getElementById("nav-trial-badge");
    if (badge) {
      if (_authState.user.is_trial && _authState.user.trial_days_left > 0) {
        badge.style.display = "inline-block";
        badge.textContent = "试用 " + _authState.user.trial_days_left + " 天";
        badge.className = "trial-badge";
      } else if (_authState.user.is_vip_active) {
        badge.style.display = "inline-block";
        badge.textContent = "PRO";
        badge.className = "trial-badge trial-badge-pro";
      } else {
        badge.style.display = "none";
      }
    }
  } else {
    loginBtn.style.display = "";
    userInfo.style.display = "none";
  }
}

function toggleUserMenu() {
  const menu = document.getElementById("nav-user-menu");
  if (!menu) return;
  menu.style.display = menu.style.display === "block" ? "none" : "block";
}

// 点击外部关闭用户菜单
document.addEventListener("click", (e) => {
  if (!e.target.closest(".nav-user-info")) {
    const menu = document.getElementById("nav-user-menu");
    if (menu) menu.style.display = "none";
  }
});

// ---- 登录注册弹窗 ----
function showAuthModal(tab) {
  document.getElementById("auth-modal").style.display = "flex";
  switchAuthTab(tab || "login");
  document.getElementById("auth-error").style.display = "none";
}
function closeAuthModal() {
  document.getElementById("auth-modal").style.display = "none";
  // 重置验证面板状态
  const vp = document.getElementById("auth-verify-panel");
  if (vp) vp.style.display = "none";
  const fp = document.getElementById("auth-forgot-panel");
  if (fp) fp.style.display = "none";
  const rp = document.getElementById("auth-reset-panel");
  if (rp) rp.style.display = "none";
  const tabs = document.getElementById("auth-tabs");
  if (tabs) tabs.style.display = "";
}
function switchAuthTab(tab) {
  const tabLogin = document.getElementById("auth-tab-login");
  const tabReg = document.getElementById("auth-tab-register");
  const fLogin = document.getElementById("auth-login-form");
  const fReg = document.getElementById("auth-register-form");
  if (tab === "register") {
    tabLogin.classList.remove("active"); tabReg.classList.add("active");
    fLogin.style.display = "none"; fReg.style.display = "block";
  } else {
    tabLogin.classList.add("active"); tabReg.classList.remove("active");
    fLogin.style.display = "block"; fReg.style.display = "none";
  }
  document.getElementById("auth-error").style.display = "none";
}

function showAuthError(msg) {
  const el = document.getElementById("auth-error");
  el.textContent = msg;
  el.style.display = "block";
}

async function doLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const btn = document.getElementById("login-submit-btn");
  btn.disabled = true; btn.textContent = "登录中...";
  try {
    const resp = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "登录失败");
    _authState.token = json.access_token;
    _authState.user = json.user;
    localStorage.setItem("auth_token", json.access_token);
    // 移除旧的纯前端 vip 标记
    localStorage.removeItem("vip");
    closeAuthModal();
    updateNavUser();
    // 加载服务端收藏和历史
    loadServerFavorites();
    loadServerHistory();
    showToast("登录成功，欢迎回来！");
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "登录";
  }
}

async function doRegister(e) {
  e.preventDefault();
  const email = document.getElementById("reg-email").value.trim();
  const nickname = document.getElementById("reg-nickname").value.trim();
  const password = document.getElementById("reg-password").value;
  const btn = document.getElementById("reg-submit-btn");
  btn.disabled = true; btn.textContent = "注册中...";
  try {
    const resp = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, nickname: nickname || null }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "注册失败");
    _authState.token = json.access_token;
    _authState.user = json.user;
    localStorage.setItem("auth_token", json.access_token);
    localStorage.removeItem("vip");
    updateNavUser();
    showToast("注册成功！已开启 7 天 PRO 免费试用");
    // 注册成功后 → 显示邮箱验证面板
    showVerifyPanel(email);
  } catch (err) {
    showAuthError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "注册并开始试用";
  }
}

function doLogout() {
  _authState.token = null;
  _authState.user = null;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("vip");
  // 清除服务端缓存，回退到 localStorage
  _serverFavorites = null;
  _serverHistory = null;
  updateNavUser();
  renderWatchlist();
  renderHistory();
  const menu = document.getElementById("nav-user-menu");
  if (menu) menu.style.display = "none";
  showToast("已退出登录");
}

// ---- 邮箱验证 ----
function showVerifyPanel(email) {
  // 隐藏登录/注册表单，显示验证面板
  document.getElementById("auth-login-form").style.display = "none";
  document.getElementById("auth-register-form").style.display = "none";
  document.getElementById("auth-tabs").style.display = "none";
  document.getElementById("auth-error").style.display = "none";
  const panel = document.getElementById("auth-verify-panel");
  panel.style.display = "block";
  document.getElementById("verify-email-display").textContent = email;
  document.getElementById("verify-code-input").value = "";
  document.getElementById("verify-hint").textContent = "";
  // 自动发送验证码
  doSendVerifyCode();
}

/** 从菜单打开验证面板 */
function openVerifyPanel() {
  if (!_authState.user) { showAuthModal("login"); return; }
  document.getElementById("auth-modal").style.display = "flex";
  showVerifyPanel(_authState.user.email);
}

let _resendCountdown = 0;
let _resendTimer = null;

async function doSendVerifyCode() {
  const btn = document.getElementById("verify-resend-btn");
  const hint = document.getElementById("verify-hint");
  try {
    const resp = await apiFetch(`${API_BASE}/auth/send-verify-code`, { method: "POST" });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "发送失败");
    hint.textContent = json.message || "验证码已发送";
    hint.style.color = "var(--green)";
    // 60秒倒计时
    startResendCountdown(btn);
  } catch (err) {
    hint.textContent = err.message;
    hint.style.color = "var(--red)";
  }
}

function startResendCountdown(btn) {
  _resendCountdown = 60;
  btn.disabled = true;
  if (_resendTimer) clearInterval(_resendTimer);
  _resendTimer = setInterval(() => {
    _resendCountdown--;
    if (_resendCountdown <= 0) {
      clearInterval(_resendTimer);
      btn.disabled = false;
      btn.textContent = "重新发送";
    } else {
      btn.textContent = `${_resendCountdown}s 后重发`;
    }
  }, 1000);
}

async function doResendCode() {
  await doSendVerifyCode();
}

async function doVerifyEmail() {
  const code = document.getElementById("verify-code-input").value.trim();
  const btn = document.getElementById("verify-submit-btn");
  const hint = document.getElementById("verify-hint");
  if (!code || code.length < 6) { hint.textContent = "请输入 6 位验证码"; hint.style.color = "var(--red)"; return; }
  btn.disabled = true; btn.textContent = "验证中...";
  try {
    const resp = await apiFetch(`${API_BASE}/auth/verify-email`, {
      method: "POST",
      body: { code },
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "验证失败");
    _authState.user = json.user;
    closeAuthModal();
    updateNavUser();
    showToast("邮箱验证成功！");
  } catch (err) {
    hint.textContent = err.message;
    hint.style.color = "var(--red)";
  } finally {
    btn.disabled = false; btn.textContent = "验证";
  }
}

function skipVerify() {
  closeAuthModal();
  showToast("您可以稍后在菜单中验证邮箱");
}

// ---- 忘记密码 / 重置密码 ----
let _resetEmail = "";
let _resetCountdown = 0;
let _resetTimer = null;

function showForgotPanel() {
  document.getElementById("auth-login-form").style.display = "none";
  document.getElementById("auth-register-form").style.display = "none";
  document.getElementById("auth-tabs").style.display = "none";
  document.getElementById("auth-error").style.display = "none";
  document.getElementById("auth-verify-panel").style.display = "none";
  document.getElementById("auth-reset-panel").style.display = "none";
  const panel = document.getElementById("auth-forgot-panel");
  panel.style.display = "block";
  document.getElementById("forgot-email").value = "";
  document.getElementById("forgot-hint").textContent = "";
}

function backToLogin() {
  document.getElementById("auth-forgot-panel").style.display = "none";
  document.getElementById("auth-reset-panel").style.display = "none";
  document.getElementById("auth-tabs").style.display = "";
  switchAuthTab("login");
}

async function doForgotPassword(e) {
  e.preventDefault();
  const email = document.getElementById("forgot-email").value.trim();
  const btn = document.getElementById("forgot-submit-btn");
  const hint = document.getElementById("forgot-hint");
  if (!email) { hint.textContent = "请输入邮箱"; hint.style.color = "var(--red)"; return; }

  btn.disabled = true; btn.textContent = "发送中...";
  try {
    const resp = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "发送失败");

    _resetEmail = email;
    hint.textContent = json.message || "验证码已发送";
    hint.style.color = "var(--green)";

    // 切换到重置密码面板
    setTimeout(() => showResetPanel(email), 800);
  } catch (err) {
    hint.textContent = err.message;
    hint.style.color = "var(--red)";
  } finally {
    btn.disabled = false; btn.textContent = "发送验证码";
  }
}

function showResetPanel(email) {
  document.getElementById("auth-forgot-panel").style.display = "none";
  const panel = document.getElementById("auth-reset-panel");
  panel.style.display = "block";
  document.getElementById("reset-email-display").textContent = email;
  document.getElementById("reset-code").value = "";
  document.getElementById("reset-password").value = "";
  document.getElementById("reset-hint").textContent = "";
  startResetCountdown();
}

function startResetCountdown() {
  const btn = document.getElementById("reset-resend-btn");
  _resetCountdown = 60;
  btn.disabled = true;
  if (_resetTimer) clearInterval(_resetTimer);
  _resetTimer = setInterval(() => {
    _resetCountdown--;
    if (_resetCountdown <= 0) {
      clearInterval(_resetTimer);
      btn.disabled = false;
      btn.textContent = "重新发送";
    } else {
      btn.textContent = `${_resetCountdown}s 后重发`;
    }
  }, 1000);
}

async function doResendResetCode() {
  const hint = document.getElementById("reset-hint");
  try {
    const resp = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: _resetEmail }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "发送失败");
    hint.textContent = "验证码已重新发送";
    hint.style.color = "var(--green)";
    startResetCountdown();
  } catch (err) {
    hint.textContent = err.message;
    hint.style.color = "var(--red)";
  }
}

async function doResetPassword(e) {
  e.preventDefault();
  const code = document.getElementById("reset-code").value.trim();
  const password = document.getElementById("reset-password").value;
  const btn = document.getElementById("reset-submit-btn");
  const hint = document.getElementById("reset-hint");

  if (!code || code.length < 6) { hint.textContent = "请输入6位验证码"; hint.style.color = "var(--red)"; return; }
  if (!password || password.length < 6) { hint.textContent = "密码至少6位"; hint.style.color = "var(--red)"; return; }

  btn.disabled = true; btn.textContent = "重置中...";
  try {
    const resp = await fetch(`${API_BASE}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: _resetEmail, code, new_password: password }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "重置失败");

    showToast("密码重置成功，请重新登录");
    backToLogin();
  } catch (err) {
    hint.textContent = err.message;
    hint.style.color = "var(--red)";
  } finally {
    btn.disabled = false; btn.textContent = "确认重置";
  }
}

// ---- OAuth 第三方登录 ----
let _oauthProviders = [];

async function loadOAuthProviders() {
  try {
    const resp = await fetch(`${API_BASE}/auth/oauth/providers`);
    if (resp.ok) {
      const json = await resp.json();
      _oauthProviders = json.providers || [];
      renderOAuthButtons();
    }
  } catch (err) {
    console.error("加载OAuth提供商失败", err);
  }
}

function renderOAuthButtons() {
  const section = document.getElementById("oauth-section");
  const container = document.getElementById("oauth-buttons");
  if (!section || !container) return;

  if (_oauthProviders.length === 0) {
    section.style.display = "none";
    return;
  }

  section.style.display = "block";
  container.innerHTML = _oauthProviders.map(p => {
    const icon = p.id === "wechat" ? "&#128172;" : p.id === "github" ? "&#128025;" : "&#128279;";
    return `<button class="oauth-btn oauth-${p.id}" onclick="doOAuthLogin('${p.id}')">${icon} ${p.name}</button>`;
  }).join("");
}

async function doOAuthLogin(provider) {
  try {
    const resp = await fetch(`${API_BASE}/auth/oauth/${provider}/url`);
    if (!resp.ok) {
      const json = await resp.json();
      throw new Error(json.detail || "获取授权链接失败");
    }
    const json = await resp.json();
    // 保存 state 用于验证
    sessionStorage.setItem("oauth_state", json.state);
    sessionStorage.setItem("oauth_provider", provider);
    // 跳转到授权页面
    window.location.href = json.url;
  } catch (err) {
    showToast(err.message);
  }
}

async function handleOAuthCallback() {
  // 检查 URL 中是否有 OAuth 回调参数
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const state = params.get("state");
  
  if (!code) return;
  
  const savedState = sessionStorage.getItem("oauth_state");
  const provider = sessionStorage.getItem("oauth_provider");
  
  // 清理 URL 参数
  window.history.replaceState({}, document.title, window.location.pathname);
  
  if (!provider) {
    showToast("OAuth 登录失败：会话已过期");
    return;
  }
  
  // 验证 state（可选，增强安全性）
  if (savedState && state !== savedState) {
    showToast("OAuth 登录失败：状态验证失败");
    return;
  }
  
  sessionStorage.removeItem("oauth_state");
  sessionStorage.removeItem("oauth_provider");
  
  try {
    const resp = await fetch(`${API_BASE}/auth/oauth/${provider}/callback?code=${encodeURIComponent(code)}`, {
      method: "POST",
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "登录失败");
    
    _authState.token = json.access_token;
    _authState.user = json.user;
    localStorage.setItem("auth_token", json.access_token);
    updateNavUser();
    loadServerFavorites();
    loadServerHistory();
    
    if (json.is_new) {
      showToast("欢迎！账号已自动创建");
    } else if (json.bound) {
      showToast("已绑定到现有账户");
    } else {
      showToast("登录成功！");
    }
  } catch (err) {
    showToast(err.message);
  }
}

// ---- 个人设置弹窗 ----
function showSettingsModal() {
  if (!_authState.user) { showAuthModal("login"); return; }
  document.getElementById("settings-modal").style.display = "flex";
  document.getElementById("settings-email").value = _authState.user.email || "";
  document.getElementById("settings-nickname").value = _authState.user.nickname || "";
  document.getElementById("settings-error").style.display = "none";
  document.getElementById("settings-success").style.display = "none";
  switchSettingsTab("profile");
}

function closeSettingsModal() {
  document.getElementById("settings-modal").style.display = "none";
}

function switchSettingsTab(tab) {
  const tabProfile = document.getElementById("settings-tab-profile");
  const tabPassword = document.getElementById("settings-tab-password");
  const fProfile = document.getElementById("settings-profile-form");
  const fPassword = document.getElementById("settings-password-form");
  document.getElementById("settings-error").style.display = "none";
  document.getElementById("settings-success").style.display = "none";

  if (tab === "password") {
    tabProfile.classList.remove("active"); tabPassword.classList.add("active");
    fProfile.style.display = "none"; fPassword.style.display = "block";
    document.getElementById("settings-old-password").value = "";
    document.getElementById("settings-new-password").value = "";
    document.getElementById("settings-confirm-password").value = "";
  } else {
    tabProfile.classList.add("active"); tabPassword.classList.remove("active");
    fProfile.style.display = "block"; fPassword.style.display = "none";
  }
}

function showSettingsError(msg) {
  const el = document.getElementById("settings-error");
  el.textContent = msg;
  el.style.display = "block";
  document.getElementById("settings-success").style.display = "none";
}

function showSettingsSuccess(msg) {
  const el = document.getElementById("settings-success");
  el.textContent = msg;
  el.style.display = "block";
  document.getElementById("settings-error").style.display = "none";
}

async function doUpdateProfile(e) {
  e.preventDefault();
  const nickname = document.getElementById("settings-nickname").value.trim();
  const btn = document.getElementById("profile-submit-btn");

  if (!nickname) { showSettingsError("昵称不能为空"); return; }

  btn.disabled = true; btn.textContent = "保存中...";
  try {
    const resp = await apiFetch(`${API_BASE}/user/profile`, {
      method: "PUT",
      body: { nickname },
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "保存失败");

    _authState.user = json.user;
    updateNavUser();
    showSettingsSuccess("资料已更新");
  } catch (err) {
    showSettingsError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "保存修改";
  }
}

async function doChangePassword(e) {
  e.preventDefault();
  const oldPwd = document.getElementById("settings-old-password").value;
  const newPwd = document.getElementById("settings-new-password").value;
  const confirmPwd = document.getElementById("settings-confirm-password").value;
  const btn = document.getElementById("password-submit-btn");

  if (!oldPwd) { showSettingsError("请输入原密码"); return; }
  if (newPwd.length < 6) { showSettingsError("新密码至少6位"); return; }
  if (newPwd !== confirmPwd) { showSettingsError("两次输入的新密码不一致"); return; }

  btn.disabled = true; btn.textContent = "修改中...";
  try {
    const resp = await apiFetch(`${API_BASE}/user/change-password`, {
      method: "POST",
      body: { old_password: oldPwd, new_password: newPwd },
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "修改失败");

    showSettingsSuccess("密码修改成功");
    document.getElementById("settings-old-password").value = "";
    document.getElementById("settings-new-password").value = "";
    document.getElementById("settings-confirm-password").value = "";
  } catch (err) {
    showSettingsError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "修改密码";
  }
}

/** 创建订单并发起支付 */
async function createOrder(planType) {
  if (!_authState.user) {
    closeVIPModal();
    showAuthModal("register");
    return;
  }
  try {
    const resp = await apiFetch(`${API_BASE}/user/orders`, {
      method: "POST",
      body: { plan_type: planType },
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "创建订单失败");

    // 显示支付面板
    showPaymentPanel(json);
  } catch (err) {
    showToast(err.message);
  }
}

/** 显示支付面板 */
function showPaymentPanel(orderData) {
  const { order_no, plan, payment, sandbox } = orderData;

  // 隐藏套餐选择，显示支付面板
  const plansEl = document.getElementById("vip-plans");
  const paymentEl = document.getElementById("vip-payment");
  if (plansEl) plansEl.style.display = "none";
  if (!paymentEl) {
    // 动态创建支付面板
    const modal = document.querySelector(".vip-modal-box");
    const payDiv = document.createElement("div");
    payDiv.id = "vip-payment";
    payDiv.innerHTML = `<div class="payment-panel"></div>`;
    modal.insertBefore(payDiv, modal.querySelector(".vip-modal-note"));
  }

  const panel = document.querySelector("#vip-payment .payment-panel") || document.getElementById("vip-payment");
  
  if (sandbox && payment.pay_url) {
    // 沙盒模式：显示模拟支付按钮
    panel.innerHTML = `
      <div class="payment-info">
        <h3>确认支付</h3>
        <div class="payment-plan">${plan.name}</div>
        <div class="payment-amount">${plan.price_yuan}</div>
        <p class="payment-hint">沙盒测试模式</p>
      </div>
      <div class="payment-actions">
        <button class="payment-btn" onclick="doSandboxPayment('${order_no}')">模拟支付</button>
        <button class="payment-cancel-btn" onclick="cancelPayment()">取消</button>
      </div>
    `;
  } else if (payment.qr_code) {
    // 生产模式：显示支付二维码
    panel.innerHTML = `
      <div class="payment-info">
        <h3>扫码支付</h3>
        <div class="payment-plan">${plan.name}</div>
        <div class="payment-amount">${plan.price_yuan}</div>
        <img src="${payment.qr_code}" alt="支付二维码" class="payment-qrcode" />
        <p class="payment-hint">请使用支付宝或微信扫码</p>
      </div>
      <div class="payment-actions">
        <button class="payment-check-btn" onclick="checkPaymentStatus('${order_no}')">我已支付</button>
        <button class="payment-cancel-btn" onclick="cancelPayment()">取消</button>
      </div>
    `;
  } else {
    // 支付接口未配置
    panel.innerHTML = `
      <div class="payment-info">
        <h3>${plan.name}</h3>
        <div class="payment-amount">${plan.price_yuan}</div>
        <p class="payment-hint">${payment.message || '支付功能配置中，敬请期待！'}</p>
      </div>
      <div class="payment-actions">
        <button class="payment-cancel-btn" onclick="cancelPayment()">返回</button>
      </div>
    `;
  }

  document.getElementById("vip-payment").style.display = "block";
}

/** 沙盒模式模拟支付 */
async function doSandboxPayment(orderNo) {
  try {
    const resp = await apiFetch(`${API_BASE}/payment/sandbox/${orderNo}`, {
      method: "POST",
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "支付失败");

    // 更新用户状态
    if (json.user) {
      _authState.user = json.user;
      updateNavUser();
    }

    closeVIPModal();
    showToast("支付成功！VIP 已激活");
  } catch (err) {
    showToast(err.message);
  }
}

/** 检查支付状态 */
async function checkPaymentStatus(orderNo) {
  try {
    const resp = await apiFetch(`${API_BASE}/user/orders/${orderNo}`);
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.detail || "查询失败");

    if (json.status === "paid") {
      // 刷新用户状态
      const profileResp = await apiFetch(`${API_BASE}/user/profile`);
      if (profileResp.ok) {
        const profileJson = await profileResp.json();
        _authState.user = profileJson.user;
        updateNavUser();
      }
      closeVIPModal();
      showToast("支付成功！VIP 已激活");
    } else {
      showToast("订单尚未支付，请完成支付后再试");
    }
  } catch (err) {
    showToast(err.message);
  }
}

/** 取消支付 */
function cancelPayment() {
  const plansEl = document.getElementById("vip-plans");
  const paymentEl = document.getElementById("vip-payment");
  if (plansEl) plansEl.style.display = "";
  if (paymentEl) paymentEl.style.display = "none";
}

// ---- 页面切换 ----
function showPage(id) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
  window.scrollTo(0, 0);
  // 导航高亮
  const navHome = document.getElementById("nav-home");
  const navBatch = document.getElementById("nav-batch");
  const navPf = document.getElementById("nav-portfolio");
  if (navHome) navHome.classList.toggle("active", id === "page-home");
  if (navBatch) navBatch.classList.toggle("active", id === "page-batch");
  if (navPf) navPf.classList.toggle("active", id === "page-portfolio");
  // 移动端底部导航
  document.querySelectorAll(".mbn-item").forEach(b => b.classList.remove("active"));
  const mbnMap = { "page-home": "mbn-home", "page-batch": "mbn-batch", "page-portfolio": "mbn-portfolio" };
  const mbn = document.getElementById(mbnMap[id]);
  if (mbn) mbn.classList.add("active");
}

function showHome() { _fromBatch = false; showPage("page-home"); }
function showBatchPage() { showPage("page-batch"); }
function showPortfolioPage() { showPage("page-portfolio"); renderPfTable(); }
function goBack() {
  if (_fromBatch) { showPage("page-batch"); }
  else { showHome(); }
}

// ---- 搜索 / 扫描 ----
let _searchTimer = null;
const _searchDropdown = () => document.getElementById("search-dropdown");

function doScan() {
  const input = document.getElementById("search-input");
  const code = input.value.trim();
  if (!code) { input.focus(); return; }
  hideDropdown();
  // 提取纯代码（如果用户选了自动补全项 "600519 贵州茅台" 取前6位）
  const match = code.match(/^(\d{6})/);
  scanStock(match ? match[1] : code);
}

function quickScan(code) {
  document.getElementById("search-input").value = code;
  hideDropdown();
  scanStock(code);
}

// 搜索自动补全
function onSearchInput(e) {
  const q = e.target.value.trim();
  if (_searchTimer) clearTimeout(_searchTimer);
  if (q.length < 1) { hideDropdown(); return; }
  _searchTimer = setTimeout(() => fetchSearchResults(q), 300);
}

async function fetchSearchResults(q) {
  try {
    const dd = _searchDropdown();
    dd.innerHTML = '<div class="search-loading">搜索中...</div>';
    dd.style.display = "block";
    const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
    const json = await resp.json();
    const results = json.results || [];
    if (results.length === 0) { dd.innerHTML = '<div class="search-loading">未找到结果</div>'; return; }
    dd.innerHTML = results.map(r => `
      <div class="search-item" onmousedown="selectSearchItem('${esc(r.code)}','${esc(r.name)}')">
        <span class="si-code">${esc(r.code)}</span>
        <span class="si-name">${esc(r.name)}</span>
      </div>
    `).join("");
    dd.style.display = "block";
  } catch (_) { hideDropdown(); }
}

function selectSearchItem(code, name) {
  document.getElementById("search-input").value = code;
  hideDropdown();
  scanStock(code);
}

function hideDropdown() {
  const dd = _searchDropdown();
  if (dd) dd.style.display = "none";
}

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-input-wrap")) hideDropdown();
  if (!e.target.closest(".pf-add-input-wrap")) hidePfDropdown();
});

async function scanStock(code) {
  _fromBatch = false;
  document.getElementById("loading-text").textContent =
    `正在扫描 ${code} 的风险数据...`;
  // 重置步骤
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById("ls-" + i);
    if (el) { el.className = "ls-item" + (i === 1 ? " active" : ""); }
  }
  showPage("page-loading");

  // 模拟步骤推进
  const stepTimers = [
    setTimeout(() => { setLoadingStep(2); }, 2000),
    setTimeout(() => { setLoadingStep(3); }, 5000),
    setTimeout(() => { setLoadingStep(4); }, 8000),
  ];

  try {
    const resp = await apiFetch(`${API_BASE}/scan/${encodeURIComponent(code)}`);
    stepTimers.forEach(clearTimeout);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    const json = await resp.json();
    if (json.success && json.data) {
      // 标记所有步骤完成
      for (let i = 1; i <= 4; i++) setLoadingStep(i, true);
      await new Promise(r => setTimeout(r, 300));
      renderResult(json.data);
      showPage("page-result");
    } else {
      throw new Error("返回数据异常");
    }
  } catch (e) {
    stepTimers.forEach(clearTimeout);
    document.getElementById("error-msg").textContent = e.message;
    showPage("page-error");
  }
}

function setLoadingStep(n, done) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById("ls-" + i);
    if (!el) continue;
    if (done && i <= n) el.className = "ls-item done";
    else if (i < n) el.className = "ls-item done";
    else if (i === n) el.className = "ls-item active";
    else el.className = "ls-item";
  }
}

// ---- 渲染结果 ----
function renderResult(data) {
  document.getElementById("result-name").textContent = data.stock_name || "未知";
  document.getElementById("result-code").textContent = data.stock_code || "";

  // 评分环
  const score = data.total_score || 0;
  const circumference = 2 * Math.PI * 52;
  const offset = circumference * (1 - score / 100);
  const ringFg = document.getElementById("ring-fg");
  ringFg.style.strokeDashoffset = circumference;
  requestAnimationFrame(() => {
    ringFg.style.strokeDashoffset = offset;
    ringFg.style.stroke = scoreColor(score);
  });

  const scoreEl = document.getElementById("score-value");
  animateNumber(scoreEl, 0, Math.round(score), 800);
  scoreEl.style.color = scoreColor(score);

  // 风险等级
  const levelEl = document.getElementById("risk-level");
  const cls = levelClass(data.risk_level);
  levelEl.className = "risk-level " + cls;
  levelEl.textContent = data.risk_level;

  // 摘要
  document.getElementById("summary").textContent = data.summary || "";

  // 统计
  const rc = data.risk_count || {};
  document.getElementById("risk-stats").innerHTML = `
    <span class="risk-stat"><span class="dot dot-danger"></span> 危险 ${rc.danger || 0}</span>
    <span class="risk-stat"><span class="dot dot-warning"></span> 警惕 ${rc.warning || 0}</span>
    <span class="risk-stat"><span class="dot dot-caution"></span> 注意 ${rc.caution || 0}</span>
  `;

  // 评分卡边框色
  const card = document.getElementById("score-card");
  card.style.borderColor =
    cls === "danger"  ? "rgba(239,68,68,.35)"  :
    cls === "warning" ? "rgba(249,115,22,.3)"   :
    cls === "caution" ? "rgba(234,179,8,.3)"    : "var(--card-border)";

  // 迷你走势图
  renderSparkline(data);

  // 收藏按钮状态
  updateFavBtn(data.stock_code);

  // 保存 risk_items 供导出用
  window._lastRiskItems = (data.risk_items || []).slice().sort((a, b) => a.score - b.score);

  // 风险明细 - 有问题的排前面
  const itemsEl = document.getElementById("risk-items");
  const items = (data.risk_items || []).slice().sort((a, b) => a.score - b.score);
  itemsEl.innerHTML = items.map((item, idx) => {
    const c = levelClass(item.level);
    return `
      <div class="risk-item anim-fade-up" style="animation-delay:${idx * 60}ms">
        <div class="ri-badge ${c}">${Math.round(item.score)}</div>
        <div class="ri-body">
          <div class="ri-top">
            <span class="ri-name">${esc(item.name)}</span>
            <span class="ri-cat">${esc(item.category)}</span>
          </div>
          <div class="ri-detail">${esc(item.detail)}</div>
        </div>
      </div>`;
  }).join("");

  // 风险雷达图
  const radarContainer = document.getElementById("risk-radar-container");
  if (radarContainer) {
    radarContainer.innerHTML = renderRiskRadar(data.risk_items || []);
  }

  // 底部建议
  const adviceEl = document.getElementById("result-advice");
  if (adviceEl) {
    if (score < 30) {
      adviceEl.textContent = "强烈建议：该股票风险极高，建议回避！";
      adviceEl.className = "result-advice danger";
    } else if (score < 50) {
      adviceEl.textContent = "建议：该股票存在较大风险，请谨慎考虑";
      adviceEl.className = "result-advice warning";
    } else if (score < 70) {
      adviceEl.textContent = "提示：存在一定风险，建议深入研究后决策";
      adviceEl.className = "result-advice caution";
    } else {
      adviceEl.textContent = "该股票基本面相对健康，但投资有风险，请自行判断";
      adviceEl.className = "result-advice safe";
    }
  }

  // 量化因子分析
  renderQuantSection(data.quant_analysis);

  // 保存历史 & 更新首页
  saveToHistory(data);
  renderHistory();
  renderDashboard();
}

// ---- VIP 状态管理（服务端驱动） ----
function checkVIP() {
  if (_authState.user) return _authState.user.has_pro_access === true;
  return false;
}
function unlockVIP() {
  // 兼容旧调用 — 引导到订单流程
  createOrder("yearly");
}
function showVIPModal() {
  document.getElementById("vip-modal").style.display = "flex";
}
function closeVIPModal() {
  document.getElementById("vip-modal").style.display = "none";
  // 重置支付面板状态
  const plansEl = document.getElementById("vip-plans");
  const paymentEl = document.getElementById("vip-payment");
  if (plansEl) plansEl.style.display = "";
  if (paymentEl) paymentEl.style.display = "none";
}

// ---- 量化因子渲染 ----
function renderQuantSection(qa) {
  const section = document.getElementById("quant-section");
  if (!qa || !qa.factors || !qa.factors.beta) {
    section.style.display = "none";
    return;
  }
  section.style.display = "block";

  const f = qa.factors || {};
  const r = qa.risk_metrics || {};
  const m = (qa.momentum && !qa.momentum.locked) ? qa.momentum : {};
  const s = (qa.smart_money && !qa.smart_money.locked) ? qa.smart_money : {};
  const mLocked = qa.momentum && qa.momentum.locked;
  const sLocked = qa.smart_money && qa.smart_money.locked;
  const qScore = qa.overall_quant_score || 0;
  const qLevel = qa.quant_level || "";

  // 评分颜色
  const qColor = qScore >= 65 ? "var(--green)" : qScore >= 45 ? "var(--yellow)" : "var(--red)";

  // VIP锁定标记（动量和聪明钱需要VIP）
  const locked = !checkVIP();
  const lockCls = locked ? "vip-locked" : "";
  const lockOverlay = locked ? `<div class="vip-blur-overlay" onclick="showVIPModal()"><div class="vip-lock-inner"><span class="vip-lock-icon">&#128274;</span><span>升级 PRO 解锁完整因子数据</span></div></div>` : "";

  // 试用/VIP 徽章
  let trialBadgeHTML = "";
  if (_authState.user && _authState.user.is_vip_active) {
    trialBadgeHTML = `<span class="quant-pro-badge">PRO</span>`;
  } else if (_authState.user && _authState.user.is_trial && _authState.user.trial_days_left > 0) {
    trialBadgeHTML = `<span class="quant-trial-badge">&#9201; 试用剩余 ${_authState.user.trial_days_left} 天</span>`;
  } else if (_authState.user && !_authState.user.has_pro_access) {
    trialBadgeHTML = `<span class="quant-trial-badge trial-expired">试用已结束</span>`;
  } else {
    trialBadgeHTML = `<span class="quant-trial-badge">&#9733; 免费试用</span>`;
  }

  section.innerHTML = `
    <div class="quant-header">
      <h3>量化因子分析</h3>
      ${trialBadgeHTML}
      ${!checkVIP() ? `<button class="quant-upgrade-btn" onclick="${_authState.user ? 'showVIPModal()' : 'showAuthModal(\"register\")'}">${_authState.user ? '升级 PRO' : '登录解锁'}</button>` : ``}
    </div>

    <div class="quant-score-banner">
      <div class="quant-score-num" style="color:${qColor}">${qScore}</div>
      <div class="quant-score-info">
        <div class="quant-score-level" style="color:${qColor}">${esc(qLevel)}</div>
        <div class="quant-score-model">基于 Fama-French / Markowitz / Momentum 多因子综合评估 &middot; ${esc(qa.model_version || "")}</div>
      </div>
    </div>

    <div class="quant-grid">
      <!-- Fama-French (免费) -->
      <div class="quant-card">
        <div class="quant-card-head">
          <span class="quant-card-title">Fama-French 五因子</span>
          <span class="quant-card-nobel">Nobel ${f.nobel_year || 2013}</span>
        </div>
        <div class="quant-metrics">
          ${qMetric("Beta (市场因子)", fmtNum(f.beta, 3), valCls(f.beta, 1, 1.5, true))}
          ${qMetric("Jensen's Alpha", fmtPct(f.alpha), valCls(f.alpha, 0))}
          ${qMetric("年化收益率", fmtPct(f.annual_return), valCls(f.annual_return, 0))}
          ${qMetric("年化波动率", fmtPct(f.annual_volatility), "qv-neutral")}
          ${qMetric("HML 价值因子", fmtNum(f.hml_value, 3), valCls(f.hml_value, 0))}
          ${qMetric("RMW 盈利因子", fmtNum(f.rmw_profitability, 3), valCls(f.rmw_profitability, 0))}
          ${qMetric("CMA 投资因子", fmtNum(f.cma_investment, 3), valCls(f.cma_investment, 0))}
        </div>
      </div>

      <!-- 风险度量 (免费) -->
      <div class="quant-card">
        <div class="quant-card-head">
          <span class="quant-card-title">Markowitz-Sharpe 风险度量</span>
          <span class="quant-card-nobel">Nobel ${r.nobel_year || 1990}</span>
        </div>
        <div class="quant-metrics">
          ${qMetric("Sharpe Ratio", fmtNum(r.sharpe_ratio, 3), valCls(r.sharpe_ratio, 0.5))}
          ${qMetric("Sortino Ratio", fmtNum(r.sortino_ratio, 3), valCls(r.sortino_ratio, 0.5))}
          ${qMetric("Calmar Ratio", fmtNum(r.calmar_ratio, 3), valCls(r.calmar_ratio, 0.5))}
          ${qMetric("VaR 95%", r.var_95 + "%", "qv-warn")}
          ${qMetric("CVaR 95%", r.cvar_95 + "%", "qv-warn")}
          ${qMetric("最大回撤", r.max_drawdown + "%", r.max_drawdown < -25 ? "qv-negative" : "qv-neutral")}
          ${qMetric("20日波动率", r.volatility_20d + "%", "qv-neutral")}
        </div>
      </div>

      <!-- 动量因子 (VIP) -->
      <div class="quant-card ${(locked || mLocked) ? 'vip-locked' : ''}">
        <div class="quant-card-head">
          <span class="quant-card-title">Cross-Sectional Momentum</span>
          <span class="quant-card-nobel">AQR / Jegadeesh</span>
          ${(locked || mLocked) ? '<span class="quant-card-pro">PRO</span>' : ''}
        </div>
        <div class="quant-metrics">
          ${qMetric("5日动量", m.momentum_5d != null ? m.momentum_5d + "%" : "--", valCls(m.momentum_5d, 0))}
          ${qMetric("20日动量", m.momentum_20d != null ? m.momentum_20d + "%" : "--", valCls(m.momentum_20d, 0))}
          ${qMetric("60日动量", m.momentum_60d != null ? m.momentum_60d + "%" : "--", valCls(m.momentum_60d, 0))}
          ${qMetric("120日动量", m.momentum_120d != null ? m.momentum_120d + "%" : "--", valCls(m.momentum_120d, 0))}
          ${qMetric("RSI (14)", m.rsi_14 != null ? fmtNum(m.rsi_14, 1) : "--", m.rsi_14 > 70 ? "qv-warn" : m.rsi_14 < 30 ? "qv-negative" : "qv-neutral")}
          ${qMetric("量比", m.volume_ratio != null ? fmtNum(m.volume_ratio, 2) : "--", "qv-neutral")}
        </div>
        ${m.divergence_signal && m.divergence_signal !== "无" ?
          `<div class="quant-signal ${m.divergence_signal.includes("顶背离") || m.divergence_signal.includes("恐慌") ? "bearish" : m.divergence_signal.includes("企稳") ? "bullish" : "neutral"}">${esc(m.divergence_signal)}</div>` : ""}
        ${(locked || mLocked) ? lockOverlay : ""}
      </div>

      <!-- 聪明钱 (VIP) -->
      <div class="quant-card ${(locked || sLocked) ? 'vip-locked' : ''}">
        <div class="quant-card-head">
          <span class="quant-card-title">Smart Money Flow</span>
          <span class="quant-card-nobel">Chaikin / OBV</span>
          ${(locked || sLocked) ? '<span class="quant-card-pro">PRO</span>' : ''}
        </div>
        <div class="quant-metrics">
          ${qMetric("CMF (20日)", s.cmf_20 != null ? fmtNum(s.cmf_20, 4) : "--", valCls(s.cmf_20, 0))}
          ${qMetric("OBV 趋势", s.obv_trend || "--", s.obv_trend === "资金流入" ? "qv-positive" : s.obv_trend === "资金流出" ? "qv-negative" : "qv-neutral")}
          ${qMetric("资金压力", s.capital_pressure != null ? fmtNum(s.capital_pressure, 2) : "--", valCls(s.capital_pressure, 1))}
        </div>
        ${s.signal ?
          `<div class="quant-signal ${s.signal === "主力吸筹" ? "bullish" : s.signal === "主力出货" ? "bearish" : "neutral"}">${esc(s.signal)}</div>` : ""}
        ${(locked || sLocked) ? lockOverlay : ""}
      </div>
    </div>
  `;
}

// ---- 量化因子工具函数 ----
function qMetric(label, value, cls) {
  return `<div class="quant-metric-row"><span class="quant-metric-label">${label}</span><span class="quant-metric-value ${cls || ''}">${value}</span></div>`;
}

function fmtNum(v, decimals) {
  if (v == null || isNaN(v)) return "--";
  return Number(v).toFixed(decimals || 2);
}

function fmtPct(v) {
  if (v == null || isNaN(v)) return "--";
  return (Number(v) * 100).toFixed(2) + "%";
}

function valCls(v, threshold, upperThreshold, invertHigh) {
  if (v == null || isNaN(v)) return "qv-neutral";
  if (invertHigh && upperThreshold != null && v > upperThreshold) return "qv-warn";
  if (v > threshold) return "qv-positive";
  if (v < -threshold || (threshold === 0 && v < 0)) return "qv-negative";
  return "qv-neutral";
}

// ---- 批量扫描 ----

// 预设组合填充
function fillPreset(codes) {
  const textarea = document.getElementById("batch-input");
  textarea.value = codes;
  updateBatchCount();
}

// 实时计数
function updateBatchCount() {
  const textarea = document.getElementById("batch-input");
  const codes = textarea.value.trim().split(/[,，\s]+/).filter(c => c.trim());
  const el = document.getElementById("batch-count");
  el.textContent = `已输入 ${codes.length} 只`;
  el.style.color = codes.length > 10 ? "var(--red)" : "var(--text2)";
}

// 批量扫描（逐个进行，带进度）
async function doBatchScan() {
  const textarea = document.getElementById("batch-input");
  const raw = textarea.value.trim();
  if (!raw) { textarea.focus(); return; }

  const codes = raw.split(/[,，\s]+/).filter(c => c.trim()).map(c => c.trim().padStart(6, "0"));
  if (codes.length === 0) { textarea.focus(); return; }
  if (codes.length > 10) {
    alert("单次最多扫描10只股票"); return;
  }

  const resultsEl = document.getElementById("batch-results");
  const progressEl = document.getElementById("batch-progress");
  const summaryEl = document.getElementById("batch-summary");
  resultsEl.innerHTML = "";
  summaryEl.style.display = "none";

  // 显示进度条
  progressEl.style.display = "block";
  const progressFill = document.getElementById("batch-progress-fill");
  const progressText = document.getElementById("batch-progress-text");
  const progressNum = document.getElementById("batch-progress-num");

  const allResults = [];
  const stats = { danger: 0, warning: 0, caution: 0, safe: 0 };

  for (let i = 0; i < codes.length; i++) {
    const code = codes[i];
    const pct = ((i) / codes.length * 100);
    progressFill.style.width = pct + "%";
    progressText.textContent = `正在扫描 ${code} ...`;
    progressNum.textContent = `${i}/${codes.length}`;

    try {
      const resp = await fetch(`${API_BASE}/scan/${encodeURIComponent(code)}`);
      if (!resp.ok) throw new Error(`请求失败 (${resp.status})`);
      const json = await resp.json();

      if (json.success && json.data) {
        allResults.push({ code, success: true, data: json.data });
        const lvl = json.data.risk_level;
        if (lvl === "危险") stats.danger++;
        else if (lvl === "警惕") stats.warning++;
        else if (lvl === "注意") stats.caution++;
        else stats.safe++;
      } else {
        allResults.push({ code, success: false, error: "返回数据异常" });
      }
    } catch (e) {
      allResults.push({ code, success: false, error: e.message });
    }
  }

  // 完成
  progressFill.style.width = "100%";
  progressText.textContent = "扫描完成";
  progressNum.textContent = `${codes.length}/${codes.length}`;

  // 统计面板
  document.getElementById("bsi-danger-num").textContent = stats.danger;
  document.getElementById("bsi-warning-num").textContent = stats.warning;
  document.getElementById("bsi-caution-num").textContent = stats.caution;
  document.getElementById("bsi-safe-num").textContent = stats.safe;
  summaryEl.style.display = "flex";

  // 按分数排序 (低分在前)
  allResults.sort((a, b) => {
    const sa = a.success ? a.data.total_score : 999;
    const sb = b.success ? b.data.total_score : 999;
    return sa - sb;
  });

  // 渲染丰富结果卡片
  resultsEl.innerHTML = allResults.map((r) => {
    if (!r.success) {
      return `<div class="batch-error">${esc(r.code)}: ${esc(r.error || "扫描失败")}</div>`;
    }
    const d = r.data;
    const cls = levelClass(d.risk_level);
    const score = Math.round(d.total_score);
    const qa = d.quant_analysis;

    // 量化摘要行
    let quantLine = "";
    if (qa && qa.factors && qa.factors.beta != null) {
      const sharpe = qa.risk_metrics ? fmtNum(qa.risk_metrics.sharpe_ratio, 2) : "--";
      const beta = fmtNum(qa.factors.beta, 2);
      const mdd = qa.risk_metrics ? qa.risk_metrics.max_drawdown + "%" : "--";
      const qScore = qa.overall_quant_score || 0;
      const qColor = qScore >= 65 ? "var(--green)" : qScore >= 45 ? "var(--yellow)" : "var(--red)";
      quantLine = `
        <div class="bc-quant">
          <span class="bc-quant-badge">量化因子</span>
          <span class="bc-q-item">Sharpe <b class="${valCls(qa.risk_metrics?.sharpe_ratio, 0.5)}">${sharpe}</b></span>
          <span class="bc-q-item">Beta <b>${beta}</b></span>
          <span class="bc-q-item">MaxDD <b class="qv-warn">${mdd}</b></span>
          <span class="bc-q-score" style="color:${qColor}">${qScore}分</span>
        </div>`;
    }

    // 风险标签
    const dangerItems = (d.risk_items || []).filter(it => it.level === "危险" || it.level === "警惕");
    let riskTags = "";
    if (dangerItems.length > 0) {
      riskTags = `<div class="bc-risk-tags">${dangerItems.slice(0, 3).map(it => {
        const tcls = it.level === "危险" ? "brt-danger" : "brt-warning";
        return `<span class="bc-risk-tag ${tcls}">${esc(it.name)}</span>`;
      }).join("")}${dangerItems.length > 3 ? `<span class="bc-risk-tag brt-more">+${dangerItems.length - 3}</span>` : ""}</div>`;
    }

    return `
      <div class="batch-card-v2" onclick="viewBatchResult(this)" data-json='${esc(JSON.stringify(d))}'>
        <div class="bc-left">
          <div class="bc-score-ring ${cls}">
            <span>${score}</span>
          </div>
        </div>
        <div class="bc-body">
          <div class="bc-header">
            <h4>${esc(d.stock_name)}</h4>
            <span class="bc-code">${esc(d.stock_code)}</span>
            <span class="bc-level ${cls}">${esc(d.risk_level)}</span>
          </div>
          <p class="bc-summary">${esc(d.summary)}</p>
          ${riskTags}
          ${quantLine}
        </div>
        <div class="bc-arrow">&rsaquo;</div>
      </div>`;
  }).join("");

  // 2秒后隐藏进度条
  setTimeout(() => { progressEl.style.display = "none"; }, 2000);

  // 渲染对比面板
  const successResults = allResults.filter(r => r.success);
  if (successResults.length >= 2) {
    renderComparePanel(successResults.map(r => r.data));
  }
}

function viewBatchResult(el) {
  try {
    const data = JSON.parse(el.dataset.json);
    _fromBatch = true;
    renderResult(data);
    showPage("page-result");
  } catch (_) {}
}

// 初始化批量输入计数 + 全局初始化
document.addEventListener("DOMContentLoaded", () => {
  const batchInput = document.getElementById("batch-input");
  if (batchInput) {
    batchInput.addEventListener("input", updateBatchCount);
  }
  // 加载 OAuth 提供商
  loadOAuthProviders();
  // 处理 OAuth 回调
  handleOAuthCallback();
});

// ---- 工具函数 ----
function scoreColor(s) {
  if (s >= 90) return "#22c55e";
  if (s >= 70) return "#3b82f6";
  if (s >= 50) return "#eab308";
  if (s >= 30) return "#f97316";
  return "#ef4444";
}

function levelClass(level) {
  const m = { "安全": "safe", "良好": "good", "注意": "caution", "警惕": "warning", "危险": "danger" };
  return m[level] || "good";
}

function esc(s) {
  if (typeof s !== "string") return s;
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function animateNumber(el, from, to, duration) {
  const start = performance.now();
  function tick(now) {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (to - from) * ease);
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ---- 扫描历史管理 (支持服务端同步) ----
const HISTORY_KEY = "scan_history";
const MAX_HISTORY = 12;
let _serverHistory = null; // 缓存服务端历史

function getHistory() {
  // 已登录且有服务端缓存时使用服务端数据
  if (_authState.user && _serverHistory !== null) {
    return _serverHistory;
  }
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}

function saveToHistory(data) {
  if (!data || !data.stock_code) return;
  // 已登录时，后端会自动保存，只需更新本地缓存
  if (_authState.user && _serverHistory !== null) {
    _serverHistory = _serverHistory.filter(h => h.stock_code !== data.stock_code);
    _serverHistory.unshift({
      stock_code: data.stock_code,
      stock_name: data.stock_name || "未知",
      total_score: Math.round(data.total_score || 0),
      risk_level: data.risk_level || "--",
      scanned_at: new Date().toISOString(),
    });
    if (_serverHistory.length > MAX_HISTORY) _serverHistory.length = MAX_HISTORY;
    return;
  }
  // 未登录时保存到 localStorage
  const list = getHistory().filter(h => h.stock_code !== data.stock_code);
  list.unshift({
    stock_code: data.stock_code,
    stock_name: data.stock_name || "未知",
    total_score: Math.round(data.total_score || 0),
    risk_level: data.risk_level || "--",
    timestamp: Date.now(),
  });
  if (list.length > MAX_HISTORY) list.length = MAX_HISTORY;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}

function renderHistory() {
  const section = document.getElementById("recent-section");
  const listEl = document.getElementById("recent-list");
  if (!section || !listEl) return;
  const list = getHistory();
  if (list.length === 0) { section.style.display = "none"; return; }
  section.style.display = "block";
  listEl.innerHTML = list.map(h => {
    const cls = levelClass(h.risk_level);
    const ago = h.scanned_at ? timeAgoISO(h.scanned_at) : timeAgo(h.timestamp);
    return `
      <div class="recent-card" onclick="quickScan('${esc(h.stock_code)}')">
        <div class="rc-score ${cls}">${h.total_score}</div>
        <div class="rc-info">
          <span class="rc-name">${esc(h.stock_name)}</span>
          <span class="rc-code">${esc(h.stock_code)}</span>
        </div>
        <div class="rc-right">
          <span class="rc-level ${cls}">${esc(h.risk_level)}</span>
          <span class="rc-time">${ago}</span>
        </div>
      </div>`;
  }).join("");
}

async function clearHistory() {
  if (_authState.user) {
    try {
      await apiFetch(`${API_BASE}/user/scan-history`, { method: "DELETE" });
      _serverHistory = [];
    } catch (err) {
      console.error("清空历史失败", err);
    }
  }
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
}

function timeAgo(ts) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return mins + "分钟前";
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + "小时前";
  const days = Math.floor(hours / 24);
  return days + "天前";
}

function timeAgoISO(isoStr) {
  const ts = new Date(isoStr).getTime();
  return timeAgo(ts);
}

/** 从服务端加载扫描历史 */
async function loadServerHistory() {
  if (!_authState.user) return;
  try {
    const resp = await apiFetch(`${API_BASE}/user/scan-history`);
    if (resp.ok) {
      const json = await resp.json();
      _serverHistory = json.history || [];
      renderHistory();
    }
  } catch (err) {
    console.error("加载历史失败", err);
  }
}

// ---- 风险雷达图 (SVG) ----
function renderRiskRadar(riskItems) {
  if (!riskItems || riskItems.length === 0) return "";

  // 选取关键维度 (最多6个)
  const dims = [];
  const dimNames = ["财务风险", "价格风险", "ST风险", "质押风险", "现金流", "估值风险", "审计风险", "商誉风险", "应收账款", "股东减持", "连续亏损"];
  const catMap = {};
  riskItems.forEach(item => {
    const cat = item.category || item.name;
    if (!catMap[cat]) catMap[cat] = [];
    catMap[cat].push(item.score);
  });
  const entries = Object.entries(catMap).slice(0, 6);
  if (entries.length < 3) return "";

  entries.forEach(([name, scores]) => {
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
    dims.push({ name: name.replace("风险", ""), score: avg });
  });

  const n = dims.length;
  const cx = 140, cy = 140, R = 85;
  const angleStep = (2 * Math.PI) / n;

  // 背景网格
  let gridLines = "";
  [0.25, 0.5, 0.75, 1].forEach(ratio => {
    const r = R * ratio;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const angle = -Math.PI / 2 + i * angleStep;
      pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
    }
    gridLines += `<polygon points="${pts.join(" ")}" fill="none" stroke="rgba(148,163,184,.12)" stroke-width="1"/>`;
  });

  // 轴线
  let axes = "";
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const ex = cx + R * Math.cos(angle);
    const ey = cy + R * Math.sin(angle);
    axes += `<line x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="rgba(148,163,184,.1)" stroke-width="1"/>`;
  }

  // 数据多边形
  const dataPts = [];
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const ratio = Math.max(0, Math.min(1, dims[i].score / 100));
    dataPts.push(`${cx + R * ratio * Math.cos(angle)},${cy + R * ratio * Math.sin(angle)}`);
  }

  // 标签
  let labels = "";
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const lx = cx + (R + 28) * Math.cos(angle);
    const ly = cy + (R + 28) * Math.sin(angle);
    const anchor = Math.abs(Math.cos(angle)) < 0.1 ? "middle" : (Math.cos(angle) > 0 ? "start" : "end");
    const vOff = Math.sin(angle) > 0.3 ? 4 : (Math.sin(angle) < -0.3 ? -4 : 0);
    const scoreColor = dims[i].score >= 70 ? "var(--green)" : dims[i].score >= 50 ? "var(--yellow)" : "var(--red)";
    labels += `<text x="${lx}" y="${ly + vOff}" text-anchor="${anchor}" dominant-baseline="central" fill="var(--text2)" font-size="12">${dims[i].name}</text>`;
    labels += `<text x="${lx}" y="${ly + vOff + 15}" text-anchor="${anchor}" dominant-baseline="central" fill="${scoreColor}" font-size="11" font-weight="700">${Math.round(dims[i].score)}</text>`;
  }

  // 数据点
  let dots = "";
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const ratio = Math.max(0, Math.min(1, dims[i].score / 100));
    const dx = cx + R * ratio * Math.cos(angle);
    const dy = cy + R * ratio * Math.sin(angle);
    dots += `<circle cx="${dx}" cy="${dy}" r="3.5" fill="var(--accent)" stroke="#fff" stroke-width="1"/>`;
  }

  return `
    <div class="risk-radar-wrap">
      <h3 class="section-title">风险雷达</h3>
      <div class="risk-radar-chart">
        <svg viewBox="0 0 280 280" class="radar-svg">
          ${gridLines}
          ${axes}
          <polygon points="${dataPts.join(" ")}" fill="rgba(59,130,246,.15)" stroke="var(--accent)" stroke-width="2" class="radar-data-polygon"/>
          ${dots}
          ${labels}
        </svg>
      </div>
    </div>`;
}

// ---- 首页数字滚动动画 ----
function animateTrustNumbers() {
  const items = document.querySelectorAll(".trust-num");
  items.forEach(el => {
    const text = el.textContent.trim();
    const numMatch = text.match(/^([\d,]+)/);
    if (!numMatch) return;
    const target = parseInt(numMatch[1].replace(/,/g, ""));
    const suffix = text.replace(numMatch[1], "");
    if (isNaN(target) || target === 0) return;
    el._animated = false;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !el._animated) {
        el._animated = true;
        const duration = 1200;
        const start = performance.now();
        function tick(now) {
          const t = Math.min((now - start) / duration, 1);
          const ease = 1 - Math.pow(1 - t, 3);
          const cur = Math.round(target * ease);
          el.textContent = cur.toLocaleString() + suffix;
          if (t < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        observer.disconnect();
      }
    }, { threshold: 0.3 });
    observer.observe(el);
  });
}

// 初始化
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initAuth();
  renderHistory();
  renderWatchlist();
  renderDashboard();
  animateTrustNumbers();
});

// ---- 风险仪表盘 ----
function renderDashboard() {
  const section = document.getElementById("dashboard-section");
  if (!section) return;

  const history = getHistory();
  if (history.length < 2) { section.style.display = "none"; return; }
  section.style.display = "block";

  // 统计
  let safeCount = 0, cautionCount = 0, dangerCount = 0;
  let totalScore = 0;
  const buckets = { "90-100": 0, "70-89": 0, "50-69": 0, "30-49": 0, "0-29": 0 };

  history.forEach(h => {
    const s = h.total_score || 0;
    totalScore += s;
    if (h.risk_level === "安全" || h.risk_level === "良好") safeCount++;
    else if (h.risk_level === "注意") cautionCount++;
    else dangerCount++;

    if (s >= 90) buckets["90-100"]++;
    else if (s >= 70) buckets["70-89"]++;
    else if (s >= 50) buckets["50-69"]++;
    else if (s >= 30) buckets["30-49"]++;
    else buckets["0-29"]++;
  });

  const avgScore = Math.round(totalScore / history.length);
  const healthPct = avgScore / 100;

  document.getElementById("dash-total").textContent = history.length;
  document.getElementById("dash-safe-count").textContent = safeCount;
  document.getElementById("dash-caution-count").textContent = cautionCount;
  document.getElementById("dash-danger-count").textContent = dangerCount;

  // 半圆仪表
  const gaugeEl = document.getElementById("dash-gauge-chart");
  const sColor = scoreColor(avgScore);
  const sweepAngle = healthPct * 180;
  // SVG arc
  const rad = (deg) => deg * Math.PI / 180;
  const cx = 50, cy = 55, r = 40;
  const startAngle = 180;
  const endAngle = 180 + sweepAngle;
  const x1 = cx + r * Math.cos(rad(startAngle));
  const y1 = cy + r * Math.sin(rad(startAngle));
  const x2 = cx + r * Math.cos(rad(endAngle));
  const y2 = cy + r * Math.sin(rad(endAngle));
  const largeArc = sweepAngle > 180 ? 1 : 0;

  gaugeEl.innerHTML = `
    <svg viewBox="0 0 100 65">
      <path d="M ${cx + r * Math.cos(rad(180))},${cy + r * Math.sin(rad(180))} A ${r} ${r} 0 1 1 ${cx + r * Math.cos(rad(0))},${cy + r * Math.sin(rad(0))}"
        fill="none" stroke="var(--card-border)" stroke-width="8" stroke-linecap="round"/>
      <path d="M ${x1},${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2},${y2}"
        fill="none" stroke="${sColor}" stroke-width="8" stroke-linecap="round"/>
    </svg>
    <div class="dash-gauge-value" style="color:${sColor}">${avgScore}</div>`;

  // 分布条
  const distEl = document.getElementById("dash-dist-bars");
  const maxBucket = Math.max(...Object.values(buckets), 1);
  const distColors = { "90-100": "var(--green)", "70-89": "#3b82f6", "50-69": "var(--yellow)", "30-49": "var(--orange)", "0-29": "var(--red)" };

  distEl.innerHTML = Object.entries(buckets).map(([range, count]) => {
    const pct = (count / maxBucket) * 100;
    return `<div class="dash-dist-row">
      <span class="dash-dist-label">${range}</span>
      <div class="dash-dist-bar"><div class="dash-dist-fill" style="width:${pct}%;background:${distColors[range]}"></div></div>
      <span class="dash-dist-num">${count}</span>
    </div>`;
  }).join("");
}

// ---- 组合对比面板 ----
const COMPARE_COLORS = ["#3b82f6", "#22c55e", "#f97316", "#a855f7", "#ef4444", "#eab308", "#06b6d4", "#ec4899", "#14b8a6", "#8b5cf6"];

function renderComparePanel(dataList) {
  const panel = document.getElementById("batch-compare");
  if (!panel || dataList.length < 2) { if (panel) panel.style.display = "none"; return; }
  panel.style.display = "block";

  // 1) 叠加雷达图
  renderCompareRadar(dataList);

  // 2) 指标对比表
  renderCompareTable(dataList);
}

function renderCompareRadar(dataList) {
  const chartEl = document.getElementById("compare-radar-chart");
  const legendEl = document.getElementById("compare-legend");
  if (!chartEl) return;

  // 统一维度（按 category 聚合）
  const allCats = new Set();
  const stockDims = dataList.map(d => {
    const catMap = {};
    (d.risk_items || []).forEach(item => {
      const cat = (item.category || item.name).replace("风险", "");
      if (!catMap[cat]) catMap[cat] = [];
      catMap[cat].push(item.score);
      allCats.add(cat);
    });
    return catMap;
  });

  const dims = Array.from(allCats).slice(0, 6);
  if (dims.length < 3) { chartEl.innerHTML = ""; return; }

  const n = dims.length;
  const cx = 160, cy = 160, R = 110;
  const angleStep = (2 * Math.PI) / n;

  // 背景网格
  let gridLines = "";
  [0.25, 0.5, 0.75, 1].forEach(ratio => {
    const r = R * ratio;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const angle = -Math.PI / 2 + i * angleStep;
      pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
    }
    gridLines += `<polygon points="${pts.join(" ")}" fill="none" stroke="rgba(148,163,184,.1)" stroke-width="1"/>`;
  });

  // 轴线 + 标签
  let axes = "", labels = "";
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const ex = cx + R * Math.cos(angle);
    const ey = cy + R * Math.sin(angle);
    axes += `<line x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="rgba(148,163,184,.08)" stroke-width="1"/>`;
    const lx = cx + (R + 24) * Math.cos(angle);
    const ly = cy + (R + 24) * Math.sin(angle);
    const anchor = Math.abs(Math.cos(angle)) < 0.1 ? "middle" : (Math.cos(angle) > 0 ? "start" : "end");
    labels += `<text x="${lx}" y="${ly}" text-anchor="${anchor}" dominant-baseline="central" fill="var(--text2)" font-size="12">${dims[i]}</text>`;
  }

  // 每只股票的多边形
  let polygons = "";
  dataList.forEach((d, si) => {
    const catMap = stockDims[si];
    const color = COMPARE_COLORS[si % COMPARE_COLORS.length];
    const pts = [];
    for (let i = 0; i < n; i++) {
      const scores = catMap[dims[i]] || [50];
      const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
      const ratio = Math.max(0, Math.min(1, avg / 100));
      const angle = -Math.PI / 2 + i * angleStep;
      pts.push(`${cx + R * ratio * Math.cos(angle)},${cy + R * ratio * Math.sin(angle)}`);
    }
    polygons += `<polygon points="${pts.join(" ")}" fill="${color}22" stroke="${color}" stroke-width="2" class="compare-polygon" style="animation-delay:${si * 150}ms"/>`;
  });

  chartEl.innerHTML = `
    <svg viewBox="0 0 320 320" class="compare-radar-svg">
      ${gridLines}${axes}${polygons}${labels}
    </svg>`;

  // 图例
  legendEl.innerHTML = dataList.map((d, i) => {
    const color = COMPARE_COLORS[i % COMPARE_COLORS.length];
    return `<span class="compare-legend-item"><span class="cl-dot" style="background:${color}"></span>${esc(d.stock_name)} <b>${Math.round(d.total_score)}</b></span>`;
  }).join("");
}

function renderCompareTable(dataList) {
  const thead = document.getElementById("compare-thead");
  const tbody = document.getElementById("compare-tbody");
  if (!thead || !tbody) return;

  // 表头
  thead.innerHTML = `<tr><th>指标</th>${dataList.map((d, i) => {
    const color = COMPARE_COLORS[i % COMPARE_COLORS.length];
    return `<th style="color:${color}">${esc(d.stock_name)}</th>`;
  }).join("")}</tr>`;

  // 指标行
  const rows = [
    { label: "综合评分", key: d => Math.round(d.total_score) },
    { label: "风险等级", key: d => d.risk_level },
    { label: "量化评分", key: d => d.quant_analysis?.overall_quant_score || "--" },
    { label: "Beta", key: d => fmtNum(d.quant_analysis?.factors?.beta, 3) },
    { label: "Sharpe", key: d => fmtNum(d.quant_analysis?.risk_metrics?.sharpe_ratio, 3) },
    { label: "最大回撤", key: d => (d.quant_analysis?.risk_metrics?.max_drawdown || "--") + "%" },
    { label: "VaR 95%", key: d => (d.quant_analysis?.risk_metrics?.var_95 || "--") + "%" },
    { label: "RSI", key: d => fmtNum(d.quant_analysis?.momentum?.rsi_14, 1) },
  ];

  tbody.innerHTML = rows.map(row => {
    const vals = dataList.map(d => row.key(d));
    return `<tr><td class="ct-label">${row.label}</td>${vals.map((v, i) => {
      let cls = "";
      if (row.label === "综合评分") {
        const num = Number(v);
        cls = num >= 80 ? "ct-good" : num >= 50 ? "ct-mid" : "ct-bad";
      }
      return `<td class="${cls}">${v}</td>`;
    }).join("")}</tr>`;
  }).join("");
}

// ---- 导出报告图片 ----
function exportReport() {
  const container = document.querySelector(".result-container");
  if (!container) return;

  showToast("正在生成报告图片...");

  // 使用 Canvas 截取结果区域
  const name = document.getElementById("result-name").textContent;
  const code = document.getElementById("result-code").textContent;
  const score = document.getElementById("score-value").textContent;
  const level = document.getElementById("risk-level").textContent;
  const summary = document.getElementById("summary").textContent;

  const canvas = document.createElement("canvas");
  const W = 800, H = 480;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  // 背景
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#0b0e17");
  grad.addColorStop(1, "#111827");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // 品牌
  ctx.fillStyle = "#3b82f6";
  ctx.font = "bold 16px sans-serif";
  ctx.fillText("⚡ 投资避雷", 32, 40);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px sans-serif";
  ctx.fillText("机构级量化风控引擎", 140, 40);

  // 分割线
  ctx.strokeStyle = "rgba(37,45,68,.6)";
  ctx.beginPath();
  ctx.moveTo(32, 56);
  ctx.lineTo(W - 32, 56);
  ctx.stroke();

  // 股票名 + 代码
  ctx.fillStyle = "#e2e8f0";
  ctx.font = "bold 32px sans-serif";
  ctx.fillText(name, 32, 100);
  ctx.fillStyle = "#94a3b8";
  ctx.font = "18px sans-serif";
  ctx.fillText(code, 32 + ctx.measureText(name).width + 16, 100);

  // 评分圆环
  const ringX = 120, ringY = 210, ringR = 60;
  ctx.beginPath();
  ctx.arc(ringX, ringY, ringR, 0, Math.PI * 2);
  ctx.strokeStyle = "rgba(37,45,68,.8)";
  ctx.lineWidth = 10;
  ctx.stroke();

  const scoreNum = parseInt(score) || 0;
  const sColor = scoreColor(scoreNum);
  ctx.beginPath();
  ctx.arc(ringX, ringY, ringR, -Math.PI / 2, -Math.PI / 2 + (scoreNum / 100) * Math.PI * 2);
  ctx.strokeStyle = sColor;
  ctx.lineWidth = 10;
  ctx.lineCap = "round";
  ctx.stroke();

  ctx.fillStyle = sColor;
  ctx.font = "bold 40px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(score, ringX, ringY + 14);
  ctx.textAlign = "left";

  // 风险等级 + 摘要
  ctx.fillStyle = sColor;
  ctx.font = "bold 22px sans-serif";
  ctx.fillText(level, 220, 185);

  ctx.fillStyle = "#94a3b8";
  ctx.font = "14px sans-serif";
  const summaryLines = wrapText(ctx, summary, 540);
  summaryLines.forEach((line, i) => {
    ctx.fillText(line, 220, 215 + i * 22);
  });

  // 风险指标（取前6个）
  const items = (window._lastRiskItems || []).slice(0, 6);
  const startY = 300;
  items.forEach((item, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 32 + col * 256;
    const y = startY + row * 56;

    const badgeColor = item.score >= 80 ? "#22c55e" : item.score >= 50 ? "#eab308" : "#ef4444";
    ctx.fillStyle = badgeColor + "33";
    roundRect(ctx, x, y, 36, 28, 6);
    ctx.fill();
    ctx.fillStyle = badgeColor;
    ctx.font = "bold 13px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(Math.round(item.score), x + 18, y + 19);
    ctx.textAlign = "left";

    ctx.fillStyle = "#e2e8f0";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText(item.name, x + 44, y + 13);
    ctx.fillStyle = "#64748b";
    ctx.font = "12px sans-serif";
    ctx.fillText(item.detail.substring(0, 22), x + 44, y + 28);
  });

  // 底部水印
  ctx.fillStyle = "#475569";
  ctx.font = "11px sans-serif";
  ctx.fillText("投资避雷 · 机构级量化风控引擎 · " + new Date().toLocaleDateString("zh-CN"), 32, H - 20);
  ctx.fillText("数据仅供参考，不构成投资建议", W - 240, H - 20);

  // 下载
  canvas.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `投资避雷_${name}_${code}_${new Date().toISOString().slice(0, 10)}.png`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("报告图片已保存");
  }, "image/png");
}

function wrapText(ctx, text, maxWidth) {
  const lines = [];
  let line = "";
  for (const char of text) {
    const test = line + char;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = char;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, 3);
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// ---- 主题切换 ----
function toggleTheme() {
  const html = document.documentElement;
  const isLight = html.getAttribute("data-theme") === "light";
  const newTheme = isLight ? "dark" : "light";
  html.setAttribute("data-theme", newTheme);
  localStorage.setItem("theme", newTheme);
  document.getElementById("theme-icon").innerHTML = newTheme === "light" ? "&#9728;" : "&#9790;";
}

function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  const icon = document.getElementById("theme-icon");
  if (icon) icon.innerHTML = saved === "light" ? "&#9728;" : "&#9790;";
}

// ---- 迷你走势图 (SVG Sparkline) ----
function renderSparkline(data) {
  const section = document.getElementById("sparkline-section");
  const chartEl = document.getElementById("sparkline-chart");
  const priceEl = document.getElementById("sparkline-price");
  if (!section || !chartEl) return;

  const qa = data.quant_analysis;
  const prices = qa && qa._price_series ? qa._price_series : null;

  // 从 risk_items 提取当前价格
  const priceItem = (data.risk_items || []).find(i => i.name === "股价走势");
  let curPrice = "";
  if (priceItem && priceItem.detail) {
    const m = priceItem.detail.match(/股价([\d.]+)元/);
    if (m) curPrice = m[1] + " 元";
  }
  priceEl.textContent = curPrice;

  if (!prices || prices.length < 5) {
    section.style.display = "none";
    return;
  }
  section.style.display = "block";

  const W = 600, H = 80, pad = 4;
  const vals = prices.slice(-60);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const stepX = (W - pad * 2) / (vals.length - 1);

  const pts = vals.map((v, i) => {
    const x = pad + i * stepX;
    const y = H - pad - ((v - min) / range) * (H - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const lastY = H - pad - ((vals[vals.length - 1] - min) / range) * (H - pad * 2);
  const firstV = vals[0], lastV = vals[vals.length - 1];
  const lineColor = lastV >= firstV ? "var(--green)" : "var(--red)";
  const fillColor = lastV >= firstV ? "rgba(34,197,94,.08)" : "rgba(239,68,68,.08)";

  // 填充区域
  const fillPts = pts.join(" ") + ` ${(W - pad).toFixed(1)},${H} ${pad},${H}`;

  chartEl.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="sparkline-svg" preserveAspectRatio="none">
      <polygon points="${fillPts}" fill="${fillColor}"/>
      <polyline points="${pts.join(" ")}" fill="none" stroke="${lineColor}" stroke-width="2" stroke-linejoin="round" class="sparkline-line"/>
      <circle cx="${(W - pad).toFixed(1)}" cy="${lastY.toFixed(1)}" r="3" fill="${lineColor}" class="sparkline-dot"/>
    </svg>`;
}

// ---- 自选股管理 (支持服务端同步) ----
const FAV_KEY = "watchlist";
let _serverFavorites = null; // 缓存服务端收藏

function getWatchlist() {
  // 已登录且有服务端缓存时使用服务端数据
  if (_authState.user && _serverFavorites !== null) {
    return _serverFavorites;
  }
  try { return JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); }
  catch { return []; }
}

function isFavorited(code) {
  return getWatchlist().some(f => f.stock_code === code);
}

async function toggleFavorite() {
  const code = document.getElementById("result-code").textContent;
  const name = document.getElementById("result-name").textContent;

  if (_authState.user) {
    // 已登录：调用服务端 API
    try {
      if (isFavorited(code)) {
        await apiFetch(`${API_BASE}/user/favorites/${code}`, { method: "DELETE" });
        _serverFavorites = _serverFavorites.filter(f => f.stock_code !== code);
      } else {
        const resp = await apiFetch(`${API_BASE}/user/favorites`, {
          method: "POST",
          body: { stock_code: code, stock_name: name },
        });
        if (resp.ok) {
          const json = await resp.json();
          if (json.favorite) {
            _serverFavorites = [json.favorite, ...(_serverFavorites || [])];
          }
        }
      }
    } catch (err) {
      console.error("收藏操作失败", err);
    }
  } else {
    // 未登录：使用 localStorage
    let list = getWatchlist();
    if (isFavorited(code)) {
      list = list.filter(f => f.stock_code !== code);
    } else {
      const hist = getHistory().find(h => h.stock_code === code);
      list.unshift({
        stock_code: code,
        stock_name: name,
        total_score: hist ? hist.total_score : 0,
        risk_level: hist ? hist.risk_level : "--",
        timestamp: Date.now(),
      });
    }
    localStorage.setItem(FAV_KEY, JSON.stringify(list));
  }
  updateFavBtn(code);
  renderWatchlist();
}

function updateFavBtn(code) {
  const icon = document.getElementById("fav-icon");
  const btn = document.getElementById("fav-btn");
  if (!icon || !btn) return;
  if (isFavorited(code)) {
    icon.innerHTML = "&#9733;";
    btn.classList.add("favorited");
  } else {
    icon.innerHTML = "&#9734;";
    btn.classList.remove("favorited");
  }
}

function renderWatchlist() {
  const section = document.getElementById("watchlist-section");
  const listEl = document.getElementById("watchlist-list");
  if (!section || !listEl) return;
  const list = getWatchlist();
  if (list.length === 0) { section.style.display = "none"; return; }
  section.style.display = "block";
  listEl.innerHTML = list.map(h => {
    const cls = levelClass(h.risk_level || "良好");
    return `
      <div class="recent-card" onclick="quickScan('${esc(h.stock_code)}')">
        <div class="rc-score ${cls}">${h.total_score || 0}</div>
        <div class="rc-info">
          <span class="rc-name">${esc(h.stock_name)}</span>
          <span class="rc-code">${esc(h.stock_code)}</span>
        </div>
        <div class="rc-right">
          <span class="rc-level ${cls}">${esc(h.risk_level || "--")}</span>
          <span class="rc-fav-star">&#9733;</span>
        </div>
      </div>`;
  }).join("");
}

function clearWatchlist() {
  if (_authState.user) {
    // 服务端暂不支持批量删除，逐个删除
    _serverFavorites = [];
  }
  localStorage.removeItem(FAV_KEY);
  renderWatchlist();
}

/** 从服务端加载收藏列表 */
async function loadServerFavorites() {
  if (!_authState.user) return;
  try {
    const resp = await apiFetch(`${API_BASE}/user/favorites`);
    if (resp.ok) {
      const json = await resp.json();
      _serverFavorites = json.favorites || [];
      renderWatchlist();
    }
  } catch (err) {
    console.error("加载收藏失败", err);
  }
}

// ---- 一键分享 ----
let _currentResultData = null;

function shareReport() {
  // 显示分享选项菜单
  showShareMenu();
}

function showShareMenu() {
  const code = document.getElementById("result-code").textContent;
  if (!code) return;

  // 创建或显示分享菜单
  let menu = document.getElementById("share-menu");
  if (!menu) {
    menu = document.createElement("div");
    menu.id = "share-menu";
    menu.className = "share-menu";
    menu.innerHTML = `
      <div class="share-menu-content">
        <button onclick="copyReportText()">&#128203; 复制文字摘要</button>
        <button onclick="downloadReportImage()">&#128190; 下载报告图片</button>
        <button onclick="copyReportImage()">&#128247; 复制报告图片</button>
        <button onclick="closeShareMenu()" class="share-menu-close">取消</button>
      </div>
    `;
    document.body.appendChild(menu);
  }
  menu.style.display = "flex";
}

function closeShareMenu() {
  const menu = document.getElementById("share-menu");
  if (menu) menu.style.display = "none";
}

function copyReportText() {
  closeShareMenu();
  const name = document.getElementById("result-name").textContent;
  const code = document.getElementById("result-code").textContent;
  const score = document.getElementById("score-value").textContent;
  const level = document.getElementById("risk-level").textContent;
  const summary = document.getElementById("summary").textContent;

  const text = `【投资避雷】${name}(${code}) 风险评分报告
━━━━━━━━━━━━━━━
综合评分: ${score}/100  风险等级: ${level}
${summary}
━━━━━━━━━━━━━━━
扫描于 ${new Date().toLocaleString("zh-CN")}
投资避雷 - 机构级量化风控引擎`;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast("报告摘要已复制");
    }).catch(() => {
      fallbackCopy(text);
    });
  } else {
    fallbackCopy(text);
  }
}

async function downloadReportImage() {
  closeShareMenu();
  const code = document.getElementById("result-code").textContent;
  if (!code) return;

  showToast("正在生成报告图片...");

  try {
    const resp = await fetch(`${API_BASE}/report/${code}/image`);
    if (!resp.ok) throw new Error("生成失败");

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `投资避雷_${code}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast("报告图片已下载");
  } catch (err) {
    showToast("下载失败: " + err.message);
  }
}

async function copyReportImage() {
  closeShareMenu();
  const code = document.getElementById("result-code").textContent;
  if (!code) return;

  showToast("正在生成报告图片...");

  try {
    const resp = await fetch(`${API_BASE}/report/${code}/image`);
    if (!resp.ok) throw new Error("生成失败");

    const blob = await resp.blob();

    // 尝试使用 Clipboard API 复制图片
    if (navigator.clipboard && navigator.clipboard.write) {
      const item = new ClipboardItem({ "image/png": blob });
      await navigator.clipboard.write([item]);
      showToast("报告图片已复制到剪贴板");
    } else {
      // 降级：下载图片
      showToast("浏览器不支持复制图片，已转为下载");
      downloadReportImage();
    }
  } catch (err) {
    showToast("复制失败: " + err.message);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.cssText = "position:fixed;left:-9999px";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  showToast("报告摘要已复制到剪贴板");
}

function showToast(msg) {
  let toast = document.getElementById("toast-msg");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast-msg";
    toast.className = "toast-msg";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

// ---- 键盘事件 ----
document.getElementById("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doScan();
});
document.getElementById("search-input").addEventListener("input", onSearchInput);
document.getElementById("search-input").addEventListener("focus", (e) => {
  if (e.target.value.trim().length >= 1) onSearchInput(e);
});

// ---- 持仓组合分析 ----
const PF_KEY = "portfolio_stocks";
const PF_COLORS = ["#3b82f6","#22c55e","#f97316","#a855f7","#ef4444","#eab308","#06b6d4","#ec4899","#14b8a6","#8b5cf6"];

function getPfStocks() {
  try { return JSON.parse(localStorage.getItem(PF_KEY) || "[]"); }
  catch { return []; }
}

function savePfStocks(list) {
  localStorage.setItem(PF_KEY, JSON.stringify(list));
}

// 持仓搜索自动补全
let _pfSearchTimer = null;
const pfCodeInput = document.getElementById("pf-code");
if (pfCodeInput) {
  pfCodeInput.addEventListener("input", (e) => {
    const q = e.target.value.trim();
    if (_pfSearchTimer) clearTimeout(_pfSearchTimer);
    if (q.length < 1) { hidePfDropdown(); return; }
    _pfSearchTimer = setTimeout(() => fetchPfSearch(q), 200);
  });
  pfCodeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addPfStock();
  });
}

async function fetchPfSearch(q) {
  try {
    const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
    const json = await resp.json();
    const results = json.results || [];
    const dd = document.getElementById("pf-search-dropdown");
    if (!dd || results.length === 0) { hidePfDropdown(); return; }
    dd.innerHTML = results.map(r => `
      <div class="search-item" onmousedown="selectPfSearch('${esc(r.code)}','${esc(r.name)}')">
        <span class="si-code">${esc(r.code)}</span>
        <span class="si-name">${esc(r.name)}</span>
      </div>
    `).join("");
    dd.style.display = "block";
  } catch (_) { hidePfDropdown(); }
}

function selectPfSearch(code, name) {
  document.getElementById("pf-code").value = code;
  hidePfDropdown();
  document.getElementById("pf-shares").focus();
}

function hidePfDropdown() {
  const dd = document.getElementById("pf-search-dropdown");
  if (dd) dd.style.display = "none";
}

function addPfStock() {
  const codeInput = document.getElementById("pf-code");
  const sharesInput = document.getElementById("pf-shares");
  const code = (codeInput.value.trim().match(/^(\d{6})/) || [])[1];
  const shares = parseInt(sharesInput.value) || 0;

  if (!code) { codeInput.focus(); showToast("请输入6位股票代码"); return; }
  if (shares <= 0) { sharesInput.focus(); showToast("请输入持仓数量"); return; }

  const list = getPfStocks();
  const existing = list.find(s => s.code === code);
  if (existing) {
    existing.shares = shares;
    existing.scanned = false;
  } else {
    list.push({ code, name: "", shares, scanned: false, score: null, risk_level: null, data: null });
  }
  savePfStocks(list);

  codeInput.value = "";
  sharesInput.value = "";
  codeInput.focus();
  hidePfDropdown();
  renderPfTable();
}

function removePfStock(code) {
  const list = getPfStocks().filter(s => s.code !== code);
  savePfStocks(list);
  renderPfTable();
  // 如果清空了，隐藏结果
  if (list.length === 0) {
    const result = document.getElementById("pf-result");
    if (result) result.style.display = "none";
  }
}

function clearPortfolio() {
  localStorage.removeItem(PF_KEY);
  renderPfTable();
  const result = document.getElementById("pf-result");
  if (result) result.style.display = "none";
}

function renderPfTable() {
  const wrap = document.getElementById("pf-holdings-wrap");
  const tbody = document.getElementById("pf-tbody");
  const countEl = document.getElementById("pf-holdings-count");
  if (!wrap || !tbody) return;

  const list = getPfStocks();
  if (list.length === 0) { wrap.style.display = "none"; return; }
  wrap.style.display = "block";
  countEl.textContent = list.length;

  const totalShares = list.reduce((s, item) => s + item.shares, 0);

  tbody.innerHTML = list.map((s, i) => {
    const pct = totalShares > 0 ? ((s.shares / totalShares) * 100).toFixed(1) : "0";
    const scoreTd = s.scanned && s.score != null
      ? `<span style="color:${scoreColor(s.score)};font-weight:700">${Math.round(s.score)}</span>`
      : '<span style="color:var(--text2)">--</span>';
    const levelTd = s.scanned && s.risk_level
      ? `<span class="rc-level ${levelClass(s.risk_level)}">${esc(s.risk_level)}</span>`
      : '<span style="color:var(--text2)">--</span>';
    return `<tr>
      <td class="pf-code-cell">${esc(s.code)}</td>
      <td>${esc(s.name || "未扫描")}</td>
      <td>${s.shares.toLocaleString()}</td>
      <td class="pf-weight-cell">${pct}%</td>
      <td class="pf-score-cell">${scoreTd}</td>
      <td>${levelTd}</td>
      <td><button class="pf-remove-btn" onclick="removePfStock('${s.code}')" title="删除">&times;</button></td>
    </tr>`;
  }).join("");
}

// 预设组合
function loadPfPreset(type) {
  const presets = {
    balanced: [
      { code: "600519", shares: 100 },
      { code: "601398", shares: 2000 },
      { code: "300750", shares: 200 },
      { code: "000001", shares: 1000 },
      { code: "002594", shares: 100 },
    ],
    aggressive: [
      { code: "300750", shares: 500 },
      { code: "002594", shares: 300 },
      { code: "000858", shares: 400 },
      { code: "601012", shares: 600 },
    ],
    defensive: [
      { code: "601398", shares: 3000 },
      { code: "600036", shares: 1500 },
      { code: "601318", shares: 500 },
      { code: "600519", shares: 50 },
    ],
  };
  const items = presets[type] || [];
  const list = items.map(p => ({ code: p.code, name: "", shares: p.shares, scanned: false, score: null, risk_level: null, data: null }));
  savePfStocks(list);
  renderPfTable();
  showToast(`已导入${list.length}只股票`);
}

// 分析组合
async function analyzePortfolio() {
  const list = getPfStocks();
  if (list.length === 0) { showToast("请先添加持仓"); return; }

  const progressEl = document.getElementById("pf-progress");
  const progressFill = document.getElementById("pf-progress-fill");
  const progressText = document.getElementById("pf-progress-text");
  const progressNum = document.getElementById("pf-progress-num");
  progressEl.style.display = "block";

  for (let i = 0; i < list.length; i++) {
    const s = list[i];
    progressFill.style.width = ((i) / list.length * 100) + "%";
    progressText.textContent = `正在扫描 ${s.code} ...`;
    progressNum.textContent = `${i}/${list.length}`;

    if (s.scanned && s.data) continue; // 已有数据跳过

    try {
      const resp = await fetch(`${API_BASE}/scan/${encodeURIComponent(s.code)}`);
      if (!resp.ok) throw new Error("请求失败");
      const json = await resp.json();
      if (json.success && json.data) {
        s.name = json.data.stock_name || s.code;
        s.score = json.data.total_score;
        s.risk_level = json.data.risk_level;
        s.scanned = true;
        s.data = json.data;
      } else {
        s.scanned = true;
        s.score = null;
        s.risk_level = "未知";
      }
    } catch (e) {
      s.scanned = true;
      s.score = null;
      s.risk_level = "失败";
    }
  }

  progressFill.style.width = "100%";
  progressText.textContent = "分析完成";
  progressNum.textContent = `${list.length}/${list.length}`;
  savePfStocks(list);
  renderPfTable();

  setTimeout(() => { progressEl.style.display = "none"; }, 1500);

  // 渲染组合分析结果
  renderPortfolioResult(list);
}

function renderPortfolioResult(list) {
  const validStocks = list.filter(s => s.scanned && s.score != null);
  if (validStocks.length === 0) { showToast("无有效扫描结果"); return; }

  const resultEl = document.getElementById("pf-result");
  resultEl.style.display = "block";

  const totalShares = validStocks.reduce((s, i) => s + i.shares, 0);

  // 1) 加权评分
  let weightedScore = 0;
  validStocks.forEach(s => {
    const w = s.shares / totalShares;
    weightedScore += (s.score || 0) * w;
  });
  weightedScore = Math.round(weightedScore);

  const level = weightedScore >= 80 ? "安全" : weightedScore >= 60 ? "注意" : weightedScore >= 40 ? "警惕" : "危险";
  const cls = levelClass(level);
  const sColor = scoreColor(weightedScore);

  // HHI 集中度指数
  const hhi = validStocks.reduce((s, i) => {
    const w = i.shares / totalShares;
    return s + w * w;
  }, 0);
  const diversification = Math.round((1 - hhi) * 100);

  // 加权Beta / Sharpe / MaxDD
  let wBeta = 0, wSharpe = 0, wMDD = 0, hasQuant = false;
  validStocks.forEach(s => {
    const w = s.shares / totalShares;
    const qa = s.data?.quant_analysis;
    if (qa && qa.factors && qa.factors.beta != null) {
      hasQuant = true;
      wBeta += (qa.factors.beta || 0) * w;
      wSharpe += (qa.risk_metrics?.sharpe_ratio || 0) * w;
      wMDD += (qa.risk_metrics?.max_drawdown || 0) * w;
    }
  });

  // 危险/安全统计
  const dangerCount = validStocks.filter(s => s.risk_level === "危险" || s.risk_level === "警惕").length;
  const safeCount = validStocks.filter(s => s.risk_level === "安全" || s.risk_level === "良好").length;

  // Score panel
  const circumference = 2 * Math.PI * 48;
  const offset = circumference * (1 - weightedScore / 100);
  document.getElementById("pf-score-panel").innerHTML = `
    <div class="pf-score-ring-wrap">
      <svg class="pf-score-ring" viewBox="0 0 108 108">
        <circle cx="54" cy="54" r="48" fill="none" stroke="var(--card-border)" stroke-width="7"/>
        <circle cx="54" cy="54" r="48" fill="none" stroke="${sColor}" stroke-width="7"
          stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
          style="transition:stroke-dashoffset 1s ease"/>
      </svg>
      <div class="pf-score-value" style="color:${sColor}">${weightedScore}</div>
    </div>
    <div class="pf-score-meta">
      <div class="pf-score-label">组合加权评分</div>
      <div class="pf-score-level ${cls}">${level}</div>
      <div class="pf-score-stats">
        <div class="pf-stat">
          <span class="pf-stat-label">持仓数</span>
          <span class="pf-stat-value">${validStocks.length}</span>
        </div>
        <div class="pf-stat">
          <span class="pf-stat-label">分散度</span>
          <span class="pf-stat-value" style="color:${diversification >= 60 ? 'var(--green)' : diversification >= 30 ? 'var(--yellow)' : 'var(--red)'}">${diversification}%</span>
        </div>
        <div class="pf-stat">
          <span class="pf-stat-label">风险股</span>
          <span class="pf-stat-value" style="color:${dangerCount > 0 ? 'var(--red)' : 'var(--green)'}">${dangerCount}</span>
        </div>
        <div class="pf-stat">
          <span class="pf-stat-label">安全股</span>
          <span class="pf-stat-value" style="color:var(--green)">${safeCount}</span>
        </div>
      </div>
    </div>`;

  // 2) 持仓配比环形图 (SVG Donut)
  renderPfDonut(validStocks, totalShares);

  // 3) 组合指标
  const metricsEl = document.getElementById("pf-metrics-section");
  metricsEl.innerHTML = `
    <div class="pf-metric-card">
      <h4>组合风险指标</h4>
      <div class="pf-metric-rows">
        ${hasQuant ? `
          <div class="pf-metric-row"><span class="pf-ml">加权 Beta</span><span class="pf-mv" style="color:${wBeta > 1.5 ? 'var(--red)' : wBeta > 1 ? 'var(--yellow)' : 'var(--green)'}">${wBeta.toFixed(3)}</span></div>
          <div class="pf-metric-row"><span class="pf-ml">加权 Sharpe</span><span class="pf-mv" style="color:${wSharpe > 0.5 ? 'var(--green)' : wSharpe > 0 ? 'var(--yellow)' : 'var(--red)'}">${wSharpe.toFixed(3)}</span></div>
          <div class="pf-metric-row"><span class="pf-ml">加权最大回撤</span><span class="pf-mv" style="color:var(--orange)">${wMDD.toFixed(2)}%</span></div>
        ` : '<div class="pf-metric-row"><span class="pf-ml">量化数据不足</span><span class="pf-mv">--</span></div>'}
        <div class="pf-metric-row"><span class="pf-ml">HHI 集中度</span><span class="pf-mv">${(hhi * 10000).toFixed(0)}</span></div>
      </div>
    </div>
    <div class="pf-metric-card">
      <h4>持仓统计</h4>
      <div class="pf-metric-rows">
        <div class="pf-metric-row"><span class="pf-ml">总持仓</span><span class="pf-mv">${totalShares.toLocaleString()} 股</span></div>
        <div class="pf-metric-row"><span class="pf-ml">最高评分</span><span class="pf-mv" style="color:var(--green)">${Math.round(Math.max(...validStocks.map(s => s.score)))}</span></div>
        <div class="pf-metric-row"><span class="pf-ml">最低评分</span><span class="pf-mv" style="color:${Math.min(...validStocks.map(s => s.score)) < 50 ? 'var(--red)' : 'var(--yellow)'}">${Math.round(Math.min(...validStocks.map(s => s.score)))}</span></div>
        <div class="pf-metric-row"><span class="pf-ml">最大权重</span><span class="pf-mv">${(Math.max(...validStocks.map(s => s.shares)) / totalShares * 100).toFixed(1)}%</span></div>
      </div>
    </div>`;

  // 4) 风险分解
  renderPfRiskBreakdown(validStocks, totalShares);
}

function renderPfDonut(stocks, totalShares) {
  const chartEl = document.getElementById("pf-alloc-chart");
  if (!chartEl) return;

  const cx = 90, cy = 90, R = 70, strokeW = 28;
  const circumference = 2 * Math.PI * R;
  let accumulated = 0;

  let arcs = "";
  let legend = "";

  stocks.forEach((s, i) => {
    const pct = s.shares / totalShares;
    const dashLen = circumference * pct;
    const dashGap = circumference - dashLen;
    const rotation = accumulated * 360 - 90;
    const color = PF_COLORS[i % PF_COLORS.length];

    arcs += `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${color}" stroke-width="${strokeW}"
      stroke-dasharray="${dashLen} ${dashGap}"
      transform="rotate(${rotation} ${cx} ${cy})"
      style="transition: all .6s ease; animation-delay:${i * 100}ms"/>`;

    legend += `<div class="pf-alloc-item">
      <span class="pf-alloc-dot" style="background:${color}"></span>
      <span class="pf-alloc-name">${esc(s.name || s.code)}</span>
      <span class="pf-alloc-pct">${(pct * 100).toFixed(1)}%</span>
    </div>`;

    accumulated += pct;
  });

  chartEl.innerHTML = `
    <svg viewBox="0 0 180 180" class="pf-donut-svg">${arcs}</svg>
    <div class="pf-alloc-legend">${legend}</div>`;
}

function renderPfRiskBreakdown(stocks, totalShares) {
  const el = document.getElementById("pf-risk-breakdown");
  if (!el) return;

  const sorted = [...stocks].sort((a, b) => (a.score || 0) - (b.score || 0));

  el.innerHTML = `
    <h4>风险分解 (按评分排序)</h4>
    <div class="pf-risk-bar-wrap">
      ${sorted.map((s, i) => {
        const score = Math.round(s.score || 0);
        const color = scoreColor(score);
        const w = (s.shares / totalShares * 100).toFixed(1);
        return `<div class="pf-risk-bar-item">
          <span class="pf-risk-bar-name">${esc(s.name || s.code)}</span>
          <div class="pf-risk-bar-track">
            <div class="pf-risk-bar-fill" style="width:${score}%;background:${color}"></div>
          </div>
          <span class="pf-risk-bar-score" style="color:${color}">${score}</span>
        </div>`;
      }).join("")}
    </div>`;
}

// ---- 键盘快捷键 ----
function openKbd() { document.getElementById("kbd-overlay").style.display = "flex"; }
function closeKbd() { document.getElementById("kbd-overlay").style.display = "none"; }

document.addEventListener("keydown", (e) => {
  // 忽略在输入框中的按键
  const tag = (e.target.tagName || "").toLowerCase();
  const inInput = tag === "input" || tag === "textarea" || tag === "select";

  if (e.key === "Escape") {
    // 关闭弹窗
    if (document.getElementById("auth-modal").style.display === "flex") { closeAuthModal(); return; }
    if (document.getElementById("kbd-overlay").style.display === "flex") { closeKbd(); return; }
    if (document.getElementById("vip-modal").style.display === "flex") { closeVIPModal(); return; }
    hideDropdown();
    hidePfDropdown();
    return;
  }

  if (inInput) return;

  if (e.key === "/" || (e.key === "k" && (e.ctrlKey || e.metaKey))) {
    e.preventDefault();
    showHome();
    setTimeout(() => document.getElementById("search-input").focus(), 100);
    return;
  }
  if (e.key === "?" || (e.shiftKey && e.key === "/")) { openKbd(); return; }
  if (e.key === "b" || e.key === "B") { showBatchPage(); return; }
  if (e.key === "p" || e.key === "P") { showPortfolioPage(); return; }
  if (e.key === "h" || e.key === "H") { showHome(); return; }
});
