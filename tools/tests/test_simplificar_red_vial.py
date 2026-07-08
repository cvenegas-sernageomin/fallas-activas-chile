import geopandas as gpd
from shapely.geometry import LineString

from simplificar_red_vial import simplificar_gdf


def test_simplifica_reduce_vertices_preservando_topologia():
    linea = LineString([(0, 0), (1, 0.0001), (2, -0.0001), (3, 0.0002), (4, 0)])
    gdf = gpd.GeoDataFrame({"col": [1]}, geometry=[linea], crs="EPSG:4326")

    resultado = simplificar_gdf(gdf, tolerancia=0.001)

    assert len(resultado) == 1
    assert len(resultado.geometry.iloc[0].coords) < len(linea.coords)
    assert resultado.crs == gdf.crs


def test_simplifica_no_modifica_el_original():
    linea = LineString([(0, 0), (1, 0.0001), (2, 0)])
    gdf = gpd.GeoDataFrame({"col": [1]}, geometry=[linea], crs="EPSG:4326")

    simplificar_gdf(gdf, tolerancia=0.001)

    assert len(gdf.geometry.iloc[0].coords) == 3
