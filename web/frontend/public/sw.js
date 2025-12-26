// SAHTD PWA Service Worker - Minimal caching for offline support
const CACHE_NAME = 'sahtd-v1';
const STATIC_ASSETS = [
    '/',
    '/manifest.json',
    '/vite.svg'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            );
        })
    );
    self.clients.claim();
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip WebSocket and API calls
    if (url.protocol === 'ws:' || url.protocol === 'wss:') {
        return;
    }
    if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws') ||
        url.pathname.startsWith('/cmd') || url.pathname.startsWith('/auth') ||
        url.pathname.startsWith('/guard')) {
        return;
    }

    // Network-first for HTML (to get latest app version)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => caches.match('/'))
        );
        return;
    }

    // Cache-first for static assets
    event.respondWith(
        caches.match(event.request).then((cached) => {
            return cached || fetch(event.request);
        })
    );
});
