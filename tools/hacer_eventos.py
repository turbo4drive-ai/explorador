#!/usr/bin/env python3
"""Patea · agenda de la ciudad (Open Data BCN, licencia CC BY 4.0) → eventos.json pequeño.
Detecta las columnas por su nombre para no romperse si cambian de orden.
Uso: python3 hacer_eventos.py agenda.csv salida/eventos.json
"""
import csv, sys, json, re, datetime, io
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, "rb").read()
for enc in ("utf-8-sig", "utf-16", "latin-1"):
    try: txt = raw.decode(enc); break
    except Exception: pass
sample = txt[:5000]
delim = max([",", ";", "\t", "|"], key=lambda d: sample.split("\n")[0].count(d))
rows = list(csv.reader(io.StringIO(txt), delimiter=delim))
head = [h.strip().lower() for h in rows[0]]
print("DELIM", repr(delim), "FILAS", len(rows) - 1)
print("COLUMNAS", head)
for r in rows[1:3]: print("EJEMPLO", r[:60])
def col(*pats, avoid=()):
    for p in pats:
        for i, h in enumerate(head):
            if re.search(p, h) and not any(re.search(a, h) for a in avoid): return i
    return None
I = dict(id=col(r"^register_id$", r"^id$", r"register"), name=col(r"^name$", r"nom", r"title", r"titol"),
         lat=col(r"4326.*(lat|_y)$", r"latitud", r"^lat"), lon=col(r"4326.*(lon|_x)$", r"longitud", r"^lon"),
         start=col(r"start_date", r"data_inici", r"inici", r"start"), end=col(r"end_date", r"data_fi", r"\bfi\b", r"end"),
         cat=col(r"secondary_filters_name", r"categor", r"filters_name"), road=col(r"addresses_road_name", r"carrer", r"road"),
         num=col(r"addresses_start_street_number", r"street_number"), hood=col(r"addresses_neighborhood_name", r"barri", r"neighborhood"),
         place=col(r"institution_name", r"equipament", r"lloc"), times=col(r"timetable", r"horari"))
print("DETECTADAS", I)
def parse_dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try: return datetime.datetime.strptime(s[:19], f)
        except Exception: pass
    return None
now = datetime.datetime.utcnow(); horizon = now + datetime.timedelta(days=8)
ev = {}
def g(r, k):
    i = I.get(k); return r[i].strip() if i is not None and i < len(r) else ""
for r in rows[1:]:
    try:
        lat = float(g(r, "lat").replace(",", ".")); lon = float(g(r, "lon").replace(",", "."))
    except Exception: continue
    if not (35 < lat < 44 and -10 < lon < 5): continue
    st, en = parse_dt(g(r, "start")), parse_dt(g(r, "end"))
    if not st: continue
    en = en or st
    if en < now - datetime.timedelta(hours=6) or st > horizon: continue
    eid = g(r, "id") or (g(r, "name") + g(r, "start"))
    e = ev.get(eid)
    if not e:
        addr = " ".join(x for x in [g(r, "road"), g(r, "num")] if x)
        e = ev[eid] = {"i": eid[:40], "n": g(r, "name")[:90], "a": round(lat, 6), "o": round(lon, 6), "s": st.strftime("%Y-%m-%dT%H:%M"), "e": en.strftime("%Y-%m-%dT%H:%M"),
                       "c": [], "d": addr[:80], "b": g(r, "hood")[:40], "p": g(r, "place")[:70], "h": g(r, "times")[:120]}
    c = g(r, "cat")
    if c and c not in e["c"] and len(e["c"]) < 4: e["c"].append(c[:40])
out = sorted(ev.values(), key=lambda x: x["s"])
json.dump({"fecha": now.strftime("%Y-%m-%dT%H:%MZ"), "fuente": "Ajuntament de Barcelona · Open Data BCN (CC BY 4.0)", "eventos": out}, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("EVENTOS", len(out))
