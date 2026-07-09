"""Descarga shapefiles desde portales usando requests con sesiones."""
import sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def crear_sesion():
    """Crea sesión con reintentos y User-Agent."""
    sesion = requests.Session()

    # Configurar reintentos
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    sesion.mount('http://', adapter)
    sesion.mount('https://', adapter)

    # User-Agent realista
    sesion.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    return sesion


def descargar_archivo(url, dest_path, nombre, timeout=30):
    """Descarga archivo con manejo de errores y progreso."""
    sesion = crear_sesion()

    print(f"Descargando {nombre}...")
    print(f"  URL: {url}")

    try:
        response = sesion.get(url, timeout=timeout, stream=True, allow_redirects=True)
        response.raise_for_status()

        # Validar que es un archivo (no HTML)
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type:
            print(f"  [WARN] Servidor devolvio HTML (probablemente login requerido)")
            return False

        # Guardar archivo
        total_size = int(response.headers.get('content-length', 0))

        with open(dest_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = (downloaded / total_size) * 100
                        print(f"  {pct:.1f}%", end='\r')

        actual_size = dest_path.stat().st_size
        print(f"  [OK] Descargado: {actual_size:,} bytes")
        return True

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    outdir = Path(__file__).resolve().parent.parent / "data" / "raw"
    outdir.mkdir(parents=True, exist_ok=True)

    # URLs de Plataforma de Datos (endpoints de API)
    descargas = {
        "carabineros": "https://www.plataformadedatos.cl/datasets/es/60d196b8fe2d206e.zip",
        "educacion": "https://www.plataformadedatos.cl/datasets/es/925766d40b2366d.zip",
        "puentes": "https://www.plataformadedatos.cl/datasets/es/342f459b50db60f4.zip",
    }

    print("=" * 70)
    print("DESCARGANDO SHAPEFILES DE PLATAFORMA DE DATOS")
    print("=" * 70)
    print()

    exitosos = []
    fallidos = []

    for nombre, url in descargas.items():
        dest = outdir / f"{nombre}.zip"

        if descargar_archivo(url, dest, nombre):
            exitosos.append(nombre)
        else:
            fallidos.append(nombre)
        print()

    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    if exitosos:
        print(f"[OK] Descargados ({len(exitosos)}): {', '.join(exitosos)}")
    if fallidos:
        print(f"[WARN] Fallidos ({len(fallidos)}): {', '.join(fallidos)}")
        print()
        print("Para descargas fallidas, ir a:")
        for nombre, url in descargas.items():
            if nombre in fallidos:
                print(f"  {nombre}: {url.replace('.zip', '')}")

    return 0 if not fallidos else 1


if __name__ == "__main__":
    sys.exit(main())
