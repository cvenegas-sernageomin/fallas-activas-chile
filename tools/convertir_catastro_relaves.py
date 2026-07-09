"""Convierte el catastro SERNAGEOMIN de depositos de relaves (Oct-2025, Excel) a KML.

Reemplaza relaves_sernageomin_2018.kml (742 registros, sourced from
infraestructura-critica-chile/) por un catastro mas reciente y completo (836 registros,
Octubre 2025) que el usuario aporto directamente como planilla Excel. Fuente:
SERNAGEOMIN, "Catastro de Depositos de Relaves" (DS 248/2007).
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

ORIGEN_XLSX = (
    Path(__file__).resolve().parent.parent.parent
    / "Fallas Activas" / "Info" / "CATASTRO_RELAVES_CHILE_OCT2025.xlsx"
)
DESTINO_KML = Path(__file__).resolve().parent.parent / "data" / "relaves" / "relaves_sernageomin_2025.kml"
HOJA = "CDR_CHILE"
FILA_ENCABEZADO = 6  # 0-indexed: las primeras 6 filas del Excel son titulo/metadata


def leer_catastro(ruta_xlsx: Path, hoja: str = HOJA, fila_encabezado: int = FILA_ENCABEZADO) -> pd.DataFrame:
    """Lee la hoja de datos del catastro, saltando las filas de titulo/metadata iniciales."""
    return pd.read_excel(ruta_xlsx, sheet_name=hoja, header=fila_encabezado)


def _es_columna_entera(serie: pd.Series) -> bool:
    """True si `serie` es numerica y todos sus valores no nulos son enteros exactos.

    Columnas como CANTIDAD_MUROS__CONTENCION_ o RES_PDC_APRUEBA llegan desde Excel
    como float64 (porque la columna tiene NaN mezclados con enteros), pero
    representan cantidades enteras. Se compara contra la version en int64 en vez
    de usar `float.is_integer` para no depender de que cada valor individual sea
    ya un `float` de Python (puede ser numpy.float64/int64 segun el dtype de origen).
    """
    if not pd.api.types.is_numeric_dtype(serie):
        return False
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return False
    return (no_nulos.astype("int64") == no_nulos).all()


def construir_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Arma un GeoDataFrame EPSG:4326 desde las columnas LATITUD/LONGITUD.

    - Descarta filas sin coordenadas.
    - Arma 'Name' = NOMBRE_FAENA + " - " + NOMBRE_INSTALACION (mismo patron que
      shp_a_kmz.py: un campo 'Name' legible es lo que el driver KML de geopandas
      usa como <name> del Placemark). Se aplica fillna("") explicito antes del
      astype(str)/concatenacion en vez de confiar en que un NaN sobreviva sin
      convertirse en el string literal "nan" (comportamiento que depende de la
      version de pandas y no esta fijado por un test).
    - Convierte columnas de fecha a texto ISO (el driver KML no serializa
      datetime64 de forma confiable) y reemplaza NaN/None por cadena vacia en
      TODOS los atributos, para que el filtro esValorVacio() del visor los
      descarte igual que un campo -99 (en vez de mostrar literalmente "NaT"/"None").
    - Columnas numericas cuyos valores no nulos son todos enteros (ver
      _es_columna_entera) se formatean sin el ".0" espurio que deja
      float-to-string (ej. CANTIDAD_MUROS__CONTENCION_: "1" en vez de "1.0").
    """
    df = df.dropna(subset=["LATITUD", "LONGITUD"]).copy()
    geometry = [Point(lon, lat) for lat, lon in zip(df["LATITUD"], df["LONGITUD"])]
    df["Name"] = (
        df["NOMBRE_FAENA"].fillna("").astype(str).str.strip()
        + " - "
        + df["NOMBRE_INSTALACION"].fillna("").astype(str).str.strip()
    )
    atributos = df.drop(columns=["LATITUD", "LONGITUD"]).copy()
    for col in atributos.columns:
        serie = atributos[col]
        if pd.api.types.is_datetime64_any_dtype(serie):
            atributos[col] = serie.dt.strftime("%Y-%m-%d")
        elif _es_columna_entera(serie):
            atributos[col] = serie.apply(lambda v: "" if pd.isna(v) else str(int(v)))
            continue
        atributos[col] = atributos[col].where(atributos[col].notna(), "")
    return gpd.GeoDataFrame(atributos, geometry=geometry, crs="EPSG:4326")


def main() -> None:
    if not ORIGEN_XLSX.exists():
        raise FileNotFoundError(
            f"No se encontro {ORIGEN_XLSX}. Se espera la planilla del catastro de relaves "
            "en 'Fallas Activas/Info/' (directorio hermano de este repo)."
        )
    print(f"Leyendo {ORIGEN_XLSX} (hoja '{HOJA}') ...")
    df = leer_catastro(ORIGEN_XLSX)
    print(f"  {len(df)} filas leidas")
    gdf = construir_geodataframe(df)
    print(f"  {len(gdf)} depositos con coordenadas validas")
    print(f"  {len(df) - len(gdf)} registros descartados por falta de coordenadas")
    DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(DESTINO_KML, driver="KML")
    print(f"Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
