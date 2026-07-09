"""Crea capas KML de prueba para integrar al visor.

Datos de prueba basados en ubicaciones conocidas de Chile.
Reemplazar con shapefiles reales una vez descargados.
"""
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def crear_carabineros():
    """Crea capa de Carabineros con datos de ejemplo."""
    data = {
        'Name': [
            'Comisaria Region Metropolitana',
            'Cuartel General Carabineros',
            'Prefectura Policial Santiago',
            'Comisaria Providencia',
            'Comisaria Las Condes'
        ],
        'Region': ['RM', 'RM', 'RM', 'RM', 'RM'],
        'Tipo': ['Comisaria', 'Cuartel', 'Prefectura', 'Comisaria', 'Comisaria']
    }

    geometry = [
        Point(-70.6693, -33.4489),
        Point(-70.6728, -33.4397),
        Point(-70.6000, -33.4200),
        Point(-70.5800, -33.4100),
        Point(-70.5500, -33.4400)
    ]

    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
    return gdf


def crear_bomberos():
    """Crea capa de Bomberos con datos de ejemplo."""
    data = {
        'Name': [
            'Parque Estacion Central',
            'Parque Providencia',
            'Parque Las Condes',
            'Parque Puente Alto',
            'Parque Maipu'
        ],
        'Region': ['RM', 'RM', 'RM', 'RM', 'RM'],
        'Personal': [45, 38, 42, 35, 40]
    }

    geometry = [
        Point(-70.6600, -33.4400),
        Point(-70.5900, -33.4150),
        Point(-70.5700, -33.4050),
        Point(-70.5400, -33.6000),
        Point(-70.7100, -33.6200)
    ]

    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
    return gdf


def crear_puentes():
    """Crea capa de Puentes con datos de ejemplo."""
    data = {
        'Name': [
            'Puente Mapocho',
            'Puente Lorena',
            'Puente Pio Nono',
            'Puente Lastarria',
            'Puente Baquedano'
        ],
        'Tipo': ['Hormigon', 'Acero', 'Acero', 'Hormigon', 'Acero'],
        'Estado': ['Bueno', 'Bueno', 'Regular', 'Bueno', 'Bueno']
    }

    geometry = [
        Point(-70.6500, -33.4450),
        Point(-70.6550, -33.4400),
        Point(-70.6600, -33.4380),
        Point(-70.6650, -33.4370),
        Point(-70.6700, -33.4360)
    ]

    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
    return gdf


def crear_educacion():
    """Crea capa de Establecimientos Educacionales."""
    data = {
        'Name': [
            'Universidad de Chile',
            'Pontificia Universidad Catolica',
            'Universidad de Concepcion',
            'Liceo 1 Javiera Carrera',
            'Escuela Francia'
        ],
        'Tipo': ['Universidad', 'Universidad', 'Universidad', 'Liceo', 'Escuela'],
        'Estudiantes': [32000, 28000, 25000, 1200, 800]
    }

    geometry = [
        Point(-70.6690, -33.4591),
        Point(-70.5407, -33.3410),
        Point(-72.1440, -36.8201),
        Point(-70.6500, -33.4300),
        Point(-70.6300, -33.4200)
    ]

    gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
    return gdf


def main():
    """Crea todos los KML."""
    base_path = Path(__file__).resolve().parent.parent / "data"

    capas = {
        "seguridad/carabineros": crear_carabineros(),
        "seguridad/bomberos": crear_bomberos(),
        "transporte/puentes": crear_puentes(),
        "educacion/establecimientos_educacion": crear_educacion()
    }

    print("=" * 70)
    print("CREANDO CAPAS DE DEMOSTRACION")
    print("=" * 70)

    for nombre, gdf in capas.items():
        ruta = base_path / f"{nombre}.kml"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(ruta, driver="KML")
        print(f"  {nombre}: {len(gdf)} registros -> {ruta.name}")

    print()
    print("[INFO] Capas de prueba creadas.")
    print("[INFO] Reemplazar con datos reales descargados desde:")
    print("       https://www.plataformadedatos.cl/")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
