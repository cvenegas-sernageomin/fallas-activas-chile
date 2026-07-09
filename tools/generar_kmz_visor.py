"""Empaqueta todas las capas del visor en un unico KMZ para Google Earth Pro.

El visor es web (Leaflet); esto genera el equivalente estatico para Google Earth,
con el mismo estilo tematico:
  - Fallas Activas: lineas por actividad (Proved/Probable/Possible)
  - Sismos Harvard: mecanismo focal (beachball PNG embebido), tamano por Mw
  - Sismos USGS/CSN: circulo por magnitud (color+tamano)
  - Vs30: punto por clase de suelo NCh433 (A roca .. E blando)
  - Infraestructura: punto/linea por sector

Salida: fallas_activas_chile.kmz (en la raiz del repo).
Nota: USGS/CSN son instantaneas (el KMZ es estatico); Harvard y Vs30 no cambian.
"""
import json
import re
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OUT = REPO / "fallas_activas_chile.kmz"
BB_DIR = DATA / "sismos" / "beachballs"

INCLUIR_RED_VIAL = True  # red_vial es la capa mas pesada (~20 MB); False la excluye


# ---------------------------------------------------------------- utilidades
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def kcol(css, alpha="ff"):
    """CSS #rrggbb -> color KML aabbggrr."""
    c = css.lstrip("#")
    rr, gg, bb = c[0:2], c[2:4], c[4:6]
    return f"{alpha}{bb}{gg}{rr}"


DOT = "http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png"


# ------------------------------------------------------- parseo de fuentes
def puntos_geojson(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in d.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        c = g["coordinates"]
        out.append((c[0], c[1], c[2] if len(c) > 2 else None, f.get("properties", {})))
    return out


_PM = re.compile(r"<Placemark\b[^>]*>(.*?)</Placemark>", re.S)
_NAME = re.compile(r"<name>(.*?)</name>", re.S)
_SD = re.compile(r'<SimpleData name="([^"]+)">(.*?)</SimpleData>', re.S)
_PT = re.compile(r"<Point>.*?<coordinates>(.*?)</coordinates>", re.S)
_LS = re.compile(r"<LineString>.*?<coordinates>(.*?)</coordinates>", re.S)


def _dec(s):
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")).strip()


def _attrs(block):
    return {m.group(1): _dec(m.group(2)) for m in _SD.finditer(block)}


def puntos_kml(path):
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    out = []
    for m in _PM.finditer(txt):
        block = m.group(1)
        pt = _PT.search(block)
        if not pt:
            continue
        p = pt.group(1).strip().split(",")
        try:
            lon, lat = float(p[0]), float(p[1])
        except (ValueError, IndexError):
            continue
        nm = _NAME.search(block)
        out.append((lon, lat, _dec(nm.group(1)) if nm else "", _attrs(block)))
    return out


def lineas_kml(path):
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    out = []
    for m in _PM.finditer(txt):
        block = m.group(1)
        segs = []
        for ls in _LS.finditer(block):
            coords = " ".join(pair for pair in ls.group(1).strip().split())
            if coords:
                segs.append(coords)
        if not segs:
            continue
        nm = _NAME.search(block)
        out.append((segs, _dec(nm.group(1)) if nm else "", _attrs(block)))
    return out


# ------------------------------------------------------- placemarks/estilos
def tabla_desc(attrs, saltar=()):
    filas = "".join(
        f"<tr><td><b>{esc(k)}</b></td><td>{esc(v)}</td></tr>"
        for k, v in attrs.items()
        if v not in ("", "-99", "-99.0", "No value") and k not in saltar
    )
    return f"<![CDATA[<table>{filas}</table>]]>" if filas else ""


def pm_punto(lon, lat, name, style_url, desc=""):
    d = f"<description>{desc}</description>" if desc else ""
    return (f'<Placemark><name>{esc(name)}</name><styleUrl>{style_url}</styleUrl>{d}'
            f'<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>')


def pm_punto_icono(lon, lat, name, icon_href, scale, desc=""):
    d = f"<description>{desc}</description>" if desc else ""
    return (f'<Placemark><name>{esc(name)}</name>'
            f'<Style><IconStyle><scale>{scale}</scale>'
            f'<Icon><href>{icon_href}</href></Icon></IconStyle>'
            f'<LabelStyle><scale>0</scale></LabelStyle></Style>{d}'
            f'<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>')


def pm_lineas(segs, name, style_url, desc=""):
    d = f"<description>{desc}</description>" if desc else ""
    geoms = "".join(f"<LineString><tessellate>1</tessellate>"
                    f"<coordinates>{s}</coordinates></LineString>" for s in segs)
    if len(segs) > 1:
        geoms = f"<MultiGeometry>{geoms}</MultiGeometry>"
    return (f'<Placemark><name>{esc(name)}</name><styleUrl>{style_url}</styleUrl>{d}'
            f'{geoms}</Placemark>')


# escala de magnitud (mismo criterio que el visor / alertas-redes)
def mag_bin(m):
    if m is None:
        return "s_mag_nd"
    if m >= 7: return "s_mag7"
    if m >= 6: return "s_mag6"
    if m >= 5: return "s_mag5"
    if m >= 4: return "s_mag4"
    return "s_mag3"


MAG_STYLES = {
    "s_mag7": ("#cc0000", 1.8), "s_mag6": ("#ff3300", 1.3), "s_mag5": ("#ff8000", 1.0),
    "s_mag4": ("#ffd700", 0.7), "s_mag3": ("#80ff40", 0.5), "s_mag_nd": ("#9db1c4", 0.6),
}
VS30_STYLES = {  # (min, css, label)
    "s_vsA": (900, "#313695"), "s_vsB": (500, "#74add1"), "s_vsC": (350, "#fee090"),
    "s_vsD": (180, "#f46d43"), "s_vsE": (0, "#a50026"),
}
SECTOR_COLOR = {
    "agua": "#38bdf8", "energia": "#f59e0b", "relaves": "#92400e", "salud": "#f43f5e",
    "transporte": "#a855f7", "seguridad": "#ef4444", "educacion": "#06b6d4",
}
FALLA_COLOR = {"Proved": "#ff2d2d", "Probable": "#ff8c00", "Possible": "#e6c400"}


def vs30_bin(v):
    for sid, (mn, _css) in VS30_STYLES.items():
        if v is not None and v >= mn:
            return sid
    return "s_vsE"


def bloque_estilos():
    s = []
    for sid, (css, scale) in MAG_STYLES.items():
        s.append(f'<Style id="{sid}"><IconStyle><color>{kcol(css)}</color>'
                 f'<scale>{scale}</scale><Icon><href>{DOT}</href></Icon></IconStyle>'
                 f'<LabelStyle><scale>0</scale></LabelStyle></Style>')
    for sid, (_mn, css) in VS30_STYLES.items():
        s.append(f'<Style id="{sid}"><IconStyle><color>{kcol(css)}</color>'
                 f'<scale>0.8</scale><Icon><href>{DOT}</href></Icon></IconStyle>'
                 f'<LabelStyle><scale>0</scale></LabelStyle></Style>')
    for sec, css in SECTOR_COLOR.items():
        s.append(f'<Style id="s_sec_{sec}"><IconStyle><color>{kcol(css)}</color>'
                 f'<scale>0.6</scale><Icon><href>{DOT}</href></Icon></IconStyle>'
                 f'<LabelStyle><scale>0</scale></LabelStyle>'
                 f'<LineStyle><color>{kcol(css)}</color><width>2</width></LineStyle></Style>')
    for act, css in FALLA_COLOR.items():
        s.append(f'<Style id="s_fa_{act}"><LineStyle><color>{kcol(css)}</color>'
                 f'<width>3</width></LineStyle></Style>')
    return "\n".join(s)


# ------------------------------------------------------------ construccion
def folder(nombre, contenido, abierto=False):
    return f'<Folder><name>{esc(nombre)}</name><open>{1 if abierto else 0}</open>\n{contenido}\n</Folder>'


def build():
    partes = []
    iconos = {}  # ruta_en_kmz -> bytes

    # --- Fallas ---
    fal = []
    for segs, name, attrs in lineas_kml(DATA / "red_fallas.kml"):
        act = attrs.get("activity", "")
        nm = attrs.get("F_name") or name or act or "falla"
        fal.append(pm_lineas(segs, nm, f"#s_fa_{act}" if act in FALLA_COLOR else "#s_fa_Possible",
                             tabla_desc(attrs)))
    partes.append(folder(f"Fallas Activas (CHAF v1) — {len(fal)}", "\n".join(fal)))

    # --- Sismos ---
    sis = []
    # Harvard con beachballs
    hv = puntos_geojson(DATA / "sismos" / "harvard_someros.geojson")
    hpm = []
    for lon, lat, _z, p in hv:
        bb = p.get("beachball")  # "beachballs/bb_XXXX.png"
        mw = p.get("mw")
        scale = round(max(0.6, min(2.2, 0.25 * ((mw or 5) - 3.0) + 0.6)), 2)
        if bb:
            png = BB_DIR / Path(bb).name
            if png.exists():
                iconos[bb] = png.read_bytes()
        nm = f"M{mw if mw is not None else '?'} {p.get('fecha','')}"
        hpm.append(pm_punto_icono(lon, lat, nm, bb or DOT, scale, tabla_desc(p, saltar=("beachball",))))
    sis.append(folder(f"Historicos Harvard/GCMT — mecanismos focales — {len(hpm)}", "\n".join(hpm)))
    # USGS + CSN por magnitud
    for etiqueta, archivo in [("USGS (instantanea)", "usgs_snapshot.geojson"),
                              ("CSN (instantanea)", "csn_reciente.geojson")]:
        pm = []
        for lon, lat, z, p in puntos_geojson(DATA / "sismos" / archivo):
            mag = p.get("mag")
            try:
                mag = float(mag) if mag is not None else None
            except (TypeError, ValueError):
                mag = None
            nm = f"M{mag if mag is not None else '?'} — {p.get('place') or p.get('fecha','')}"
            pm.append(pm_punto(lon, lat, nm, f"#{mag_bin(mag)}", tabla_desc(p)))
        sis.append(folder(f"{etiqueta} — {len(pm)}", "\n".join(pm)))
    partes.append(folder("Sismos", "\n".join(sis)))

    # --- Vs30 ---
    vpm = []
    for lon, lat, name, attrs in puntos_kml(DATA / "vs30" / "vs30_chile.kml"):
        try:
            v = float(attrs.get("Vs30", ""))
        except ValueError:
            v = None
        vpm.append(pm_punto(lon, lat, name, f"#{vs30_bin(v)}", tabla_desc(attrs)))
    partes.append(folder(f"Vs30 — rigidez del sitio (NCh433) — {len(vpm)}", "\n".join(vpm)))

    # --- Infraestructura ---
    INFRA = [
        ("seguridad", "Cuarteles de Carabineros", "seguridad/carabineros.kml", "points"),
        ("seguridad", "Parques de Bomberos", "seguridad/bomberos.kml", "points"),
        ("salud", "Establecimientos de Salud", "salud/establecimientos_salud.kml", "points"),
        ("educacion", "Establecimientos Educacionales", "educacion/establecimientos_educacion.kml", "points"),
        ("agua", "Agua Potable Rural", "agua/agua_potable_rural.kml", "points"),
        ("agua", "Bocatomas", "agua/bocatomas.kml", "points"),
        ("relaves", "Relaves (SERNAGEOMIN 2025)", "relaves/relaves_sernageomin_2025.kml", "points"),
        ("transporte", "Puentes", "transporte/puentes.kml", "points"),
        ("transporte", "Infraestructura Portuaria", "transporte/infraestructura_portuaria.kml", "points"),
        ("transporte", "Red Aeroportuaria", "transporte/red_aeroportuaria.kml", "points"),
        ("transporte", "Red Ferrea", "transporte/red_ferrea.kml", "lines"),
        ("transporte", "Red Vial", "transporte/red_vial.kml", "lines"),
        ("energia", "Almacenes de Combustible", "energia/almacenes_combustible.kml", "points"),
        ("energia", "Centrales de Biomasa", "energia/centrales_biomasa.kml", "points"),
        ("energia", "Centrales Eolicas", "energia/centrales_eolicas.kml", "points"),
        ("energia", "Centrales Geotermicas", "energia/centrales_geotermicas.kml", "points"),
        ("energia", "Centrales Hidroelectricas", "energia/centrales_hidroelectricas.kml", "points"),
        ("energia", "Centrales Solares", "energia/centrales_solares.kml", "points"),
        ("energia", "Termoelectricas", "energia/termoelectricas.kml", "points"),
        ("energia", "Terminales Maritimos de Descarga", "energia/terminales_maritimos_descarga.kml", "points"),
        ("energia", "Subestaciones SEA", "energia/subestaciones_sea.kml", "points"),
        ("energia", "Subestaciones SEM", "energia/subestaciones_sem.kml", "points"),
        ("energia", "Subestaciones SIC", "energia/subestaciones_sic.kml", "points"),
        ("energia", "Subestaciones SING", "energia/subestaciones_sing.kml", "points"),
        ("energia", "Gasoductos", "energia/gasoductos.kml", "lines"),
        ("energia", "Oleoductos", "energia/oleoductos.kml", "lines"),
        ("energia", "Lineas Electricas SEA", "energia/lineas_sea.kml", "lines"),
        ("energia", "Lineas Electricas SEM", "energia/lineas_sem.kml", "lines"),
        ("energia", "Lineas Electricas SIC", "energia/lineas_sic.kml", "lines"),
        ("energia", "Lineas Electricas SING", "energia/lineas_sing.kml", "lines"),
    ]
    # las capas grandes van con name only (sin tabla) para no inflar el KMZ
    GRANDES = {"educacion/establecimientos_educacion.kml", "transporte/puentes.kml"}
    por_sector = {}
    for sector, label, rel, kind in INFRA:
        ruta = DATA / rel
        if not ruta.exists():
            continue
        if rel == "transporte/red_vial.kml" and not INCLUIR_RED_VIAL:
            continue
        pm = []
        if kind == "points":
            for lon, lat, name, attrs in puntos_kml(ruta):
                desc = "" if rel in GRANDES else tabla_desc(attrs)
                pm.append(pm_punto(lon, lat, name or label, f"#s_sec_{sector}", desc))
        else:
            for segs, name, attrs in lineas_kml(ruta):
                pm.append(pm_lineas(segs, name or label, f"#s_sec_{sector}"))
        por_sector.setdefault(sector, []).append(folder(f"{label} — {len(pm)}", "\n".join(pm)))

    ORDEN = ["seguridad", "salud", "educacion", "agua", "energia", "transporte", "relaves"]
    ICON_SEC = {"seguridad": "🚨", "salud": "🏥", "educacion": "📚", "agua": "💧",
                "energia": "⚡", "transporte": "🚦", "relaves": "⛏️"}
    infra_folders = []
    for sec in ORDEN:
        if sec in por_sector:
            infra_folders.append(folder(f"{ICON_SEC.get(sec,'')} {sec.capitalize()}",
                                        "\n".join(por_sector[sec])))
    partes.append(folder("Infraestructura Critica", "\n".join(infra_folders)))

    doc = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
           f'<name>Fallas Activas + Sismos + Vs30 + Infraestructura — Chile</name>\n'
           f'{bloque_estilos()}\n'
           f'{chr(10).join(partes)}\n'
           f'</Document></kml>')

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", doc)
        for ruta, datos in iconos.items():
            z.writestr(ruta, datos)
    mb = OUT.stat().st_size / 1e6
    print(f"KMZ generado: {OUT.name}  ({mb:.1f} MB, {len(iconos)} beachballs embebidos)")


if __name__ == "__main__":
    build()
