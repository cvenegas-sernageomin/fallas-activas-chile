"""Descarga el catalogo nacional CHAF v1 (PANGAEA, CC-BY 4.0) y extrae red_fallas.kml.

Fuente: Melnick, Maldonado & Contreras (2020), doi:10.1594/PANGAEA.922241.
Acceso directo sin autenticacion (verificado durante el diseno de este proyecto).
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kmz_utils import contar_placemarks, extraer_doc_kml

URL_CHAF = "https://download.pangaea.de/dataset/922241/files/CHAF_Pangaea_v1.kmz"
DESTINO = Path(__file__).resolve().parent.parent / "data" / "red_fallas.kml"
TOTAL_ESPERADO = 958


def descargar_kmz(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> None:
    print(f"Descargando {URL_CHAF} ...")
    kmz_bytes = descargar_kmz(URL_CHAF)
    print(f"  {len(kmz_bytes):,} bytes")
    kml_text = extraer_doc_kml(kmz_bytes)
    total = contar_placemarks(kml_text)
    print(f"  {total} fallas (Placemarks)")
    if total != TOTAL_ESPERADO:
        print(f"  ADVERTENCIA: se esperaban {TOTAL_ESPERADO} fallas, se obtuvieron {total}")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(kml_text, encoding="utf-8")
    print(f"Escrito: {DESTINO}")


if __name__ == "__main__":
    main()
