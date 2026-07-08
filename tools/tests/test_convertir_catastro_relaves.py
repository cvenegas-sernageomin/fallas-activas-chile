import pandas as pd

from convertir_catastro_relaves import construir_geodataframe


def _df_prueba():
    return pd.DataFrame({
        "NOMBRE_FAENA": ["FAENA A", "FAENA B", "FAENA C"],
        "NOMBRE_INSTALACION": ["DEPOSITO 1", "DEPOSITO 2", "SIN COORDENADAS"],
        "LATITUD": [-33.5, -20.9, None],
        "LONGITUD": [-70.6, -68.6, None],
        "ESTADO_INSTALACION": ["ACTIVO", "ABANDONADO", "ACTIVO"],
        "FECHA_RES_APRUEBA": pd.to_datetime(["2022-12-05", None, "2019-01-01"]),
        "RES_PDC_APRUEBA": [None, 123, None],
    })


def test_construir_geodataframe_arma_geometria_desde_lat_lon():
    gdf = construir_geodataframe(_df_prueba())
    assert len(gdf) == 2  # la fila sin coordenadas se descarta
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.iloc[0].x == -70.6
    assert gdf.geometry.iloc[0].y == -33.5


def test_construir_geodataframe_arma_nombre_legible():
    gdf = construir_geodataframe(_df_prueba())
    assert gdf["Name"].iloc[0] == "FAENA A - DEPOSITO 1"
    assert gdf["Name"].iloc[1] == "FAENA B - DEPOSITO 2"


def test_construir_geodataframe_convierte_fechas_y_vacios_a_texto():
    gdf = construir_geodataframe(_df_prueba())
    # fila 0 (FAENA A): tiene fecha real -> queda como texto ISO, no Timestamp
    assert gdf["FECHA_RES_APRUEBA"].iloc[0] == "2022-12-05"
    # fila 1 (FAENA B): NaT/None -> cadena vacia (no "NaT"/"None"), para que el
    # filtro esValorVacio() del visor la descarte igual que un campo -99
    assert gdf["FECHA_RES_APRUEBA"].iloc[1] == ""
    assert gdf["RES_PDC_APRUEBA"].iloc[0] == ""
