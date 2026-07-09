"""Convierte los shapefiles REALES de infraestructura critica (descargados por el
usuario) a KML para el visor, reemplazando los datos demo/placeholder previos.

Los shapefiles vienen de portales de gobierno con encodings inconsistentes (unos
UTF-8 reales, otros doble-codificados utf8->latin1, otros latin1 con un byte
corrupto). Se detecta el encoding por archivo probando configs de GDAL y eligiendo
la que no deja mojibake; si ninguna limpia, se repara el mojibake con round-trip
latin1->utf-8. Puentes ademas viene en EPSG:5360 y se reproyecta a 4326.

Fuentes: Carabineros/Puentes/Educacion de plataformadedatos.cl; Bomberos de geoportal.cl.
Salida: reemplaza data/{sector}/{capa}.kml que el visor ya referencia en LAYER_DEFS.
"""
from pathlib import Path
import glob
import tempfile
import zipfile

import geopandas as gpd
import pandas as pd
import pyogrio

DATA = Path(__file__).resolve().parent.parent / "data"

# zip fuente en data/raw/, columna de nombre, y KML de salida (lo que el visor referencia).
RAW = DATA / "raw"
CAPAS = [
    {"nombre": "Carabineros", "zip": RAW / "cuarteles.zip",
     "name_col": "nombre", "salida": DATA / "seguridad" / "carabineros.kml"},
    {"nombre": "Bomberos", "zip": RAW / "bomberos_src.zip",
     "name_col": "nombre", "salida": DATA / "seguridad" / "bomberos.kml"},
    {"nombre": "Puentes", "zip": RAW / "puentes_src.zip",
     "name_col": "NOMBRE_PUE", "salida": DATA / "transporte" / "puentes.kml"},
    {"nombre": "Educacion", "zip": RAW / "educacion_src.zip",
     "name_col": "Nombre_del", "salida": DATA / "educacion" / "establecimientos_educacion.kml"},
]


def _reparar_mojibake(s):
    """Revierte texto UTF-8 que fue leido como latin-1 ('EspaÃ±a' -> 'España')."""
    if not isinstance(s, str) or ("Ã" not in s and "Â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s.encode("latin-1", "ignore").decode("utf-8", "replace")


def _score_mojibake(gdf) -> int:
    muestra = " ".join(str(v) for v in gdf.select_dtypes(include="object").head(400).values.ravel())
    return muestra.count("Ã") + muestra.count("Â") + muestra.count("�")


def leer_shp(shp: str):
    """Lee un shapefile detectando su encoding; repara mojibake si hace falta."""
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
        sc = _score_mojibake(g)
        if sc == 0:
            return g, f"{cfg or 'auto'}"
        if mejor is None or sc < mejor[2]:
            mejor = (g, f"{cfg or 'auto'}", sc)
    # ninguna config quedo limpia: usar la menos mala y reparar mojibake explicito.
    # Se deduplican los nombres ANTES de iterar (hay .dbf con columnas repetidas,
    # ej. educacion tiene 'Coordenada' dos veces) para que g[col] sea una Serie y no
    # un DataFrame.
    g = mejor[0].copy()
    g.columns = _dedupe_columnas([_reparar_mojibake(c) for c in g.columns])
    for col in g.columns:
        if col == "geometry":
            continue
        if g[col].dtype == object:
            g[col] = g[col].map(_reparar_mojibake)
    return g, f"{mejor[1]}+reparado"


def _dedupe_columnas(cols):
    """Renombra columnas repetidas (el .dbf trunca nombres a 10 chars y colisionan)."""
    vistas, salida = {}, []
    for c in cols:
        if c in vistas:
            vistas[c] += 1
            salida.append(f"{c}_{vistas[c]}")
        else:
            vistas[c] = 0
            salida.append(c)
    return salida


def _es_columna_entera(serie: pd.Series) -> bool:
    if not pd.api.types.is_numeric_dtype(serie):
        return False
    no_nulos = serie.dropna()
    return (not no_nulos.empty) and (no_nulos.astype("int64") == no_nulos).all()


def procesar(capa: dict) -> int:
    if not capa["zip"].exists():
        print(f"[SKIP] {capa['nombre']}: no existe {capa['zip']}")
        return 0
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(capa["zip"]) as zf:
            zf.extractall(td)
        shp = glob.glob(f"{td}/**/*.shp", recursive=True)[0]
        gdf, enc = leer_shp(shp)
        print(f"[{capa['nombre']}] {len(gdf)} features | encoding: {enc}")

        gdf.columns = _dedupe_columnas(list(gdf.columns))
        gdf = gdf.to_crs("EPSG:4326")

        # Campo Name (lo que el driver KML mapea a <name> del Placemark)
        ncol = capa["name_col"]
        if ncol not in gdf.columns:
            ncol = next((c for c in gdf.columns if "nomb" in c.lower() or "name" in c.lower()), None)
        gdf["Name"] = gdf[ncol].map(_reparar_mojibake).fillna("").astype(str).str.strip() if ncol else ""

        # Sanitizar atributos: fechas->ISO, enteros sin ".0", NaN->""
        atributos = gdf.drop(columns=["geometry", "Name"]).copy()
        for col in atributos.columns:
            serie = atributos[col]
            if pd.api.types.is_datetime64_any_dtype(serie):
                atributos[col] = serie.dt.strftime("%Y-%m-%d")
            elif _es_columna_entera(serie):
                atributos[col] = serie.apply(lambda v: "" if pd.isna(v) else str(int(v)))
            else:
                atributos[col] = serie.where(serie.notna(), "")
        out = gpd.GeoDataFrame(atributos, geometry=gdf.geometry, crs="EPSG:4326")
        out.insert(0, "Name", gdf["Name"].values)

        capa["salida"].parent.mkdir(parents=True, exist_ok=True)
        if capa["salida"].exists():
            capa["salida"].unlink()
        out.to_file(capa["salida"], driver="KML")
        print(f"           -> {capa['salida'].relative_to(DATA.parent)} ({capa['salida'].stat().st_size:,} bytes)")
        return len(out)


def main():
    print("=" * 70)
    print("PROCESANDO SHAPEFILES REALES DE INFRAESTRUCTURA -> KML")
    print("=" * 70)
    total = 0
    for capa in CAPAS:
        total += procesar(capa)
        print()
    print(f"Total features convertidos: {total:,}")


if __name__ == "__main__":
    main()
