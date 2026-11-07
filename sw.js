/**
 * =============================================================================
 *             🌌 ANDROMEDA PWA SERVICE WORKER & OFFLINE CACHE
 * =============================================================================
 * Manages:
 *  1. Offline shell caching for 100% host-independent execution
 *  2. Model weight shard persistence in CacheStorage
 *  3. Background pre-warming when on the landing page
 * =============================================================================
 */

const CACHE_NAME = 'andromeda-shell-v1';
const WEIGHTS_CACHE_NAME = 'andromeda-model-weights-v1';

const STATIC_SHELL = [
  './',
  './index.html',
  './app.html',
  './landing.html',
  './manifest.webmanifest',
  './favicon.svg',
  './icons.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_SHELL).catch((err) => {
        console.warn('[Andromeda SW]: Partial shell cache failed:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key !== WEIGHTS_CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 1. Bypass WebSocket connections and live API endpoints
  if (url.pathname.startsWith('/ws/') || url.pathname.startsWith('/api/')) {
    return;
  }

  // 2. Model weight requests: Cache-First for persistent local RAM/disk caching
  if (url.pathname.includes('/models/') || url.pathname.includes('/_andromeda_model_')) {
    event.respondWith(
      caches.open(WEIGHTS_CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const netResponse = await fetch(event.request);
        if (netResponse.ok) {
          cache.put(event.request, netResponse.clone());
        }
        return netResponse;
      })
    );
    return;
  }

  // 3. Static Assets: Stale-While-Revalidate
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200 && event.request.method === 'GET') {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseToCache);
            });
          }
          return networkResponse;
        })
        .catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});

// Background message handler for landing page pre-caching
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'PRECACHE_MODEL') {
    const modelId = event.data.modelId;
    console.log(`[Andromeda SW]: Background pre-cache initiated for model ${modelId}`);
    // Register background sync or pre-fetch shard manifest
  }
});
