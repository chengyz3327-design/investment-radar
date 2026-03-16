const CACHE_NAME = "ir-v1";
const PRECACHE = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

// 安装：预缓存核心资源
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 拦截请求：网络优先，失败回退缓存
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API 请求：永远走网络，不缓存
  if (url.pathname.startsWith("/scan") ||
      url.pathname.startsWith("/auth") ||
      url.pathname.startsWith("/user") ||
      url.pathname.startsWith("/batch") ||
      url.pathname.startsWith("/portfolio") ||
      url.pathname.startsWith("/vip") ||
      url.pathname.startsWith("/admin")) {
    return;
  }

  // 静态资源 + 页面：网络优先，失败用缓存
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
