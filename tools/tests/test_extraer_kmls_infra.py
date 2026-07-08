from pathlib import Path

from extraer_kmls_infra import ruta_salida, rutas_kmz


def _tocar(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"PK")  # contenido irrelevante para estas pruebas


def test_rutas_kmz_encuentra_kmz_de_cada_sector(tmp_path):
    _tocar(tmp_path / "agua" / "bocatomas.kmz")
    _tocar(tmp_path / "energia" / "gasoductos.kmz")
    _tocar(tmp_path / "energia" / "gasoductos.shp")  # no es .kmz, se ignora

    encontrados = rutas_kmz(tmp_path)

    assert sorted(p.name for p in encontrados) == ["bocatomas.kmz", "gasoductos.kmz"]


def test_rutas_kmz_excluye_red_vial(tmp_path):
    _tocar(tmp_path / "transporte" / "red_vial.kmz")
    _tocar(tmp_path / "transporte" / "red_ferrea.kmz")

    encontrados = rutas_kmz(tmp_path)

    assert [p.name for p in encontrados] == ["red_ferrea.kmz"]


def test_rutas_kmz_excluye_ambos_nombres(tmp_path):
    _tocar(tmp_path / "transporte" / "red_vial.kmz")
    _tocar(tmp_path / "transporte" / "red_ferrea.kmz")
    _tocar(tmp_path / "relaves" / "relaves_sernageomin_2018.kmz")
    _tocar(tmp_path / "relaves" / "otra_capa.kmz")

    encontrados = rutas_kmz(tmp_path)

    assert sorted(p.name for p in encontrados) == ["otra_capa.kmz", "red_ferrea.kmz"]


def test_ruta_salida_preserva_sector_y_cambia_extension(tmp_path):
    raiz_infra = tmp_path / "infraestructura-critica-chile"
    destino_data = tmp_path / "fallas-activas-chile" / "data"
    kmz = raiz_infra / "agua" / "bocatomas.kmz"

    salida = ruta_salida(kmz, raiz_infra, destino_data)

    assert salida == destino_data / "agua" / "bocatomas.kml"
