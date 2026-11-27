/* Glovebox · guarda la app en el móvil para que abra al instante y sin internet */
const V="cochera-be27610e",FONTS="cochera-fuentes-1",SHELL=['./', './index.html', './car-mask.webp', './car-top.webp', './moto-top.webp', './apple-touch-icon.png', './icon-192.png', './icon-512.png', './manifest.webmanifest'];
self.addEventListener("install",e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith("cochera-")&&k!==V&&k!==FONTS).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",e=>{
 const r=e.request;if(r.method!=="GET")return;const u=new URL(r.url);
 if(u.hostname==="fonts.googleapis.com"||u.hostname==="fonts.gstatic.com"){e.respondWith(caches.open(FONTS).then(c=>c.match(r).then(m=>m||fetch(r).then(x=>{if(x.ok||x.type==="opaque")c.put(r,x.clone());return x}))));return}
 if(u.origin!==location.origin||!u.pathname.includes("/cochera/"))return;
 if(r.mode==="navigate"){e.respondWith(fetch(r,{cache:"no-cache"}).then(x=>{if(x.ok){const cp=x.clone();caches.open(V).then(c=>c.put("./index.html",cp))}return x}).catch(()=>caches.match("./index.html")));return}
 e.respondWith(caches.match(r).then(m=>m||fetch(r).then(x=>{if(x.ok){const cp=x.clone();caches.open(V).then(c=>c.put(r,cp))}return x})));
});
