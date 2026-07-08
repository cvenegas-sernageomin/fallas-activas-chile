"""Utilidad compartida para leer el doc.kml embebido en un archivo KMZ."""
import io
import zipfile


def extraer_doc_kml(kmz_source) -> str:
    """Lee y decodifica doc.kml de un KMZ.

    kmz_source puede ser una ruta (str) o los bytes crudos del KMZ ya descargado.
    """
    fuente = io.BytesIO(kmz_source) if isinstance(kmz_source, (bytes, bytearray)) else kmz_source
    with zipfile.ZipFile(fuente) as z:
        return z.read("doc.kml").decode("utf-8")


def contar_placemarks(kml_text: str) -> int:
    """Cuenta ocurrencias de <Placemark en el texto KML (conteo rapido, sin parsear XML)."""
    return kml_text.count("<Placemark")
