// Offline, deliberately.
//
// Before this, a reload with the network down happened to work when the HTTP
// cache still held the 9 MB of Pyodide, and happened not to when it did not.
// "Happened to" is not a feature: Vimny does all its computing in the tab and
// keeps its saves in this browser, so there is no honest reason it should need
// a server to start. After one visit, it does not.
//
// Two strategies, split by what the file is:
//
//   vendor/    cache-first. Pyodide, xterm.js, the wheels, the font subsets —
//              9 MB that changes only when web/build.sh runs. Serving it from
//              disk is the whole speed win, and going to the network first to
//              be told it has not changed would throw that away.
//   everything else  network-first, falling back to cache. index.html, app.js,
//              worker.js and py/boot.py are small and are what actually gets
//              edited; a stale one of those against a fresh wheel is the kind
//              of bug that wastes an afternoon. Online you always get today's.
//
// Freshness across builds is a whole-cache swap rather than per-file cleverness:
// build.sh stamps vendor/manifest.json with a build id, the page hands it over,
// and any cache under a different id is deleted. A rebuild costs one refetch of
// everything, which is the right trade for never reasoning about half-stale
// mixtures of old wheel and new boot code.

const PREFIX = 'vimny-';

// The app shell — enough to start the game with the network unplugged. The
// vendor files are not listed: they arrive through the fetch handler on the
// first visit, which is also the visit that has a network.
const SHELL = [
  './',
  'index.html',
  'app.js',
  'worker.js',
  'py/boot.py',
  'vendor/xterm/xterm.js',
  'vendor/xterm/xterm.css',
  'vendor/xterm/addon-fit.js',
  'vendor/fonts/fonts.css',
  // Named explicitly, unlike the rest of vendor/: a font requested by CSS on
  // the first visit can be served from the browser's own font cache without
  // ever reaching this worker, so waiting for a fetch to cache would leave the
  // runes to a fallback the moment the network went away.
  'vendor/fonts/DejaVuSansMono.woff2',
  'vendor/fonts/Symbola.woff2',
  'vendor/fonts/DejaVuSans.woff2',
  'vendor/manifest.json',
];

let cacheName = null;      // set from the build id; nothing is cached before it

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

// The page reads vendor/manifest.json anyway, so it tells us the build id
// rather than making this worker fetch the same file a second time.
self.addEventListener('message', (event) => {
  const { type, build } = event.data || {};
  if (type !== 'build' || !build) return;
  cacheName = PREFIX + build;
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith(PREFIX) && name !== cacheName) await caches.delete(name);
    }
    const cache = await caches.open(cacheName);
    // Individually, not addAll: one 404 in the list would otherwise reject the
    // whole precache and leave the visit with no offline copy at all.
    await Promise.all(SHELL.map((url) =>
      cache.add(new Request(url, { cache: 'reload' })).catch(() => {})));
  })());
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (cacheName && response.ok) {
    (await caches.open(cacheName)).put(request, response.clone());
  }
  return response;
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (cacheName && response.ok) {
      (await caches.open(cacheName)).put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // Only plain same-origin reads. A range request (which is how a browser asks
  // for part of a large file) must reach the network to be answered honestly.
  if (request.method !== 'GET' || request.headers.has('range')) return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(url.pathname.includes('/vendor/')
    ? cacheFirst(request)
    : networkFirst(request));
});
