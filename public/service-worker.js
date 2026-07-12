const CACHE_NAME = 'phakts-studio-v35';
const APP_SHELL = [
  './PHAKTS\u00b7STUDIO.html',
  './manifest.webmanifest',
  './icons/icon-192.svg',
  './icons/icon-512.svg',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
  './screenshots/desktop.png',
  './screenshots/mobile.png',
  './vendor/exceljs.min.js',
  './vendor/mammoth.browser.min.js',
  './vendor/ocrad.js',
  './vendor/pdf.min.mjs',
  './vendor/pdf.worker.min.mjs'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys
        .filter(key => key !== CACHE_NAME)
        .map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Skip API calls - never cache them
  if (url.pathname.startsWith('/api/')) return;

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(event.request, { ignoreSearch: true });

    // Navigation: network-first with offline fallback
    if (event.request.mode === 'navigate') {
      try {
        const resp = await fetch(event.request);
        if (resp.ok) cache.put(event.request, resp.clone());
        return resp;
      } catch {
        return cached
          || cache.match('./PHAKTS\u00b7STUDIO.html')
          || cache.match('./PHAKTS%C2%B7STUDIO.html');
      }
    }

    // Other assets: cache-first with network fallback
    if (cached) return cached;

    try {
      const resp = await fetch(event.request);
      if (resp.ok) cache.put(event.request, resp.clone());
      return resp;
    } catch {
      return Response.error();
    }
  })());
});
