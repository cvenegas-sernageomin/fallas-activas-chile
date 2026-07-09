"""Descarga y convierte catastro de Cuarteles de Carabineros a KML.

Fuente: Plataforma de Datos para Resiliencia ante Desastres (Chile).
URL: https://www.plataformadedatos.cl/datasets/es/60d196b8fe2d206e
Formato: Shapefile (929+ cuarteles, comisarías, retenes, tenencias nacionales).
"""
from pathlib import Path
import tempfile
import urllib.request
import zipfile

import geopandas as gpd
import pandas as pd


ORIGEN_URL = "https://www.plataformadedatos.cl/datasets/es/60d196b8fe2d206e"
DESTINO_KML = Path(__file__).resolve().parent.parent / "data" / "seguridad" / "carabineros.kml"


def _es_columna_entera(serie: pd.Series) -> bool:
    """True si serie es numerica y todos sus valores no nulos son enteros exactos."""
    if not pd.api.types.is_numeric_dtype(serie):
        return False
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return False
    return (no_nulos.astype("int64") == no_nulos).all()


def procesar_carabineros(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Prepara GeoDataFrame para export a KML.

    - Asegura proyección EPSG:4326 (WGS84)
    - Crea campo 'Name' legible para popup
    - Sanitiza atributos (NaN → "", floats enteros → int)
    """
    gdf = gdf.to_crs("EPSG:4326")

    # Crear 'Name' field: combina nombre instalación + tipo
    # Buscar columnas que contengan "nombre" (case-insensitive)
    nombre_cols = [col for col in gdf.columns if 'nombre' in col.lower()]
    tipo_cols = [col for col in gdf.columns if 'tipo' in col.lower() or 'tipo_ins' in col.lower()]

    if nombre_cols:
        col_nombre = nombre_cols[0]
        if tipo_cols:
            col_tipo = tipo_cols[0]
            gdf["Name"] = (
                gdf[col_nombre].fillna("").astype(str).str.strip() + " — " +
                gdf[col_tipo].fillna("").astype(str).str.strip()
            )
        else:
            gdf["Name"] = gdf[col_nombre].fillna("").astype(str).str.strip()
    else:
        # Fallback: usar primera columna de texto
        text_cols = [col for col in gdf.columns if gdf[col].dtype == 'object']
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
    # Asegurar que 'Name' esté en el dataframe
    gdf.insert(0, 'Name', atributos.index if 'Name' not in atributos else atributos['Name'])
    return gdf


def descargar_y_procesar():
    """Descarga catastro de Carabineros (shapefile o CSV), convierte a KML."""
    print(f"Procesando catastro de Carabineros...")

    raw_path = Path(__file__).resolve().parent.parent / "data" / "raw"
    raw_path.mkdir(parents=True, exist_ok=True)

    zip_file = raw_path / "carabineros.zip"
    github_zip = raw_path / "carabineros_github.zip"

    # Intentar shapefile primero, luego GitHub CSV
    gdf = None

    # 1. Intentar shapefile
    if zip_file.exists():
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    z.extractall(tmpdir)
                tmp_path = Path(tmpdir)
                shp_files = list(tmp_path.glob("**/*.shp"))
                if shp_files:
                    shp_file = shp_files[0]
                    print(f"  Leyendo shapefile: {shp_file.name}")
                    gdf = gpd.read_file(shp_file)
                    print(f"  {len(gdf)} registros leídos")
        except Exception as e:
            print(f"  Shapefile no válido: {e}")

    # 2. Intentar CSV desde GitHub si shapefile no funcionó
    if gdf is None and github_zip.exists():
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(github_zip, 'r') as z:
                    z.extractall(tmpdir)
                tmp_path = Path(tmpdir)
                csv_files = list(tmp_path.glob("**/*cuarteles*.csv"))
                if csv_files:
                    csv_file = csv_files[0]
                    print(f"  Leyendo CSV desde GitHub: {csv_file.name}")
                    df = pd.read_csv(csv_file)

                    # Detectar columnas de lat/lon (nombres típicos)
                    lat_cols = [c for c in df.columns if 'lat' in c.lower()]
                    lon_cols = [c for c in df.columns if 'lon' in c.lower()]

                    if lat_cols and lon_cols:
                        from shapely.geometry import Point
                        lat_col, lon_col = lat_cols[0], lon_cols[0]
                        df_valid = df.dropna(subset=[lat_col, lon_col])
                        geometry = [Point(lon, lat) for lat, lon in zip(df_valid[lat_col], df_valid[lon_col])]
                        gdf = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")
                        print(f"  {len(gdf)} registros con coordenadas válidas")
        except Exception as e:
            print(f"  GitHub CSV no válido: {e}")

    if gdf is None:
        raise FileNotFoundError(f"No se encontró shapefile ni CSV en {raw_path}")

    gdf = procesar_carabineros(gdf)

    DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(DESTINO_KML, driver="KML")
    print(f"  Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")

    return len(gdf)


if __name__ == "__main__":
    try:
        count = descargar_y_procesar()
        print(f"✓ Conversión completada: {count} registros")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        exit(1)
