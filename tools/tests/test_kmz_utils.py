import io
import zipfile

from kmz_utils import contar_placemarks, extraer_doc_kml


def _kmz_bytes(kml_text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml_text)
    return buf.getvalue()


def test_extrae_doc_kml_desde_bytes():
    kml = "<kml><Document><Placemark/></Document></kml>"
    assert extraer_doc_kml(_kmz_bytes(kml)) == kml


def test_extrae_doc_kml_desde_ruta(tmp_path):
    kml = "<kml><Document></Document></kml>"
    ruta = tmp_path / "prueba.kmz"
    ruta.write_bytes(_kmz_bytes(kml))
    assert extraer_doc_kml(str(ruta)) == kml


def test_contar_placemarks_cuenta_dos():
    kml = "<Placemark></Placemark><Placemark></Placemark>"
    assert contar_placemarks(kml) == 2


def test_contar_placemarks_cero_sin_placemarks():
    assert contar_placemarks("<Document></Document>") == 0
