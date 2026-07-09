"""Convierte el levantamiento de Vs30 (velocidad de onda de corte en los 30 m
superiores) a KML para el visor.

904 puntos georreferenciados con valor de Vs30 (m/s) de distintas instituciones,
estudios y tesis; cada punto trae ciudad, año, autor, título de la investigación,
tipo de documento, referencia, etc. Vs30 es un parámetro clave de efecto de sitio
para peligro sísmico: a menor Vs30 (suelo blando) mayor amplificación.

El visor colorea por CLASE DE SUELO NCh433/DS61 (A roca .. E suelo blando).

Encoding: el .dbf viene en latin-1 con mojibake ("BastÃ­as"); mismo tratamiento que
tools/procesar_infra_shapefiles.py (detección por config GDAL + reparación round-trip).
"""
from pathlib import Path
import glob
import tempfile
import zipfile

import geopandas as gpd
import pandas as pd
import pyogrio

DATA = Path(__file__).resolve().parent.parent / "data"
ZIP = DATA / "raw" / "vs30_src.zip"
SALIDA = DATA / "vs30" / "vs30_chile.kml"
COL_VS30_ORIG = "Vs30_(m/s)"


def _reparar_mojibake(s):
    if not isinstance(s, str) or ("Ã" not in s and "Â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s.encode("latin-1", "ignore").decode("utf-8", "replace")


def _score(g) -> int:
    m = " ".join(str(v) for v in g.select_dtypes(include="object").head(400).values.ravel())
    return m.count("Ã") + m.count("Â") + m.count("�")


def _dedupe(cols):
    vistas, out = {}, []
    for c in cols:
        if c in vistas:
            vistas[c] += 1
            out.append(f"{c}_{vistas[c]}")
        else:
            vistas[c] = 0
            out.append(c)
    return out


def leer_shp(shp):
    mejor = None
    for cfg in [None, "UTF-8", "ISO-8859-1"]:
        pyogrio.set_gdal_config_options({"SHAPE_ENCODING": cfg})
        try:
            g = pyogrio.read_dataframe(shp)
        except UnicodeDecodeError:
            g = None
        finally:
            pyogrio.set_gdal_config_options({"SHAPE_ENCODING": None})
        if g is None:
            continue
        sc = _score(g)
        if sc == 0:
            return g
        if mejor is None or sc < mejor[1]:
            mejor = (g, sc)
    g = mejor[0].copy()
    g.columns = _dedupe([_reparar_mojibake(c) for c in g.columns])
    for col in g.columns:
        if col != "geometry" and g[col].dtype == object:
            g[col] = g[col].map(_reparar_mojibake)
    return g


def main():
    if not ZIP.exists():
        raise FileNotFoundError(f"No existe {ZIP} (mover el zip del levantamiento Vs30 ahí).")
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(ZIP) as zf:
            zf.extractall(td)
        shp = glob.glob(f"{td}/**/*.shp", recursive=True)[0]
        gdf = leer_shp(shp)
    gdf.columns = _dedupe(list(gdf.columns))
    gdf = gdf.to_crs("EPSG:4326")

    # Vs30 numérico, columna limpia "Vs30" (m/s) para que el visor la lea sin líos de
    # paréntesis/slash en el nombre del campo KML.
    vs = pd.to_numeric(gdf[COL_VS30_ORIG], errors="coerce")
    gdf["Vs30"] = vs

    # Name legible para el popup: ciudad + valor.
    ciudad = gdf["City"].map(_reparar_mojibake).fillna("").astype(str).str.strip() if "City" in gdf.columns else ""
    gdf["Name"] = [
        (f"{c}: Vs30 {int(v)} m/s" if pd.notna(v) else (c or "Vs30")) for c, v in zip(ciudad, vs)
    ]

    # Atributos: quitar duplicados de coordenadas y el original con nombre feo; "No value" -> "".
    quitar = [c for c in ["Lat", "Lon", COL_VS30_ORIG, "geometry", "Name"] if c in gdf.columns]
    atributos = gdf.drop(columns=quitar).copy()
    for col in atributos.columns:
        serie = atributos[col]
        if pd.api.types.is_datetime64_any_dtype(serie):
            atributos[col] = serie.dt.strftime("%Y-%m-%d")
        else:
            atributos[col] = serie.where(serie.notna(), "").astype(str).map(_reparar_mojibake)
            atributos[col] = atributos[col].replace({"No value": "", "nan": "", "None": ""})
    # Vs30 como entero legible (sin ".0")
    atributos["Vs30"] = [("" if pd.isna(v) else str(int(v))) for v in vs]

    out = gpd.GeoDataFrame(atributos, geometry=gdf.geometry, crs="EPSG:4326")
    out.insert(0, "Name", gdf["Name"].values)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    if SALIDA.exists():
        SALIDA.unlink()
    out.to_file(SALIDA, driver="KML")

    print(f"Vs30: {len(out)} puntos | rango {int(vs.min())}-{int(vs.max())} m/s")
    # distribución por clase NCh433
    clases = {"A (>=900)": (vs >= 900).sum(), "B (500-900)": ((vs >= 500) & (vs < 900)).sum(),
              "C (350-500)": ((vs >= 350) & (vs < 500)).sum(), "D (180-350)": ((vs >= 180) & (vs < 350)).sum(),
              "E (<180)": (vs < 180).sum()}
    for k, v in clases.items():
        print(f"  {k}: {v}")
    print(f"Escrito: {SALIDA.relative_to(DATA.parent)} ({SALIDA.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
