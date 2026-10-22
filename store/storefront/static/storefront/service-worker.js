'use strict';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith('sabzi-shell-')).map((key) => caches.delete(key))
  )));
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    // Never cache personalized HTML, orders or account pages on a shared device.
    event.respondWith(fetch(request).catch(() => new Response(
      '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>اتصال برقرار نیست</title><body style="font-family:Tahoma,sans-serif;background:#f4f8f5;color:#1b3028;padding:32px;line-height:2"><h1>اتصال به اینترنت برقرار نیست</h1><p>برای مشاهده فروشگاه سبزی، اتصال اینترنت را بررسی کنید و دوباره تلاش کنید.</p><button onclick="location.reload()" style="font:inherit;padding:10px 20px">تلاش دوباره</button></body></html>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } }
    )));
  }
});
