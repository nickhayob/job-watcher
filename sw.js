/* Service worker: online, always ask the network; offline, serve the last copy. */
const CACHE = "jobwatcher-v3";
const SHELL = [
  "./",
  "index.html",
  "browse.html",
  "market.html",
  "map.html",
  "resume.html",
  "resume-calc.js",
  "style.css",
  "app.js",
  "charts.js",
  "market-calc.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "data/status.json",
  "data/history.csv",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        cache
          .addAll(SHELL)
          // map coordinates are an extra: a missing file must not stop the install
          .then(() => cache.add("data/geo.json").catch(() => {}))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    // Online: go to the network (skipping the browser's own cache) and keep a copy.
    fetch(new Request(request.url, { cache: "no-cache", credentials: "same-origin" }))
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request.url, copy));
        }
        return response;
      })
      // Offline: the last copy of this file, or the Today page for any page request.
      .catch(() =>
        caches
          .match(request.url, { ignoreSearch: true })
          .then((cached) => cached || (request.mode === "navigate" ? caches.match("index.html") : Response.error()))
      )
  );
});
