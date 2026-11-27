const ASSET_CACHE_NAME = "prisonbot-assets-v26";

function isImmutableAssetRequest(url) {
  const path = url.pathname || "";
  if (path.includes("/assets_cache/")) return true;
  if (path.includes("/api/v1/assets/proxy")) return true;
  if (path.includes("/static/assets/icons/")) return true;
  if (path.includes("/static/assets/rooms/")) return true;
  return false;
}

function isCacheableAssetResponse(url, resp) {
  if (!resp || !resp.ok || resp.status !== 200) return false;
  const ctype = (resp.headers.get("content-type") || "").toLowerCase();
  if ((url.pathname || "").includes("assets/proxy")) {
    if (ctype.startsWith("image/") || ctype.startsWith("application/octet-stream") || ctype.startsWith("text/plain")) {
      return true;
    }
    if (ctype.startsWith("application/json")) {
      const targetPath = url.searchParams.get("path") || "";
      return targetPath.toLowerCase().endsWith(".json");
    }
    return false;
  }
  return !ctype.includes("text/html");
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
        if (isCacheableAssetResponse(url, cached)) {
          return cached;
        }
        await cache.delete(req).catch(() => {});
      }
      const resp = await fetch(req);
      if (isCacheableAssetResponse(url, resp)) {
        cache.put(req, resp.clone()).catch(() => {});
      }
      return resp;
    })
  );
});
