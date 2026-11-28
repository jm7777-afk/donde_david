const CACHE_NAME = "donde-david-pwa-v36";
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
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS_TO_CACHE))
      .catch(err => console.warn("[SW] Cache preload warning:", err))
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(cacheNames => Promise.all(
        cacheNames
          .filter(name => name.startsWith("donde-david-pwa-") && name !== CACHE_NAME)
          .map(name => {
            console.log("[SW] Deleting obsolete cache:", name);
            return caches.delete(name);
          })
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

  // Para archivos JS, CSS y HTML: Estrategia Network-First obligatoria para reflejar cambios en tiempo real
  if (url.pathname.endsWith(".js") || url.pathname.endsWith(".css") || url.pathname.endsWith(".html")) {
    event.respondWith(
      fetch(request, { cache: "no-store" }).then(response => {
        if (response.ok) {
          const responseCopy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, responseCopy));
        }
        return response;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // Para otros activos estáticos (imágenes, logos): Cache-First con fallback a red
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) return cachedResponse;
      return fetch(request).then(response => {
        if (response.ok) {
          const responseCopy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, responseCopy));
        }
        return response;
      });
    })
  );
});
