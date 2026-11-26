/* Patea · guarda la app y las calles en el móvil para que abra al instante */
const V="patea-app-8";const TILES="patea-tiles-1";const DATAC="patea-datos-1";const MAXT=2500;
const SHELL=["./","./index.html","./maplibre-gl.js","./maplibre-gl.css","./icon-180.png","./icon-512.png","./patea-icono.png","./manifest.json"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V&&k!==TILES&&k!==DATAC).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
let puts=0;
function trim(){caches.open(TILES).then(c=>c.keys().then(ks=>{if(ks.length>MAXT)return Promise.all(ks.slice(0,ks.length-MAXT).map(k=>c.delete(k)));}));}
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;const u=new URL(r.url);
  // La propia app: primero internet (para tener siempre la última versión), si tarda o no hay, la guardada
  if(u.origin===location.origin&&(r.mode==="navigate"||u.pathname.endsWith("/")||u.pathname.endsWith("index.html"))){
    e.respondWith(new Promise(res=>{let done=false;const cached=()=>caches.match("./index.html").then(m=>m||caches.match("./"));
      const t=setTimeout(()=>{cached().then(m=>{if(m&&!done){done=true;res(m);}});},2500);
      fetch(r).then(n=>{if(n&&n.ok){const cp=n.clone();caches.open(V).then(c=>c.put("./index.html",cp));}clearTimeout(t);if(!done){done=true;res(n);}})
        .catch(()=>{clearTimeout(t);cached().then(m=>{if(!done){done=true;res(m||Response.error());}});});}));return;}
  // Resto de archivos de la app: los guardados, y se actualizan por detrás
  if(u.origin===location.origin){e.respondWith(caches.match(r).then(m=>{const n=fetch(r).then(x=>{if(x&&x.ok){const cp=x.clone();caches.open(V).then(c=>c.put(r,cp));}return x;}).catch(()=>m);return m||n;}));return;}
  // Datos propios de sitios (rama «datos»): lo guardado al momento y se refresca por detrás
  if((u.hostname==="cdn.jsdelivr.net"||u.hostname==="raw.githubusercontent.com")&&u.pathname.indexOf("datos")>=0){e.respondWith(caches.open(DATAC).then(c=>c.match(r).then(m=>{const n=fetch(r).then(x=>{if(x&&(x.ok||x.status===404)&&x.type!=="opaque"){if(x.ok)c.put(r,x.clone());}return x;}).catch(()=>m||Response.error());return m||n;})));return;}
  // Calles y estilo del mapa (OpenFreeMap): lo guardado al momento y se refresca por detrás
  if(/(^|\.)openfreemap\.org$/.test(u.hostname)){e.respondWith(caches.open(TILES).then(c=>c.match(r).then(m=>{const n=fetch(r).then(x=>{if(x&&x.ok){c.put(r,x.clone());if(++puts%60===0)trim();}return x;}).catch(()=>m);return m||n;})));return;}
});
