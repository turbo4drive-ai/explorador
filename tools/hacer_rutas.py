#!/usr/bin/env python3
"""Patea · Modo Monte. Convierte los senderos de OpenStreetMap en archivos pequeños para la app.

Entradas (las genera osmium en la tarea nocturna):
  vias.geojsonseq   geometría de los caminos que forman parte de alguna ruta (id «w123»)
  rel.opl           las relaciones route=hiking/foot en formato OPL (miembros y etiquetas)
  monte.geojsonseq  fuentes, manantiales, refugios, miradores y cimas
Salida (dentro de carpeta_salida, junto a lo que ya deja hacer_celdas.py):
  datos-NN/m/I_J.json   cuadrícula de 0,2° (~20 km): trozos de sendero + resumen de sus rutas + puntos del monte
  datos-NN/rt/rID.json  ficha de cada ruta con su recorrido ordenado (para seguirla con el GPS)
  datos/meta.json       se le añade «rutas» y «rpaso»
Uso: python3 hacer_rutas.py vias.geojsonseq rel.opl monte.geojsonseq carpeta_salida
"""
import json, sys, os, math, re
from collections import defaultdict

RSTEP = 5          # celdas de 0,2°
TOL_WAY = 6.0      # simplificación de cada trozo (m)
TOL_DET = 5.0      # simplificación del recorrido de la ficha (m)
JOIN = 40.0        # distancia máxima para unir trozos consecutivos (m)


def unesc(s):
    return re.sub(r"%([0-9a-fA-F]+)%", lambda m: chr(int(m.group(1), 16)), s)


def read_opl(path):
    rels = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("r"):
                continue
            toks = line.rstrip("\n").split(" ")
            rid = toks[0]
            tags, mem = {}, []
            for t in toks[1:]:
                if t.startswith("T") and len(t) > 1:
                    for kv in t[1:].split(","):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            tags[unesc(k)] = unesc(v)
                elif t.startswith("M") and len(t) > 1:
                    for m in t[1:].split(","):
                        if not m:
                            continue
                        ref, _, role = m.partition("@")
                        mem.append((ref, unesc(role)))
            rels[rid] = (tags, mem)
    return rels


def lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def dist(a, b):  # puntos (lon, lat) → metros
    k = math.cos(math.radians((a[1] + b[1]) / 2)) * 111320
    return math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * 110540)


def simplify(pts, tol):
    if len(pts) < 3:
        return pts[:]
    k = math.cos(math.radians(pts[0][1])) * 111320
    xy = [(p[0] * k, p[1] * 110540) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop()
        ax, ay = xy[a]; bx, by = xy[b]; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i]
            if L2:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                qx, qy = ax + t * dx - px, ay + t * dy - py
            else:
                qx, qy = px - ax, py - ay
            d = qx * qx + qy * qy
            if d > best:
                best, bi = d, i
        if bi > 0 and best > tol * tol:
            keep[bi] = True
            st.append((a, bi)); st.append((bi, b))
    return [p for p, k2 in zip(pts, keep) if k2]


def enc(pts):
    """Polilínea de Google (precisión 1e-5), puntos (lon, lat)."""
    out, plat, plon = [], 0, 0
    for lon, lat in pts:
        ilat, ilon = int(round(lat * 1e5)), int(round(lon * 1e5))
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63)); v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def chains(segs):
    """Une los trozos en recorridos continuos respetando el orden de la relación cuando se puede."""
    segs = [s for s in segs if len(s) >= 2]
    if not segs:
        return []
    out = []
    left = segs[:]
    while left:
        ch = left.pop(0)[:]
        grown = True
        while grown and left:
            grown = False
            # primero el siguiente en orden; si no encaja, cualquiera que toque un extremo
            for idx in list(range(len(left))):
                s = left[idx]
                if dist(ch[-1], s[0]) < JOIN: ch += s[1:]
                elif dist(ch[-1], s[-1]) < JOIN: ch += s[::-1][1:]
                elif dist(ch[0], s[-1]) < JOIN: ch = s[:-1] + ch
                elif dist(ch[0], s[0]) < JOIN: ch = s[::-1][:-1] + ch
                else: continue
                left.pop(idx); grown = True
                break
        out.append(ch)
    out.sort(key=lambda c: -len(c))
    return out


def color(tags):
    ref = (tags.get("ref") or "").upper().replace(" ", "")
    net = tags.get("network") or ""
    sym = (tags.get("osmc:symbol") or "").lower()
    if ref.startswith("GR") or "red:white:red" in sym: return "gr"
    if ref.startswith("PR") or "yellow" in sym: return "pr"
    if ref.startswith("SL") or "green" in sym: return "sl"
    if net in ("iwn", "nwn"): return "gr"
    if net == "rwn": return "pr"
    if net == "lwn": return "sl"
    return "ot"


def main(vias, opl, monte, out):
    rels = read_opl(opl)
    keep = {}
    for rid, (tags, mem) in rels.items():
        if tags.get("route") not in ("hiking", "foot"): continue
        if tags.get("state") in ("proposed", "disused", "abandoned"): continue
        if not (tags.get("name") or tags.get("ref")): continue
        ws = [ref for ref, role in mem if ref.startswith("w") and role not in ("alternative", "excursion", "approach", "connection")]
        if not ws: continue
        keep[rid] = (tags, ws)
    need = set(w for _, ws in keep.values() for w in ws)
    print("Relaciones:", len(rels), "· rutas válidas:", len(keep), "· tramos necesarios:", len(need))

    geo = {}
    for ft in lines(vias):
        fid = str(ft.get("id") or "")
        if fid not in need: continue
        g = ft.get("geometry") or {}
        if g.get("type") != "LineString": continue
        cs = [(round(c[0], 6), round(c[1], 6)) for c in g.get("coordinates") or []]
        if len(cs) >= 2: geo[fid] = cs
    print("Tramos con geometría:", len(geo))

    way_routes = defaultdict(list)
    summ, cells = {}, defaultdict(lambda: {"w": [], "r": {}, "p": []})
    n_rt = 0
    for rid, (tags, ws) in keep.items():
        segs = [geo[w] for w in ws if w in geo]
        if not segs: continue
        km = sum(dist(s[i], s[i + 1]) for s in segs for i in range(len(s) - 1)) / 1000
        if km < 0.3: continue
        chs = chains(segs)
        main_c = chs[0]
        circ = tags.get("roundtrip") == "yes" or (len(chs) == 1 and dist(main_c[0], main_c[-1]) < 250)
        allp = [p for s in segs for p in s]
        bb = [round(min(p[1] for p in allp), 4), round(min(p[0] for p in allp), 4), round(max(p[1] for p in allp), 4), round(max(p[0] for p in allp), 4)]
        st = main_c[0]
        band = math.floor(st[1] / 2)
        name = (tags.get("name:es") or tags.get("name") or "").strip()[:90]
        s = {"n": name, "ref": (tags.get("ref") or "")[:24], "k": color(tags), "km": round(km, 1), "c": 1 if circ else 0,
             "s": [round(st[1], 5), round(st[0], 5)], "b": bb, "f": band}
        summ[rid] = s
        det = dict(s)
        for k, k2 in (("from", "de"), ("to", "a"), ("operator", "op"), ("website", "web"), ("description", "d"), ("description:es", "d"), ("network", "net")):
            if tags.get(k): det[k2] = tags[k][:200]
        det["id"] = rid
        det["p"] = [enc(simplify(c, TOL_DET)) for c in chs[:12]]
        d = os.path.join(out, "datos-%d" % band, "rt"); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, rid + ".json"), "w", encoding="utf-8") as f:
            json.dump(det, f, ensure_ascii=False, separators=(",", ":"))
        n_rt += 1
        for w in ws:
            if w in geo and rid not in way_routes[w]: way_routes[w].append(rid)

    order = {"gr": 0, "pr": 1, "sl": 2, "ot": 3}
    for w, rs in way_routes.items():
        cs = geo[w]; mid = cs[len(cs) // 2]
        key = "%d_%d" % (math.floor(mid[1] * RSTEP), math.floor(mid[0] * RSTEP))
        c = cells[key]
        rs = sorted(rs, key=lambda r: (order.get(summ[r]["k"], 9), -summ[r]["km"]))
        for r in rs: c["r"][r] = summ[r]
        c["w"].append([enc(simplify(cs, TOL_WAY)), rs])

    n_p = 0
    for ft in lines(monte):
        p = ft.get("properties") or {}
        g = ft.get("geometry") or {}
        if g.get("type") == "Point": lon, lat = g["coordinates"][:2]
        else:
            pts = []
            def walk(x):
                if isinstance(x, list) and x and isinstance(x[0], (int, float)): pts.append(x)
                elif isinstance(x, list):
                    for y in x: walk(y)
            walk(g.get("coordinates"))
            if not pts: continue
            lon = sum(q[0] for q in pts) / len(pts); lat = sum(q[1] for q in pts) / len(pts)
        name = (p.get("name:es") or p.get("name") or "")[:60]
        t, x = None, ""
        if p.get("natural") == "peak":
            if not name: continue
            t, x = "c", str(p.get("ele") or "")[:8]
        elif p.get("amenity") == "drinking_water" or p.get("natural") == "spring":
            t = "f"; dw = p.get("drinking_water")
            x = "no" if dw == "no" else ("si" if (dw == "yes" or p.get("amenity") == "drinking_water") else "")
        elif p.get("tourism") in ("alpine_hut", "wilderness_hut"):
            t, x = "r", ("g" if p.get("tourism") == "alpine_hut" else "l")
        elif p.get("amenity") == "shelter":
            if p.get("shelter_type") in ("public_transport", "lean_to_bus", "changing_rooms"): continue
            t, x = "r", "s"
        elif p.get("tourism") == "viewpoint":
            t = "m"
        if not t: continue
        key = "%d_%d" % (math.floor(lat * RSTEP), math.floor(lon * RSTEP))
        cells[key]["p"].append([t, round(lat, 5), round(lon, 5), name, x])
        n_p += 1

    for key, c in cells.items():
        i = int(key.split("_")[0])
        d = os.path.join(out, "datos-%d" % (i // (2 * RSTEP)), "m"); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, key + ".json"), "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, separators=(",", ":"))

    mp = os.path.join(out, "datos", "meta.json")
    meta = {}
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f: meta = json.load(f)
    meta.update({"rutas": n_rt, "rpaso": 1 / RSTEP, "monte": n_p})
    os.makedirs(os.path.dirname(mp), exist_ok=True)
    with open(mp, "w", encoding="utf-8") as f: json.dump(meta, f, separators=(",", ":"))
    print("Rutas:", n_rt, "· celdas de monte:", len(cells), "· puntos del monte:", n_p)
    if n_rt < 100: sys.exit("Muy pocas rutas: algo ha ido mal")


if __name__ == "__main__":
    main(*sys.argv[1:5])
