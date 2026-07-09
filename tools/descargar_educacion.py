"""Descarga y convierte catastro de Establecimientos Educacionales a KML.

Fuente: MINEDUC (Ministerio de Educación) - Plataforma de Datos.
URL: https://www.plataformadedatos.cl/datasets/es/925766D40B2366D
Formato: Shapefile con establecimientos de educación escolar nacional.
"""
from pathlib import Path
import tempfile
import zipfile

import geopandas as gpd
import pandas as pd


DESTINO_KML = Path(__file__).resolve().parent.parent / "data" / "educacion" / "establecimientos_educacion.kml"


def _es_columna_entera(serie: pd.Series) -> bool:
    """True si serie es numerica y todos sus valores no nulos son enteros exactos."""
    if not pd.api.types.is_numeric_dtype(serie):
        return False
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return False
    return (no_nulos.astype("int64") == no_nulos).all()


def procesar_educacion(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Prepara GeoDataFrame para export a KML.

    - Asegura proyección EPSG:4326 (WGS84)
    - Crea campo 'Name' legible para popup
    - Sanitiza atributos (NaN → "", floats enteros → int)
    """
    gdf = gdf.to_crs("EPSG:4326")

    # Crear 'Name' field: busca columnas de nombre
    nombre_cols = [col for col in gdf.columns if any(
        x in col.lower() for x in ['nombre', 'name', 'rbd_nombre', 'nombre_establecimiento']
    )]

    if nombre_cols:
        col_nombre = nombre_cols[0]
        gdf["Name"] = gdf[col_nombre].fillna("").astype(str).str.strip()
    else:
        # Fallback
        text_cols = [col for col in gdf.columns if gdf[col].dtype == 'object' and col != 'geometry']
        if text_cols:
            gdf["Name"] = gdf[text_cols[0]].fillna("")
        else:
            gdf["Name"] = gdf.index.astype(str)

    # Sanitizar atributos
    atributos = gdf.drop(columns=['Name', 'geometry']).copy()
    for col in atributos.columns:
        serie = atributos[col]
        if pd.api.types.is_datetime64_any_dtype(serie):
            atributos[col] = serie.dt.strftime("%Y-%m-%d")
        elif _es_columna_entera(serie):
            atributos[col] = serie.apply(lambda v: "" if pd.isna(v) else str(int(v)))
        else:
            atributos[col] = serie.where(serie.notna(), "")

    gdf = gpd.GeoDataFrame(atributos, geometry=gdf.geometry, crs=gdf.crs)
    gdf.insert(0, 'Name', atributos.index if 'Name' not in atributos else atributos['Name'])
    return gdf


def descargar_y_procesar():
    """Descarga shapefile de Educación, convierte a KML."""
    print(f"Descargando catastro de Establecimientos Educacionales...")

    raw_path = Path(__file__).resolve().parent.parent / "data" / "raw"
    raw_path.mkdir(parents=True, exist_ok=True)

    zip_file = raw_path / "educacion.zip"

    if not zip_file.exists():
        print(f"⚠️  Descarga manual requerida:")
        print(f"  URL: https://www.plataformadedatos.cl/datasets/es/925766D40B2366D")
        print(f"  Guardar en: {zip_file}")
        raise FileNotFoundError(f"Falta {zip_file}")

    # Extraer shapefile
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_file, 'r') as z:
            z.extractall(tmpdir)

        tmp_path = Path(tmpdir)
        shp_files = list(tmp_path.glob("**/*.shp"))

        if not shp_files:
            raise FileNotFoundError(f"No se encontró .shp en {zip_file}")

        shp_file = shp_files[0]
        print(f"  Leyendo: {shp_file.name}")

        gdf = gpd.read_file(shp_file)
        print(f"  {len(gdf)} registros leídos")

        gdf = procesar_educacion(gdf)

        DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(DESTINO_KML, driver="KML")
        print(f"  Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")

        return len(gdf)


if __name__ == "__main__":
    try:
        count = descargar_y_procesar()
        print(f"✓ Conversión completada: {count} registros")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        exit(1)
