const CACHE_NAME = "rent-app-v2";

const urlsToCache = [
  "/",
  "/login",
  "/dashboard",
  "/static/style.css"
];

// INSTALL
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// FETCH
self.addEventListener("fetch", event => {
  event.respondWith(
    fetch(event.request)
      .catch(() => caches.match(event.request))
      .then(response => response || caches.match("/offline"))
  );
});