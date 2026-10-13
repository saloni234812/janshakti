/**
 * JanaShakti Service Worker
 * Provides offline caching for PWA assets, content/rivers.json, audio prompts,
 * and handles background offline capabilities.
 */

const CACHE_NAME = 'janashakti-v1.0';

const PRECACHE_ASSETS = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/map.svg',
  '/static/content/rivers.json',
  '/static/audio/M1.opus'
];

// Install Event - Precache core app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Precaching App Shell & Content');
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[ServiceWorker] Precache partial error (will fetch on demand):', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate Event - Clean up stale caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[ServiceWorker] Removing obsolete cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event - Hybrid Caching Strategy
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // If request is for an API endpoint (/api/)
  if (url.pathname.startsWith('/api/')) {
    // Network-first with graceful offline fallback
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // If GET API request, keep a clone in cache for offline viewing
          if (event.request.method === 'GET' && response.status === 200) {
            const respClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, respClone));
          }
          return response;
        })
        .catch(async () => {
          // Fallback to cached API response if available
          const cachedResponse = await caches.match(event.request);
          if (cachedResponse) {
            return cachedResponse;
          }
          // Return synthetic offline response
          return new Response(
            JSON.stringify({
              offline: true,
              message: 'Offline mode active. Request queued locally.'
            }),
            {
              headers: { 'Content-Type': 'application/json' },
              status: 503
            }
          );
        })
    );
    return;
  }

  // Cache-first for App Shell, Static Files, Assets, and SVG
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });
        return networkResponse;
      });
    })
  );
});
