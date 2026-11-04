const CACHE_NAME = "donde-david-pwa-v10";
const ASSETS_TO_CACHE = [
  "/static/index.html",
  "/static/cliente/app.html",
  "/static/css/global.css",
  "/static/css/toon-theme.css",
  "/static/css/index.css",
  "/static/js/auth.js",
  "/static/js/websocket.js",
  "/static/js/cliente-toon.js",
  "/static/js/appShell.js",
  "/static/img/logo.png",
  "/static/images/logo-donde-david.jpg"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS_TO_CACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(cacheNames => Promise.all(
        cacheNames
          .filter(name => name.startsWith("donde-david-pwa-") && name !== CACHE_NAME)
          .map(name => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    request.method !== "GET"
    || url.origin !== self.location.origin
    || !url.pathname.startsWith("/static/")
    || url.pathname.startsWith("/static/api/")
  ) return;

  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then(cachedResponse => {
      if (cachedResponse) return cachedResponse;
      return fetch(request).then(response => {
        if (response.ok) {
          const responseCopy = response.clone();
          return caches.open(CACHE_NAME)
            .then(cache => cache.put(request, responseCopy))
            .then(() => response);
        }
        return response;
      });
    })
  );
});
