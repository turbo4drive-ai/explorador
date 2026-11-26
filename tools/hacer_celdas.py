#!/usr/bin/env python3
"""Patea · convierte los sitios de OpenStreetMap (GeoJSON por líneas, de osmium export)
en archivos pequeños por cuadrícula de 0,01° (~1 km) que la app descarga al momento.
Uso: python3 hacer_celdas.py sitios.geojsonseq carpeta_salida
"""
import json, sys, os, math, datetime
from collections import defaultdict

KEEP = {"name","name:es","name:en","name:ca","amenity","tourism","historic","emergency","internet_access","leisure","man_made",
        "artwork_type","heritage","wikidata","wikipedia","image","wikimedia_commons","opening_hours","cuisine","phone","contact:phone",
        "website","contact:website","contact:instagram","outdoor_seating","min_age","diet:vegan","diet:vegetarian","takeaway","delivery",
        "veterinary:emergency","fee","wheelchair","changing_table","access","internet_access:fee","backrest","covered","indoor","operator",
        "unisex","toilets:disposal","toilets:position","drinking_water","bottle","level","start_date","artist_name","inscription",
        "description","description:es","description:en"}
STEP = 100  # celdas de 0,01°

def centro(g):
    t = g.get("type"); c = g.get("coordinates")
    if t == "Point": return c[1], c[0]
    pts = []
    def walk(x):
        if isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float)): pts.append(x)
        elif isinstance(x, (list, tuple)):
            for y in x: walk(y)
    walk(c)
    if not pts: return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)

def main(src, out):
    cells = defaultdict(dict); n = 0
    s = w = 90; nn = e = -90; s = 90; w = 180; nn = -90; e = -180
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line: continue
            try: ft = json.loads(line)
            except Exception: continue
            props = ft.get("properties") or {}
            fid = str(ft.get("id") or props.get("@id") or "")
            if not fid or not props: continue
            # osmium type_id: n123 / w123 / r123 (las áreas pueden venir como a123 → par = way, impar = relación)
            if fid[0] == "a" and fid[1:].isdigit():
                num = int(fid[1:]); fid = ("w%d" % (num // 2)) if num % 2 == 0 else ("r%d" % (num // 2))
            g = ft.get("geometry")
            if not g: continue
            c = centro(g)
            if not c: continue
            lat, lon = round(c[0], 6), round(c[1], 6)
            tags = {k: str(v)[:100] for k, v in props.items() if k in KEEP}
            if not tags or tags.get("amenity") == "bench": continue
            if "internet_access" in props and "name" not in tags and not tags.get("amenity") and not tags.get("tourism"): continue
            key = "%d_%d" % (math.floor(lat * STEP), math.floor(lon * STEP))
            cells[key][fid] = [fid, lat, lon, tags]
            n += 1; s = min(s, lat); nn = max(nn, lat); w = min(w, lon); e = max(e, lon)
    # cada franja de 2° de latitud va en su propia rama («datos-20», «datos-21»…) para que ninguna pese demasiado
    cov = set(); bands = defaultdict(int)
    for key, items in cells.items():
        i, j = map(int, key.split("_")); lat = i / STEP; band = math.floor(lat / 2)
        d = os.path.join(out, "datos-%d" % band, "c"); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, key + ".json"), "w", encoding="utf-8") as f:
            json.dump(list(items.values()), f, ensure_ascii=False, separators=(",", ":"))
        bands[band] += len(items)
        cov.add("%d_%d" % (math.floor(i / 25), math.floor(j / 25)))  # zonas cubiertas de 0,25°
    meta = {"fecha": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "paso": 1 / STEP, "sitios": n, "celdas": len(cells),
            "zona": [round(s - .01, 3), round(w - .01, 3), round(nn + .01, 3), round(e + .01, 3)], "cubre": sorted(cov),
            "franjas": {str(b): c for b, c in sorted(bands.items())}}
    os.makedirs(os.path.join(out, "datos"), exist_ok=True)
    with open(os.path.join(out, "datos", "meta.json"), "w", encoding="utf-8") as f: json.dump(meta, f, separators=(",", ":"))
    print("Sitios:", n, "· celdas:", len(cells), "· zona:", meta["zona"], "· franjas:", meta["franjas"], "· zonas cubiertas:", len(meta["cubre"]))
    if n < 1000: sys.exit("Muy pocos sitios: algo ha ido mal, no publico nada")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
