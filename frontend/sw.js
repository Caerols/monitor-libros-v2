const CACHE_NAME = 'matriz-cache-v2';
const urlsToCache = [
  '/',
  '/index.html',
  '/biblioteca.html',
  '/estadisticas.html',
  '/logros.html',
  '/css/style.css',
  '/css/biblioteca.css'
];

// Instalación del Service Worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

// Interceptar peticiones de red
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Devuelve la versión en caché si existe, si no, va a la red
        return response || fetch(event.request);
      })
  );
});