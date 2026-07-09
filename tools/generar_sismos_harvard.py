"""Genera assets web de sismos historicos Harvard/GCMT con mecanismos focales.

Adaptado de Documents\\Sernageomin_Sismos\\build_kmz.py (que produce un KMZ para
Google Earth con los PNG embebidos). Aca en cambio se producen assets para el visor
Leaflet de fallas-activas-chile:
  - data/sismos/beachballs/bb_XXXX.png  (mecanismo focal por sismo, servido suelto)
  - data/sismos/harvard_someros.geojson (un feature por sismo, con metadata + ruta al PNG)

Reutiliza tal cual el renderizador beachball_png() en numpy puro (sin obspy).
Fuente: catalogo Global CMT completo 1976-2020 (jan76_dec20.ndk), copiado como
data/raw/gcmt_1976_2020.ndk.gz. Ver reference-harvard-cmt-beachball-kmz en memoria.

Diferencias vs build_kmz.py original:
  - Filtra e bandea por profundidad de HIPOCENTRO (no centroide). El catalogo GCMT
    fija la profundidad de CENTROIDE de sismos someros en ~10-15 km (piso duro, mal
    restringida) -> con centroide la banda 0-5 km sale VACIA. La prof. de hipocentro
    (linea PDE de referencia) es la que reportan USGS y CSN como "profundidad", asi
    que se bandea por ella para consistencia entre las 3 fuentes. Ambas profundidades
    van en el popup.
  - Filtro: hipocentro <= 30 km. Subfiltro 0-5 km lo hace el visor client-side con
    la propiedad banda_prof.
  - SIN filtro "sobre tierra" (elevacion): se incluyen los sismos de interfaz de
    subduccion offshore, relevantes para un visor de fallas activas.
  - Punto ubicado en el HIPOCENTRO (epicentro) para consistencia con USGS/CSN; el
    centroide queda en el popup.
  - Salida GeoJSON + PNGs sueltos en vez de KMZ con PNG embebidos.
"""
import gzip
import io
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

REPO = Path(__file__).resolve().parent.parent
NDK_GZ = REPO / "data" / "raw" / "gcmt_1976_2020.ndk.gz"
OUT_DIR = REPO / "data" / "sismos"
BB_DIR = OUT_DIR / "beachballs"
OUT_GEOJSON = OUT_DIR / "harvard_someros.geojson"

LAT_MIN, LAT_MAX = -56.0, -17.0
LON_MIN, LON_MAX = -76.0, -66.0
DEPTH_MAX = 30.0   # km, profundidad de CENTROIDE (CMT), pedido del usuario


# ---------------------------------------------------------------- parse NDK
def parse(lines):
    evs = []
    for i in range(0, len(lines) - 4, 5):
        l1, l2, l3, l4, l5 = lines[i:i + 5]
        try:
            date_str = l1[5:15].strip()
            time_str = l1[16:26].strip()
            lat_h = float(l1[27:33]); lon_h = float(l1[34:41])
            dep_h = float(l1[42:47])
            mb = float(l1[48:51]); ms = float(l1[52:55])
            region = l1[56:].strip()
        except ValueError:
            continue
        try:
            p3 = l3.split()
            clat = float(p3[3]); clon = float(p3[5]); cdep = float(p3[7])
        except (ValueError, IndexError):
            clat, clon, cdep = lat_h, lon_h, dep_h
        try:
            p4 = l4.split()
            exp = int(p4[0])
            Mrr = float(p4[1]); Mtt = float(p4[3]); Mpp = float(p4[5])
            Mrt = float(p4[7]); Mrp = float(p4[9]); Mtp = float(p4[11])
        except (ValueError, IndexError):
            continue
        np1 = np2 = None; m0 = None
        try:
            p5 = l5.split()
            m0 = float(p5[10])
            np1 = (float(p5[11]), float(p5[12]), float(p5[13]))
            np2 = (float(p5[14]), float(p5[15]), float(p5[16]))
        except (ValueError, IndexError):
            pass
        mw = None
        if m0 is not None:
            m0_full = m0 * 10 ** exp
            mw = round((2.0 / 3.0) * (math.log10(m0_full) - 16.1), 2)

        if not (LAT_MIN <= clat <= LAT_MAX and LON_MIN <= clon <= LON_MAX):
            continue
        if dep_h > DEPTH_MAX:   # filtro por profundidad de HIPOCENTRO (ver docstring)
            continue
        evs.append(dict(date=date_str, time=time_str,
                        lat_h=lat_h, lon_h=lon_h, dep_h=dep_h,
                        clat=clat, clon=clon, cdep=cdep,
                        mb=mb, ms=ms, mw=mw, region=region,
                        M=(Mrr, Mtt, Mpp, Mrt, Mrp, Mtp), np1=np1, np2=np2))
    return evs


# ------------------------------------------------ beachball desde el tensor
# (identico a build_kmz.py; numpy puro, hemisferio inferior, equiarea)
def beachball_png(M, size=96):   # el visor lo muestra a 16-48 px; 96 basta para 2x (retina)
    Mrr, Mtt, Mpp, Mrt, Mrp, Mtp = M
    n = size
    xs = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(xs, xs)
    R = np.sqrt(X ** 2 + Y ** 2)
    inside = R <= 1.0
    R_c = np.clip(R, 0, 1)
    theta = 2.0 * np.arcsin(np.clip(R_c / math.sqrt(2.0), 0, 1))
    az = np.arctan2(X, Y)
    gr = -np.cos(theta)
    gt = -np.sin(theta) * np.cos(az)
    gp = np.sin(theta) * np.sin(az)
    A = (Mrr * gr * gr + Mtt * gt * gt + Mpp * gp * gp
         + 2 * Mrt * gr * gt + 2 * Mrp * gr * gp + 2 * Mtp * gt * gp)
    img = np.zeros((n, n, 4), dtype=float)
    comp = inside & (A >= 0)
    dila = inside & (A < 0)
    img[dila] = [1, 1, 1, 1]
    img[comp] = [0.10, 0.10, 0.10, 1]
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.imshow(img[::-1], extent=[-1, 1, -1, 1], interpolation="nearest")
    ax.add_patch(Circle((0, 0), 1.0, fill=False, lw=2.0, color="black"))
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, dpi=100)
    plt.close(fig)
    return buf.getvalue()


def build():
    if not NDK_GZ.exists():
        raise FileNotFoundError(
            f"No se encontro {NDK_GZ}. Copiar el catalogo GCMT (jan76_dec20.ndk.gz) "
            "desde Documents\\Sernageomin_Sismos\\ a data/raw/gcmt_1976_2020.ndk.gz. "
            "Ver reference-harvard-cmt-beachball-kmz en memoria."
        )
    with gzip.open(NDK_GZ, "rt", encoding="latin-1") as f:
        lines = [l.rstrip("\n") for l in f]

    evs = parse(lines)
    print(f"Sismos Chile, centroide <= {DEPTH_MAX:g} km: {len(evs)}")
    evs.sort(key=lambda e: (e["mw"] is None, -(e["mw"] or 0)))

    BB_DIR.mkdir(parents=True, exist_ok=True)
    # limpiar PNGs previos para no dejar beachballs huerfanos de una corrida anterior
    for viejo in BB_DIR.glob("bb_*.png"):
        viejo.unlink()
    features = []
    for idx, e in enumerate(evs):
        bb_name = f"bb_{idx:04d}.png"
        (BB_DIR / bb_name).write_bytes(beachball_png(e["M"]))
        banda = "0-5" if e["dep_h"] <= 5.0 else "5-30"
        props = {
            "fecha": e["date"], "hora": e["time"],
            "mw": e["mw"], "mb": e["mb"], "ms": e["ms"],
            "prof_centroide_km": round(e["cdep"], 1),
            "prof_hipocentro_km": round(e["dep_h"], 1),
            "lat_hipocentro": round(e["lat_h"], 3),
            "lon_hipocentro": round(e["lon_h"], 3),
            "banda_prof": banda,
            "region": e["region"],
            "beachball": f"beachballs/{bb_name}",
        }
        if e["np1"] and e["np2"]:
            props["np1_rumbo"] = round(e["np1"][0])
            props["np1_manteo"] = round(e["np1"][1])
            props["np1_cabeceo"] = round(e["np1"][2])
            props["np2_rumbo"] = round(e["np2"][0])
            props["np2_manteo"] = round(e["np2"][1])
            props["np2_cabeceo"] = round(e["np2"][2])
        props["lat_centroide"] = round(e["clat"], 3)
        props["lon_centroide"] = round(e["clon"], 3)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(e["lon_h"], 4), round(e["lat_h"], 4)]},
            "properties": props,
        })

    geojson = {"type": "FeatureCollection", "features": features}
    OUT_GEOJSON.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")

    n05 = sum(1 for f in features if f["properties"]["banda_prof"] == "0-5")
    print(f"  banda 0-5 km:  {n05}")
    print(f"  banda 5-30 km: {len(features) - n05}")
    print(f"Escrito: {OUT_GEOJSON} ({OUT_GEOJSON.stat().st_size:,} bytes)")
    print(f"Beachballs: {len(features)} PNG en {BB_DIR}")


if __name__ == "__main__":
    build()
