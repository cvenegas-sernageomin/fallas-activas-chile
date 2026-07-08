"""Re-exporta red_vial.shp con geometria simplificada.

El KMZ original (72 MB comprimido, ~7 millones de vertices) es demasiado pesado para
cargar/parsear en el navegador. Con tolerancia 0.0005 (~50 m) se reduce a ~156.000
vertices (97.8% de reduccion, verificado durante el diseno) y el KML resultante queda
en ~20 MB — mismo orden de magnitud que el precedente de simplificar 26.180 glaciares
en Catastro Glaciares/generar_kmz_glaciares.py.
"""
from pathlib import Path

import geopandas as gpd

TOLERANCIA = 0.0005
# ORIGEN_SHP vive en "infraestructura-critica-chile", un proyecto HERMANO ubicado
# junto a este repo (no forma parte de fallas-activas-chile). Se espera que ambos
# repos compartan el mismo directorio padre en la maquina donde se ejecuta esto.
ORIGEN_SHP = (
    Path(__file__).resolve().parent.parent.parent
    / "infraestructura-critica-chile" / "transporte" / "red_vial.shp"
)
DESTINO_KML = Path(__file__).resolve().parent.parent / "data" / "transporte" / "red_vial.kml"


def simplificar_gdf(gdf: gpd.GeoDataFrame, tolerancia: float) -> gpd.GeoDataFrame:
    """Devuelve una copia de gdf con la geometria simplificada (preserve_topology=True)."""
    resultado = gdf.copy()
    resultado["geometry"] = resultado.geometry.simplify(tolerancia, preserve_topology=True)
    return resultado


def main() -> None:
    if not ORIGEN_SHP.exists():
        raise FileNotFoundError(
            f"No se encontro {ORIGEN_SHP}. Se espera que 'infraestructura-critica-chile' "
            "sea un directorio hermano de este repo (ver docs/superpowers/specs para el origen del dato)."
        )
    print(f"Leyendo {ORIGEN_SHP} ...")
    gdf = gpd.read_file(ORIGEN_SHP)
    print(f"  {len(gdf)} features")
    simplificado = simplificar_gdf(gdf, TOLERANCIA)
    DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
    simplificado.to_file(DESTINO_KML, driver="KML")
    print(f"Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
