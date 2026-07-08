import geopandas as gpd
from shapely.geometry import LineString

from simplificar_red_vial import simplificar_gdf


def test_simplifica_reduce_vertices_y_preserva_crs():
    linea = LineString([(0, 0), (1, 0.0001), (2, -0.0001), (3, 0.0002), (4, 0)])
    gdf = gpd.GeoDataFrame({"col": [1]}, geometry=[linea], crs="EPSG:4326")

    resultado = simplificar_gdf(gdf, tolerancia=0.001)

    assert len(resultado) == 1
    assert len(resultado.geometry.iloc[0].coords) < len(linea.coords)
    assert resultado.crs == gdf.crs


def test_simplifica_preserva_topologia_evitando_autointerseccion():
    # Coordenadas encontradas empiricamente: con tolerancia ~2.7-3.0,
    # simplify(preserve_topology=False) colapsa esta linea en una geometria
    # que se autointersecta (is_simple == False), mientras que
    # preserve_topology=True (el modo que usa simplificar_gdf) evita ese
    # colapso y conserva una linea simple. Esto verifica de forma concreta
    # que preserve_topology=True realmente esta activo, en vez de solo
    # revisar el conteo de vertices.
    coords = [
        (-4.039513261625213, -8.025115680688401),
        (-7.150788990732611, 7.860220420989062),
        (-4.841314200235434, 8.831550304255096),
        (7.990030068303085, -8.962437629318318),
        (-5.207540727833848, 1.9400923827333845),
        (-5.270177648517573, 0.17242547160237542),
    ]
    linea = LineString(coords)
    assert linea.is_simple  # geometria de partida valida

    # Sin preservar topologia, esta linea se autointersecta al simplificar.
    assert linea.simplify(2.8, preserve_topology=False).is_simple is False

    gdf = gpd.GeoDataFrame({"col": [1]}, geometry=[linea], crs="EPSG:4326")
    resultado = simplificar_gdf(gdf, tolerancia=2.8)

    assert resultado.geometry.iloc[0].is_simple
    assert len(resultado.geometry.iloc[0].coords) < len(linea.coords)


def test_simplifica_no_modifica_el_original():
    linea = LineString([(0, 0), (1, 0.0001), (2, 0)])
    gdf = gpd.GeoDataFrame({"col": [1]}, geometry=[linea], crs="EPSG:4326")

    simplificar_gdf(gdf, tolerancia=0.001)

    assert len(gdf.geometry.iloc[0].coords) == 3
