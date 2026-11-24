const ASSET_CACHE_NAME = "prisonbot-assets-v1";

function isImmutableAssetRequest(url) {
  const path = url.pathname || "";
  if (path.includes("/api/v1/assets/proxy")) return true;
  if (path.includes("/static/assets/icons/")) return true;
  if (path.includes("/static/assets/rooms/")) return true;
  return false;
}

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("prisonbot-assets-") && k !== ASSET_CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (!isImmutableAssetRequest(url)) {
    // Network-Only for API, SSE, HTML, JS, CSS, sw.js
    return;
  }

  event.respondWith(
    caches.open(ASSET_CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(req);
      if (cached) {
        return cached;
      }
      const resp = await fetch(req);
      if (resp && resp.ok && resp.status === 200) {
        cache.put(req, resp.clone()).catch(() => {});
      }
      return resp;
    })
  );
});
