"""Extrae el doc.kml de cada KMZ de infraestructura-critica-chile a data/<sector>/<nombre>.kml.

red_vial se excluye: lo maneja simplificar_red_vial.py aparte (ver ese script), porque
necesita simplificar geometria antes de exportar, no solo copiar el KML tal cual.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kmz_utils import extraer_doc_kml

RAIZ_INFRA = Path(__file__).resolve().parent.parent.parent / "infraestructura-critica-chile"
DESTINO_DATA = Path(__file__).resolve().parent.parent / "data"
EXCLUIR = {"red_vial"}


def rutas_kmz(raiz_infra: Path):
    """Todos los .kmz de primer nivel bajo cada carpeta de sector en raiz_infra, salvo EXCLUIR."""
    return sorted(p for p in raiz_infra.glob("*/*.kmz") if p.stem not in EXCLUIR)


def ruta_salida(kmz_path: Path, raiz_infra: Path, destino_data: Path) -> Path:
    """data/<sector>/<nombre>.kml, preservando el nombre de la carpeta de sector de origen."""
    sector = kmz_path.parent.name
    return destino_data / sector / (kmz_path.stem + ".kml")


def main() -> None:
    kmzs = rutas_kmz(RAIZ_INFRA)
    print(f"{len(kmzs)} archivos KMZ a extraer (excluidos: {sorted(EXCLUIR)})")
    for kmz in kmzs:
        kml_text = extraer_doc_kml(str(kmz))
        salida = ruta_salida(kmz, RAIZ_INFRA, DESTINO_DATA)
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(kml_text, encoding="utf-8")
        print(f"  OK: {kmz} -> {salida}")


if __name__ == "__main__":
    main()
