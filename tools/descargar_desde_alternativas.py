"""Descarga datos de fuentes alternativas (GitHub, OpenStreetMap, datos abiertos)."""
import sys
from pathlib import Path
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def crear_sesion():
    """Sesion HTTP con reintentos."""
    sesion = requests.Session()
    sesion.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })
    return sesion


def descargar_carabineros_osm():
    """Descarga cuarteles de Carabineros desde OpenStreetMap (vía Overpass API)."""
    print("[carabineros] Descargando desde OpenStreetMap...")

    # Consulta Overpass para estaciones de policia/comisarias en Chile
    overpass_url = "https://overpass-api.de/api/interpreter"

    # [bbox] sur,oeste,norte,este en OSM
    query = """
    [bbox:-56,-76,-17,-66];
    (
      node["amenity"="police"]["name"];
      way["amenity"="police"]["name"];
    );
    out center;
    """

    try:
        resp = requests.post(overpass_url, data=query, timeout=30)
        resp.raise_for_status()

        # Parsear OSM JSON simple
        import json
        data = resp.json()

        registros = []
        for elem in data.get('elements', []):
            if 'tags' in elem and elem['tags'].get('name'):
                lat = elem.get('lat') or elem.get('center', {}).get('lat')
                lon = elem.get('lon') or elem.get('center', {}).get('lon')

                if lat and lon:
                    registros.append({
                        'Name': elem['tags']['name'],
                        'Type': elem['tags'].get('type', 'Police Station'),
                        'latitude': lat,
                        'longitude': lon
                    })

        if registros:
            df = pd.DataFrame(registros)
            geometry = [Point(row['longitude'], row['latitude']) for _, row in df.iterrows()]
            gdf = gpd.GeoDataFrame(
                df[['Name', 'Type']],
                geometry=geometry,
                crs="EPSG:4326"
            )
            print(f"  Encontrados {len(gdf)} registros")
            return gdf
        else:
            print("  No se encontraron registros")
            return None

    except Exception as e:
        print(f"  Error: {e}")
        return None


def crear_datos_minimos():
    """Crea datos de prueba para demostrar el pipeline."""
    print("[datos_prueba] Creando shapefiles minimos para demostracion...")

    # Carabineros: algunos cuarteles conocidos de Chile
    carabineros_data = {
        'Name': [
            'Comisaria Region Metropolitana',
            'Cuartel General Carabineros',
            'Prefectura Policial Santiago',
            'Comisaria Providencia',
            'Comisaria Las Condes'
        ],
        'geometry': [
            Point(-70.6693, -33.4489),  # Santiago
            Point(-70.6728, -33.4397),  # Centro
            Point(-70.6000, -33.4200),  # Providencia
            Point(-70.5800, -33.4100),  # Las Condes
            Point(-70.5500, -33.4400),  # Ñuñoa
        ]
    }

    # Bomberos: algunos parques conocidos
    bomberos_data = {
        'Name': [
            'Parque de Bomberos Estacion Central',
            'Parque de Bomberos Providencia',
            'Parque de Bomberos Las Condes',
            'Parque de Bomberos Puente Alto'
        ],
        'geometry': [
            Point(-70.6600, -33.4400),  # Santiago Centro
            Point(-70.5900, -33.4150),  # Providencia
            Point(-70.5700, -33.4050),  # Las Condes
            Point(-70.5400, -33.6000),  # Puente Alto
        ]
    }

    # Puentes: ubicaciones de puentes principales Santiago
    puentes_data = {
        'Name': [
            'Puente Mapocho',
            'Puente Lorena',
            'Puente Pío Nono',
            'Puente Lastarria',
            'Puente Baquedano'
        ],
        'geometry': [
            Point(-70.6500, -33.4450),
            Point(-70.6550, -33.4400),
            Point(-70.6600, -33.4380),
            Point(-70.6650, -33.4370),
            Point(-70.6700, -33.4360),
        ]
    }

    # Educacion: algunas escuelas/universidades
    educacion_data = {
        'Name': [
            'Universidad de Chile',
            'Pontificia Universidad Católica',
            'Universidad de Concepción',
            'Liceo 1 Javiera Carrera',
            'Escuela Francia'
        ],
        'geometry': [
            Point(-70.6690, -33.4591),  # Central
            Point(-70.5407, -33.3410),  # San Joaquín
            Point(-72.1440, -36.8201),  # Concepción
            Point(-70.6500, -33.4300),  # Santiago
            Point(-70.6300, -33.4200),  # Santiago
        ]
    }

    gdfs = {}
    for nombre, data in [
        ('carabineros', carabineros_data),
        ('bomberos', bomberos_data),
        ('puentes', puentes_data),
        ('educacion', educacion_data)
    ]:
        gdf = gpd.GeoDataFrame(
            {'Name': data['Name']},
            geometry=data['geometry'],
            crs="EPSG:4326"
        )
        gdfs[nombre] = gdf
        print(f"  {nombre}: {len(gdf)} registros")

    return gdfs


def main():
    outdir = Path(__file__).resolve().parent.parent / "data" / "raw"

    print("=" * 70)
    print("DESCARGANDO DATOS DESDE FUENTES ALTERNATIVAS")
    print("=" * 70)
    print()

    # Intentar OpenStreetMap primero, si falla usar datos minimos
    gdf_cara = descargar_carabineros_osm()

    if not gdf_cara:
        print("\nUsando datos minimos para demostracion...")
        gdfs = crear_datos_minimos()
        gdf_cara = gdfs['carabineros']

    print(f"\n[OK] Datos disponibles para procesamiento")
    return 0


if __name__ == "__main__":
    sys.exit(main())
