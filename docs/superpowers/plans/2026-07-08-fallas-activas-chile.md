# Visor Fallas Activas + Infraestructura Crítica — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, single-file web viewer (`fallas-activas-chile/visor-web/index.html`) that shows Chile's national active-fault catalog (CHAF v1) together with 26 national critical-infrastructure layers, and publish it to GitHub Pages.

**Architecture:** Clone the proven `alertas-redes/visor-web/index.html` pattern (Leaflet + React UMD + Babel Standalone, one HTML file, KML parsed in a Web Worker) but strip all cron/backend logic since every layer here is static. Add a generic KML parser that handles both points and lines (including `MultiGeometry`) driven by a single `LAYER_DEFS` config array, with attributes read generically from `ExtendedData/SchemaData/SimpleData` instead of hand-written per-layer descriptions. Each of the 27 layers (1 fault layer + 26 infrastructure layers) is fetched and parsed lazily, the first time the user toggles it on.

**Tech Stack:** Python 3 + geopandas (data pipeline, offline, run once), vanilla Leaflet 1.9.4 + React 18 UMD + Babel Standalone (visor, no build step), pytest (Python tests).

**Full design reference:** `docs/superpowers/specs/2026-07-08-fallas-activas-chile-design.md`

---

## Context already established (do not re-derive)

- Spec is written, reviewed, and committed at `fallas-activas-chile/docs/superpowers/specs/2026-07-08-fallas-activas-chile-design.md`. `fallas-activas-chile/` already has its own local git repo (`git init` was run in that folder; do not re-init).
- The national CHAF v1 KMZ (958 faults) downloads directly, no auth, from
  `https://download.pangaea.de/dataset/922241/files/CHAF_Pangaea_v1.kmz` — verified reachable (HTTP 200) during design.
- Source infrastructure data already exists as 26 KMZ files under
  `infraestructura-critica-chile/{agua,energia,relaves,salud,transporte}/*.kmz` (sibling directory to `fallas-activas-chile/`, i.e. `../infraestructura-critica-chile/` relative to it). Verified geometry types and feature counts for every one of the 26 shapefiles behind those KMZ (see table in Task 5).
- `infraestructura-critica-chile/transporte/red_vial.shp` has 12,609 features / ~7.0M vertices in EPSG:4326. Tested `simplify(0.0005, preserve_topology=True)` → 156,162 vertices (97.8% reduction) → resulting KML ≈ 19.9 MB (down from an unsimplified KML that would be far larger than the 72 MB *compressed* KMZ). This tolerance is the one to use.
- The complete `visor-web/index.html` (below, Task 6) was already drafted and **manually verified working** in a real browser preview during planning: sidebar renders, all 5 sector subsections + fault section expand/collapse correctly, badges compute correctly (958 for faults, `N/26` for infra), a "points" layer (synthetic bocatomas fixture), a "lines" layer (synthetic CHAF fixture), and a `MultiGeometry` "lines" layer (synthetic gasoductos fixture, 2-segment) all parsed and rendered with correct popups, and the fetch-failure path (missing file → inline error, checkbox unchecks itself) was verified too. One real bug was found and fixed during this prototyping: **a Web Worker created from a `Blob` has no page URL to resolve relative paths against** — posting a relative path like `"../data/x.kml"` to the worker throws `Failed to parse URL`. Fix already applied in the code below: `fetchKml` always resolves `new URL(..., document.baseURI).href` to an absolute URL *before* posting to the worker. Do not reintroduce a relative URL there.
- No JS unit-test framework is used for this visor (matches existing project convention for `alertas-redes`/`cuencas-chile` — verified manually via browser preview, not automated tests). Python tools DO get pytest tests (matches `catastro-fallas` convention).

---

## Task 1: Project skeleton

**Files:**
- Create: `fallas-activas-chile/.gitignore`
- Create: `fallas-activas-chile/tools/requirements.txt`
- Create (empty dirs via `.gitkeep` is not needed — they'll be populated in later tasks): `fallas-activas-chile/data/`, `fallas-activas-chile/tools/`, `fallas-activas-chile/tools/tests/`, `fallas-activas-chile/visor-web/`

- [ ] **Step 1: Create the directory structure**

Run:
```bash
cd fallas-activas-chile
mkdir -p data tools/tests visor-web
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Write `tools/requirements.txt`**

```
geopandas==1.1.4
pyogrio==0.13.0
shapely==2.1.2
pytest==9.1.1
```

- [ ] **Step 4: Verify the environment already satisfies these (they're already installed system-wide on this machine as of this plan)**

Run: `python3 -c "import geopandas, shapely, pytest; print('deps ok')"`
Expected: `deps ok`

If it fails in a different environment, run: `pip install -r tools/requirements.txt` first.

- [ ] **Step 5: Commit**

```bash
git add .gitignore tools/requirements.txt
git commit -m "chore: project skeleton (dirs, gitignore, requirements)"
```

---

## Task 2: Shared KMZ-reading utility (`tools/kmz_utils.py`)

**Files:**
- Create: `fallas-activas-chile/tools/kmz_utils.py`
- Test: `fallas-activas-chile/tools/tests/test_kmz_utils.py`

- [ ] **Step 1: Write the failing tests**

`tools/tests/test_kmz_utils.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_kmz_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kmz_utils'`

- [ ] **Step 3: Write `tools/kmz_utils.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_kmz_utils.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tools/kmz_utils.py tools/tests/test_kmz_utils.py
git commit -m "feat: add shared KMZ doc.kml reader utility"
```

---

## Task 3: Download national CHAF v1 catalog (`tools/descargar_chaf.py`)

**Files:**
- Create: `fallas-activas-chile/tools/descargar_chaf.py`
- Produces: `fallas-activas-chile/data/red_fallas.kml`

No unit test for the network-download function itself (matches existing convention in this codebase — `infraestructura-critica-chile/descargar_capa.py` has none either, since mocking a one-off data-fetch script's network call adds no real value). Instead this task's verification step *runs the real download* and checks the real output, which is a stronger check than a mock would be.

- [ ] **Step 1: Write `tools/descargar_chaf.py`**

```python
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
```

- [ ] **Step 2: Run it for real**

Run: `cd fallas-activas-chile && python tools/descargar_chaf.py`
Expected output includes: `958 fallas (Placemarks)` and `Escrito: .../data/red_fallas.kml` — no `ADVERTENCIA` line.

- [ ] **Step 3: Sanity-check the output file**

Run: `python -c "print(open('fallas-activas-chile/data/red_fallas.kml', encoding='utf-8').read().count('<Placemark'))"`
Expected: `958`

- [ ] **Step 4: Commit (script + generated data — data is static, committed per spec)**

```bash
git add tools/descargar_chaf.py data/red_fallas.kml
git commit -m "feat: download national CHAF v1 fault catalog (958 faults)"
```

---

## Task 4: Simplify and export `red_vial` (`tools/simplificar_red_vial.py`)

**Files:**
- Create: `fallas-activas-chile/tools/simplificar_red_vial.py`
- Test: `fallas-activas-chile/tools/tests/test_simplificar_red_vial.py`
- Produces: `fallas-activas-chile/data/transporte/red_vial.kml`

- [ ] **Step 1: Write the failing tests**

`tools/tests/test_simplificar_red_vial.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_simplificar_red_vial.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simplificar_red_vial'`

- [ ] **Step 3: Write `tools/simplificar_red_vial.py`**

```python
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
    print(f"Leyendo {ORIGEN_SHP} ...")
    gdf = gpd.read_file(ORIGEN_SHP)
    print(f"  {len(gdf)} features")
    simplificado = simplificar_gdf(gdf, TOLERANCIA)
    DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
    simplificado.to_file(DESTINO_KML, driver="KML")
    print(f"Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_simplificar_red_vial.py -v`
Expected: 2 passed

- [ ] **Step 5: Run it for real**

Run: `cd fallas-activas-chile && python tools/simplificar_red_vial.py`
Expected: prints `12609 features`, then `Escrito: .../data/transporte/red_vial.kml (NN,NNN,NNN bytes)` with a size in the 15–25 MB range (verified ≈19.9 MB during design with the same tolerance).

- [ ] **Step 6: Commit**

```bash
git add tools/simplificar_red_vial.py tools/tests/test_simplificar_red_vial.py data/transporte/red_vial.kml
git commit -m "feat: simplify and export red_vial (72MB KMZ -> ~20MB KML)"
```

---

## Task 5: Extract the remaining 25 infrastructure layers (`tools/extraer_kmls_infra.py`)

**Files:**
- Create: `fallas-activas-chile/tools/extraer_kmls_infra.py`
- Test: `fallas-activas-chile/tools/tests/test_extraer_kmls_infra.py`
- Produces: `fallas-activas-chile/data/{agua,energia,relaves,salud,transporte}/*.kml` (25 files; `red_vial.kml` already produced by Task 4)

Reference — full list of the 26 source shapefiles/KMZ under `infraestructura-critica-chile/`, their sector, geometry type, and feature count (verified during design; used again in Task 6's `LAYER_DEFS` and Task 7's verification):

| sector | file (stem) | geometry | features |
|---|---|---|---|
| agua | agua_potable_rural | Point | 1754 |
| agua | bocatomas | Point | 8707 |
| energia | almacenes_combustible | Point | 71 |
| energia | centrales_biomasa | Point | 32 |
| energia | centrales_eolicas | Point | 55 |
| energia | centrales_geotermicas | Point | 1 |
| energia | centrales_hidroelectricas | Point | 182 |
| energia | centrales_solares | Point | 457 |
| energia | gasoductos | LineString (13/58 multi) | 58 |
| energia | lineas_sea | LineString | 16 |
| energia | lineas_sem | LineString | 1 |
| energia | lineas_sic | LineString | 807 |
| energia | lineas_sing | LineString | 151 |
| energia | oleoductos | LineString | 29 |
| energia | subestaciones_sea | Point | 26 |
| energia | subestaciones_sem | Point | 5 |
| energia | subestaciones_sic | Point | 697 |
| energia | subestaciones_sing | Point | 167 |
| energia | terminales_maritimos_descarga | Point | 29 |
| energia | termoelectricas | Point | 157 |
| relaves | relaves_sernageomin_2018 | Point | 742 |
| salud | establecimientos_salud | Point | 4613 |
| transporte | infraestructura_portuaria | Point | 414 |
| transporte | red_aeroportuaria | Point | 338 |
| transporte | red_ferrea | LineString | 4049 |
| transporte | red_vial | LineString | 12609 (handled by Task 4) |

- [ ] **Step 1: Write the failing tests**

`tools/tests/test_extraer_kmls_infra.py`:
```python
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


def test_ruta_salida_preserva_sector_y_cambia_extension(tmp_path):
    raiz_infra = tmp_path / "infraestructura-critica-chile"
    destino_data = tmp_path / "fallas-activas-chile" / "data"
    kmz = raiz_infra / "agua" / "bocatomas.kmz"

    salida = ruta_salida(kmz, raiz_infra, destino_data)

    assert salida == destino_data / "agua" / "bocatomas.kml"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_extraer_kmls_infra.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extraer_kmls_infra'`

- [ ] **Step 3: Write `tools/extraer_kmls_infra.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_extraer_kmls_infra.py -v`
Expected: 3 passed

- [ ] **Step 5: Run it for real**

Run: `cd fallas-activas-chile && python tools/extraer_kmls_infra.py`
Expected: `25 archivos KMZ a extraer (excluidos: ['red_vial'])` followed by 25 `OK:` lines.

- [ ] **Step 6: Verify file count**

Run: `find fallas-activas-chile/data -name "*.kml" | wc -l`
Expected: `27` — 25 from this task + `red_fallas.kml` (Task 3) + `red_vial.kml` (Task 4).

- [ ] **Step 7: Commit**

```bash
git add tools/extraer_kmls_infra.py tools/tests/test_extraer_kmls_infra.py data/agua data/energia data/relaves data/salud data/transporte
git commit -m "feat: extract remaining 25 infrastructure KML layers"
```

---

## Task 6: The viewer (`visor-web/index.html`)

**Files:**
- Create: `fallas-activas-chile/visor-web/index.html`

This file was fully drafted and manually verified working during planning (see "Context already established" above) — write it exactly as below, don't redesign it.

- [ ] **Step 1: Write `visor-web/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>Fallas Activas + Infraestructura Crítica — Visor</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body, #root, #map { height: 100%; margin: 0; }
  * { box-sizing: border-box; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }

  #map { position: absolute; top: 0; right: 0; bottom: 0; left: 320px; background: #0b1622; }

  #panel {
    position: absolute; top: 0; left: 0; bottom: 0; z-index: 1000;
    width: 320px; overflow-y: auto;
    background: rgba(15,22,31,0.97); color: #e7edf3;
    padding: 14px 16px; box-shadow: 2px 0 16px rgba(0,0,0,0.45);
    font-size: 13px;
  }
  #panel h1 { font-size: 15px; margin: 0 0 8px; display: flex; align-items: center; gap: 6px; }
  .collapse { display: inline-block; margin-left: auto; background: transparent !important; width: auto !important; padding: 2px 8px !important; font-size: 14px; cursor: pointer; }

  @media (max-width: 760px) {
    #map { left: 0; }
    #panel {
      top: calc(8px + env(safe-area-inset-top)); left: 8px; right: 8px; bottom: auto;
      width: auto; max-width: none;
      max-height: calc(100vh - 16px - env(safe-area-inset-top));
      border-radius: 14px; backdrop-filter: blur(6px);
      padding: 12px 14px; font-size: 14px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.5);
    }
    #panel:not(.open) { right: auto; }
    #panel h1 { font-size: 13px; cursor: pointer; }
    .collapse { padding: 6px 12px !important; font-size: 16px; }
    .hint { color: #7fd4ff; font-size: 12px; margin-top: 6px; cursor: pointer; }
    label.tg { min-height: 40px; margin: 2px 0; }
    label.tg input[type="checkbox"] { width: 20px; height: 20px; flex: none; }
    .seg button { padding: 12px 10px; font-size: 14px; }
    button { padding: 12px 12px; font-size: 14px; }
    .leaflet-popup-content { width: min(86vw, 340px) !important; max-height: calc(100vh - 200px); }
  }
  #panel .sub { color: #93a4b5; font-size: 11px; margin-bottom: 10px; }
  .hint { color: #7fd4ff; font-size: 12px; margin-top: 6px; cursor: pointer; }
  .row { display: flex; align-items: center; justify-content: space-between; margin: 5px 0; }
  .stat { display: flex; align-items: center; gap: 7px; margin: 3px 0; }
  .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex: none; }
  .sq  { width: 12px; height: 12px; display: inline-block; flex: none; }
  .num { font-variant-numeric: tabular-nums; font-weight: 600; }
  .group { border-top: 1px solid #2a3a4a; margin-top: 8px; padding-top: 8px; }
  .subsection { margin-left: 8px; padding-left: 8px; border-left: 2px solid #2a3a4a; }
  .subsection .group { border-top: 1px dashed #2a3a4a; }
  .gtitle { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #8aa0b4; margin-bottom: 4px; }
  .sec-head {
    display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none;
    padding: 8px 10px; margin: 0 -2px 4px; border-radius: 8px;
    background: rgba(255,255,255,0.04); border-left: 3px solid #2563eb;
  }
  .sec-head:active { background: rgba(255,255,255,0.09); }
  .sec-head .sec-title { font-size: 13px; font-weight: 700; color: #eef3f8; letter-spacing: .2px; }
  .sec-badge {
    margin-left: auto; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px;
    background: #1f2b3a; color: #9db1c4;
  }
  .sec-chev { color: #6d8299; font-size: 13px; }
  label.tg { display: flex; align-items: center; gap: 7px; cursor: pointer; margin: 4px 0; user-select: none; }
  label.tg .warn { color: #ffb020; }
  button { background: #2563eb; color: #fff; border: 0; border-radius: 7px; padding: 7px 10px; cursor: pointer; font-size: 12px; width: 100%; margin-top: 8px; }
  button:disabled { opacity: .6; cursor: default; }
  .seg { display: flex; gap: 4px; margin-top: 4px; }
  .seg button { width: auto; flex: 1; margin: 0; background: #1f2b3a; }
  .seg button.on { background: #2563eb; }
  #err { color: #ff8d7a; font-size: 11px; margin-top: 6px; }
  .layer-err { color: #ff8d7a; font-size: 11px; margin: 2px 0 4px; }
  .leaflet-popup-content { font-size: 12px; max-height: calc(100vh - 210px); overflow-y: auto; overflow-x: hidden; }
  .leaflet-popup-content table { border-collapse: collapse; }
  .leaflet-popup-content td { border-bottom: 1px solid #eee; padding: 2px 6px 2px 0; vertical-align: top; }
  .leaflet-pane.leaflet-popup-pane { z-index: 1200; }
  .leaflet-tile-pane, .leaflet-tile-pane *,
  .leaflet-overlay-pane, .leaflet-overlay-pane *,
  .leaflet-marker-pane, .leaflet-marker-pane *,
  .leaflet-container > canvas { touch-action: none !important; }
</style>
</head>
<body>
<div id="root"></div>
<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

<!-- type="text/plain": evita que Babel Standalone AUTO-ejecute este script (bug conocido,
     ver alertas-redes/CLAUDE.md "Bug histórico: doble montaje de React"). Solo lo corre
     el bootstrap manual de abajo, UNA vez. -->
<script type="text/plain" id="app-src">
const { useState, useEffect, useRef, useCallback } = React;

// En localhost, los datos se sirven desde el propio repo (servidor estático apuntando
// a la raíz de fallas-activas-chile/, no solo visor-web/), para poder probar contra
// archivos locales sin depender de GitHub. Fuera de localhost, se usa la rama main
// publicada. Evita el gotcha de "revertir la URL local antes de publicar" que tuvo
// alertas-redes con las cuencas: acá es automático por hostname, no manual.
const DATA_BASE = (typeof location !== "undefined" &&
    (location.hostname === "localhost" || location.hostname === "127.0.0.1"))
  ? "../data"
  : "https://raw.githubusercontent.com/cvenegas-sernageomin/fallas-activas-chile/main/data";

const ESRI_SAT_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

const POPUP_OPTS = { maxWidth: 400, autoPanPaddingTopLeft: [16, 124], autoPanPaddingBottomRight: [16, 20] };

// Referencia a nivel de módulo: sobrevive al doble montaje de React 18 (modo estricto)
// para poder destruir el mapa anterior por completo antes de crear uno nuevo (mismo
// patrón que alertas-redes/visor-web/index.html, ver comentario ahí).
let _mapaActivo = null;

// ---------- colores ----------
const COLOR_ACTIVIDAD = { Proved: "#ff2d2d", Probable: "#ff8c00", Possible: "#e6c400" };
const COLOR_ACTIVIDAD_DEFAULT = "#9db1c4";

const SECTORES = [
  { id: "agua", label: "Agua", icon: "💧", color: "#38bdf8" },
  { id: "energia", label: "Energía", icon: "⚡", color: "#f59e0b" },
  { id: "relaves", label: "Relaves", icon: "⛏️", color: "#92400e" },
  { id: "salud", label: "Salud", icon: "🏥", color: "#f43f5e" },
  { id: "transporte", label: "Transporte", icon: "🚦", color: "#a855f7" }
];
const COLOR_SECTOR = {};
SECTORES.forEach(s => { COLOR_SECTOR[s.id] = s.color; });

// ---------- configuración de capas ----------
// sector "fallas" es especial: se muestra en su propia sección de nivel superior,
// no anidada bajo "Infraestructura Crítica". kind: "points" | "lines".
const LAYER_DEFS = [
  { id: "fallas", sector: "fallas", label: "Fallas Activas (CHAF v1)", file: "red_fallas.kml", kind: "lines" },

  { id: "agua_potable_rural", sector: "agua", label: "Agua Potable Rural", file: "agua/agua_potable_rural.kml", kind: "points" },
  { id: "bocatomas", sector: "agua", label: "Bocatomas", file: "agua/bocatomas.kml", kind: "points" },

  { id: "almacenes_combustible", sector: "energia", label: "Almacenes de Combustible", file: "energia/almacenes_combustible.kml", kind: "points" },
  { id: "centrales_biomasa", sector: "energia", label: "Centrales de Biomasa", file: "energia/centrales_biomasa.kml", kind: "points" },
  { id: "centrales_eolicas", sector: "energia", label: "Centrales Eólicas", file: "energia/centrales_eolicas.kml", kind: "points" },
  { id: "centrales_geotermicas", sector: "energia", label: "Centrales Geotérmicas", file: "energia/centrales_geotermicas.kml", kind: "points" },
  { id: "centrales_hidroelectricas", sector: "energia", label: "Centrales Hidroeléctricas", file: "energia/centrales_hidroelectricas.kml", kind: "points" },
  { id: "centrales_solares", sector: "energia", label: "Centrales Solares", file: "energia/centrales_solares.kml", kind: "points" },
  { id: "gasoductos", sector: "energia", label: "Gasoductos", file: "energia/gasoductos.kml", kind: "lines" },
  { id: "lineas_sea", sector: "energia", label: "Líneas Eléctricas SEA", file: "energia/lineas_sea.kml", kind: "lines" },
  { id: "lineas_sem", sector: "energia", label: "Líneas Eléctricas SEM", file: "energia/lineas_sem.kml", kind: "lines" },
  { id: "lineas_sic", sector: "energia", label: "Líneas Eléctricas SIC", file: "energia/lineas_sic.kml", kind: "lines" },
  { id: "lineas_sing", sector: "energia", label: "Líneas Eléctricas SING", file: "energia/lineas_sing.kml", kind: "lines" },
  { id: "oleoductos", sector: "energia", label: "Oleoductos", file: "energia/oleoductos.kml", kind: "lines" },
  { id: "subestaciones_sea", sector: "energia", label: "Subestaciones SEA", file: "energia/subestaciones_sea.kml", kind: "points" },
  { id: "subestaciones_sem", sector: "energia", label: "Subestaciones SEM", file: "energia/subestaciones_sem.kml", kind: "points" },
  { id: "subestaciones_sic", sector: "energia", label: "Subestaciones SIC", file: "energia/subestaciones_sic.kml", kind: "points" },
  { id: "subestaciones_sing", sector: "energia", label: "Subestaciones SING", file: "energia/subestaciones_sing.kml", kind: "points" },
  { id: "terminales_maritimos_descarga", sector: "energia", label: "Terminales Marítimos de Descarga", file: "energia/terminales_maritimos_descarga.kml", kind: "points" },
  { id: "termoelectricas", sector: "energia", label: "Termoeléctricas", file: "energia/termoelectricas.kml", kind: "points" },

  { id: "relaves_sernageomin_2018", sector: "relaves", label: "Relaves (SERNAGEOMIN 2018)", file: "relaves/relaves_sernageomin_2018.kml", kind: "points" },

  { id: "establecimientos_salud", sector: "salud", label: "Establecimientos de Salud", file: "salud/establecimientos_salud.kml", kind: "points" },

  { id: "infraestructura_portuaria", sector: "transporte", label: "Infraestructura Portuaria", file: "transporte/infraestructura_portuaria.kml", kind: "points" },
  { id: "red_aeroportuaria", sector: "transporte", label: "Red Aeroportuaria", file: "transporte/red_aeroportuaria.kml", kind: "points" },
  { id: "red_ferrea", sector: "transporte", label: "Red Férrea", file: "transporte/red_ferrea.kml", kind: "lines" },
  { id: "red_vial", sector: "transporte", label: "Red Vial", file: "transporte/red_vial.kml", kind: "lines", warn: true }
];
const FALLAS_DEF = LAYER_DEFS.find(d => d.id === "fallas");
const INFRA_DEFS = LAYER_DEFS.filter(d => d.sector !== "fallas");

function colorDeCapa(def, attrs) {
  if (def.id === "fallas") return COLOR_ACTIVIDAD[attrs.activity] || COLOR_ACTIVIDAD_DEFAULT;
  return COLOR_SECTOR[def.sector] || "#3388ff";
}

function tituloPopup(def, name, attrs) {
  if (def.id === "fallas") {
    const fname = attrs.F_name, ftname = attrs.FT_name;
    if (fname && ftname) return fname + " — " + ftname;
    if (fname) return fname;
    return attrs.activity || name || "(sin nombre)";
  }
  return name || "(sin nombre)";
}

// ---------- utilidades de texto/HTML ----------
function escHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function esValorVacio(v) {
  if (v == null) return true;
  const s = String(v).trim();
  return s === "" || s === "-99" || s === "-99.0";
}
function tablaAtributos(attrs) {
  const filas = Object.keys(attrs)
    .filter(k => !esValorVacio(attrs[k]))
    .map(k => `<tr><td><b>${escHtml(k)}</b></td><td>${escHtml(attrs[k])}</td></tr>`)
    .join("");
  return filas ? `<table cellpadding="2">${filas}</table>` : "";
}

// ---------- parseo genérico de KML (puntos y líneas, con ExtendedData/SimpleData) ----------
function dec(s) {
  return s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'");
}
function parseAttrs(block) {
  const attrs = {};
  const re = /<SimpleData name="([^"]+)">([\s\S]*?)<\/SimpleData>/g;
  let m;
  while ((m = re.exec(block))) attrs[m[1]] = dec(m[2]).trim();
  return attrs;
}
// kind: "lines" lee todos los <LineString> del placemark (soporta MultiGeometry, ej.
// gasoductos: 13 de 58 features son multi-tramo); default = "points" lee un <Point>.
function parsePlacemarks(text, kind) {
  const out = [];
  const pmRe = /<Placemark[^>]*>([\s\S]*?)<\/Placemark>/g;
  let pm;
  while ((pm = pmRe.exec(text))) {
    const block = pm[1];
    const nM = block.match(/<name>([\s\S]*?)<\/name>/);
    const name = nM ? dec(nM[1]).trim() : "";
    const attrs = parseAttrs(block);
    if (kind === "lines") {
      const lines = [];
      const lsRe = /<LineString>[\s\S]*?<coordinates>([\s\S]*?)<\/coordinates>[\s\S]*?<\/LineString>/g;
      let lm;
      while ((lm = lsRe.exec(block))) {
        const coords = lm[1].trim().split(/\s+/).filter(x => x !== "").map(pair => {
          const p = pair.split(","); return [parseFloat(p[1]), parseFloat(p[0])];
        });
        if (coords.length) lines.push(coords);
      }
      if (!lines.length) continue;
      out.push({ name, attrs, lines });
    } else {
      const ptM = block.match(/<Point>[\s\S]*?<coordinates>([\s\S]*?)<\/coordinates>/);
      if (!ptM) continue;
      const p = ptM[1].trim().split(",");
      const lat = parseFloat(p[1]), lon = parseFloat(p[0]);
      if (isNaN(lat) || isNaN(lon)) continue;
      out.push({ name, attrs, lat, lon });
    }
  }
  return out;
}

// ---------- Web Worker (fuera del hilo principal, igual patrón que alertas-redes) ----------
// Duplicado a mano (el Worker corre desde un Blob, scope aislado sin acceso a las
// funciones de arriba) — verificar que un cambio en parsePlacemarks se refleje acá también.
const KML_WORKER_SRC = `
function dec(s){return s.replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&apos;/g,"'");}
function parseAttrs(block){
  var attrs={}; var re=/<SimpleData name="([^"]+)">([\\s\\S]*?)<\\/SimpleData>/g, m;
  while((m=re.exec(block))) attrs[m[1]]=dec(m[2]).trim();
  return attrs;
}
function parsePlacemarks(text, kind){
  var out=[];
  var pmRe=/<Placemark[^>]*>([\\s\\S]*?)<\\/Placemark>/g, pm;
  while((pm=pmRe.exec(text))){
    var block=pm[1];
    var nM=block.match(/<name>([\\s\\S]*?)<\\/name>/);
    var name=nM?dec(nM[1]).trim():"";
    var attrs=parseAttrs(block);
    if(kind==="lines"){
      var lines=[];
      var lsRe=/<LineString>[\\s\\S]*?<coordinates>([\\s\\S]*?)<\\/coordinates>[\\s\\S]*?<\\/LineString>/g, lm;
      while((lm=lsRe.exec(block))){
        var coords=lm[1].trim().split(/\\s+/).filter(function(x){return x!=="";}).map(function(pair){
          var p=pair.split(","); return [parseFloat(p[1]),parseFloat(p[0])];
        });
        if(coords.length) lines.push(coords);
      }
      if(!lines.length) continue;
      out.push({name:name, attrs:attrs, lines:lines});
    } else {
      var ptM=block.match(/<Point>[\\s\\S]*?<coordinates>([\\s\\S]*?)<\\/coordinates>/);
      if(!ptM) continue;
      var p=ptM[1].trim().split(",");
      var lat=parseFloat(p[1]), lon=parseFloat(p[0]);
      if(isNaN(lat)||isNaN(lon)) continue;
      out.push({name:name, attrs:attrs, lat:lat, lon:lon});
    }
  }
  return out;
}
self.onmessage=function(e){
  var d=e.data;
  fetch(d.url, {cache:"no-cache"}).then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status+": "+d.url); return r.text(); })
    .then(function(t){ var out=parsePlacemarks(t, d.kind); self.postMessage({id:d.id, ok:true, out:out}); })
    .catch(function(err){ self.postMessage({id:d.id, ok:false, error:String((err&&err.message)||err)}); });
};
`;

let _kmlWorker = null, _kmlSeq = 0;
const _kmlPending = new Map();
function getKmlWorker() {
  if (_kmlWorker === false) return null;
  if (_kmlWorker) return _kmlWorker;
  try {
    const blob = new Blob([KML_WORKER_SRC], { type: "application/javascript" });
    _kmlWorker = new Worker(URL.createObjectURL(blob));
    _kmlWorker.onmessage = (e) => {
      const { id, ok, out, error } = e.data;
      const p = _kmlPending.get(id); if (!p) return;
      _kmlPending.delete(id);
      ok ? p.resolve(out) : p.reject(new Error(error));
    };
    _kmlWorker.onerror = () => {
      _kmlWorker = false;
      _kmlPending.forEach(p => p.reject(new Error("KML worker no disponible")));
      _kmlPending.clear();
    };
    return _kmlWorker;
  } catch (e) { _kmlWorker = false; return null; }
}

async function fetchGenericoAbs(url, kind) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${url}`);
  const text = await r.text();
  return parsePlacemarks(text, kind);
}

// Resuelve SIEMPRE a una URL absoluta antes de mandarla al worker: un Worker creado
// desde un Blob no tiene la página como base para resolver rutas relativas (".."),
// las resuelve contra el propio blob: y el fetch falla con "Failed to parse URL".
function fetchKml(file, kind) {
  const url = new URL(`${DATA_BASE}/${file}`, document.baseURI).href;
  const w = getKmlWorker();
  if (!w) return fetchGenericoAbs(url, kind);
  return new Promise((resolve, reject) => {
    const id = ++_kmlSeq;
    _kmlPending.set(id, { resolve, reject });
    w.postMessage({ id, url, kind });
  });
}

// Sanitiza el HTML del popup antes de inyectarlo (mismo patrón que alertas-redes):
// quita <script>/<iframe>/<object>/<embed>, atributos on* y URLs javascript:.
function sanitizePopup(html) {
  if (!html) return "";
  const t = document.createElement("template");
  t.innerHTML = html;
  t.content.querySelectorAll("script, iframe, object, embed, link, meta, style, base").forEach(n => n.remove());
  t.content.querySelectorAll("*").forEach(el => {
    for (const a of [...el.attributes]) {
      const v = (a.value || "").replace(/\s+/g, "").toLowerCase();
      if (/^on/i.test(a.name) || v.startsWith("javascript:") || v.startsWith("data:text/html")) {
        el.removeAttribute(a.name);
      }
    }
  });
  return t.innerHTML;
}

function buildLayerGroup(def, feats) {
  const g = L.layerGroup();
  feats.forEach(f => {
    const color = colorDeCapa(def, f.attrs);
    const titulo = tituloPopup(def, f.name, f.attrs);
    const popupHtml = `<b>${escHtml(titulo)}</b>${tablaAtributos(f.attrs)}`;
    let layer;
    if (def.kind === "lines") {
      layer = L.polyline(f.lines, { color, weight: def.id === "fallas" ? 3 : 2, opacity: 0.85 });
    } else {
      layer = L.circleMarker([f.lat, f.lon], {
        radius: 5, color: "#0a0a0a", weight: 0.6, fillColor: color, fillOpacity: 0.85
      });
    }
    layer.bindPopup(sanitizePopup(popupHtml), POPUP_OPTS);
    g.addLayer(layer);
  });
  return g;
}

// ---------- componentes de UI ----------
function St({ color, square, label, value }) {
  return (
    <div className="stat">
      <span className={square ? "sq" : "dot"} style={{ background: color }}></span>
      <span>{label}</span>
      {value !== "" && <span className="num" style={{ marginLeft: "auto" }}>{value}</span>}
    </div>
  );
}

function Section({ title, open, onToggle, badge, children }) {
  return (
    <div className="group">
      <div className="sec-head" onClick={onToggle}>
        <span className="sec-title">{title}</span>
        {badge != null && badge !== "" && <span className="sec-badge">{badge}</span>}
        <span className="sec-chev">{open ? "▾" : "▸"}</span>
      </div>
      {open && children}
    </div>
  );
}

function LayerRow({ def, state, onToggle }) {
  const st = state || {};
  return (
    <div>
      <label className="tg">
        <input type="checkbox" checked={!!st.on} onChange={e => onToggle(def, e.target.checked)} />
        <span>{def.label}{def.warn ? <span className="warn"> (capa pesada)</span> : ""}</span>
        <span className="num" style={{ marginLeft: "auto" }}>
          {st.loading ? "…" : (st.total != null ? st.total : "")}
        </span>
      </label>
      {st.error && <div className="layer-err">⚠ {st.error}</div>}
    </div>
  );
}

// ---------- App ----------
function App() {
  const mapRef = useRef(null);
  const basemaps = useRef({});
  const groups = useRef({});   // id -> L.layerGroup, poblado la primera vez que se activa

  const [layerState, setLayerState] = useState({});
  const [fallasOpen, setFallasOpen] = useState(false);
  const [infraOpen, setInfraOpen] = useState(false);
  const [sectorOpen, setSectorOpen] = useState({});
  const [base, setBase] = useState("sat");
  const [collapsed, setCollapsed] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 760px)").matches);

  useEffect(() => {
    if (_mapaActivo) {
      try { _mapaActivo.remove(); } catch (e) {}
      _mapaActivo = null;
    }
    const cont = L.DomUtil.get("map");
    if (cont != null && cont._leaflet_id != null) {
      cont._leaflet_id = null;
      cont.innerHTML = "";
    }
    const map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([-35.5, -71], 5);
    mapRef.current = map;
    _mapaActivo = map;

    const sat = L.tileLayer(ESRI_SAT_URL, { maxZoom: 18, attribution: "Imagery © Esri" });
    const labels = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 18 }
    );
    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 18, attribution: "© OpenStreetMap" });
    basemaps.current = { sat, labels, osm };
    sat.addTo(map); labels.addTo(map);

    return () => {
      try { map.remove(); } catch (e) {}
      if (_mapaActivo === map) _mapaActivo = null;
      mapRef.current = null;
      groups.current = {};
    };
  }, []);

  useEffect(() => {
    const b = basemaps.current, map = mapRef.current;
    if (!map || !b.sat) return;
    if (base === "sat") {
      map.removeLayer(b.osm); b.sat.addTo(map); b.labels.addTo(map);
    } else {
      map.removeLayer(b.sat); map.removeLayer(b.labels); b.osm.addTo(map);
    }
  }, [base]);

  const toggleLayer = useCallback(async (def, on) => {
    setLayerState(prev => ({ ...prev, [def.id]: { ...(prev[def.id] || {}), on } }));
    const map = mapRef.current;
    if (!map) return;
    let group = groups.current[def.id];
    if (on) {
      if (!group) {
        setLayerState(prev => ({ ...prev, [def.id]: { ...(prev[def.id] || {}), on: true, loading: true, error: "" } }));
        try {
          const feats = await fetchKml(def.file, def.kind);
          group = buildLayerGroup(def, feats);
          groups.current[def.id] = group;
          setLayerState(prev => ({ ...prev, [def.id]: { on: true, loading: false, error: "", total: feats.length } }));
        } catch (e) {
          // on:false -> el checkbox se desmarca solo (nada quedo mostrado en el mapa)
          // y no infla el contador "X/N" de capas activas; el mensaje de error queda
          // igual visible debajo para que el usuario sepa por que y pueda reintentar.
          setLayerState(prev => ({ ...prev, [def.id]: { on: false, loading: false, error: String(e.message || e) } }));
          return;
        }
      }
      group.addTo(map);
    } else if (group) {
      map.removeLayer(group);
    }
  }, []);

  return (
    <div id="panel" className={collapsed ? "" : "open"}>
      <h1 onClick={() => setCollapsed(!collapsed)}>🪨 Fallas + Infraestructura
        <button className="collapse" onClick={(e) => { e.stopPropagation(); setCollapsed(!collapsed); }}>{collapsed ? "▸" : "▾"}</button>
      </h1>
      <div className="sub">Capas estáticas — CHAF v1 (2020) + SERNAGEOMIN/sectorial</div>
      {collapsed && <div className="hint" onClick={() => setCollapsed(false)}>👆 Toca para ver capas y leyenda</div>}

      {!collapsed && <div className="pbody">
      <Section title="🪨 Fallas Activas (CHAF v1)" open={fallasOpen} onToggle={() => setFallasOpen(!fallasOpen)}
        badge={layerState.fallas && layerState.fallas.total != null ? layerState.fallas.total : "958"}>
        <LayerRow def={FALLAS_DEF} state={layerState.fallas} onToggle={toggleLayer} />
        <div style={{ marginTop: 6 }}>
          <St color={COLOR_ACTIVIDAD.Proved} label="Proved (confirmada)" value="" />
          <St color={COLOR_ACTIVIDAD.Probable} label="Probable" value="" />
          <St color={COLOR_ACTIVIDAD.Possible} label="Possible" value="" />
        </div>
        <div style={{ color: "#93a4b5", fontSize: 11, marginTop: 6 }}>
          Melnick, Maldonado &amp; Contreras (2020), PANGAEA doi:10.1594/PANGAEA.922241, CC-BY 4.0.
        </div>
      </Section>

      <Section title="🏗️ Infraestructura Crítica" open={infraOpen} onToggle={() => setInfraOpen(!infraOpen)}
        badge={INFRA_DEFS.filter(d => layerState[d.id] && layerState[d.id].on).length + "/" + INFRA_DEFS.length}>
        {SECTORES.map(sec => {
          const defsSector = LAYER_DEFS.filter(d => d.sector === sec.id);
          return (
            <div className="subsection" key={sec.id}>
              <Section title={sec.icon + " " + sec.label}
                open={!!sectorOpen[sec.id]}
                onToggle={() => setSectorOpen({ ...sectorOpen, [sec.id]: !sectorOpen[sec.id] })}
                badge={defsSector.filter(d => layerState[d.id] && layerState[d.id].on).length + "/" + defsSector.length}>
                {defsSector.map(def => (
                  <LayerRow key={def.id} def={def} state={layerState[def.id]} onToggle={toggleLayer} />
                ))}
              </Section>
            </div>
          );
        })}
      </Section>

      <div className="group">
        <div className="gtitle">Fondo</div>
        <div className="seg">
          <button className={base === "sat" ? "on" : ""} onClick={() => setBase("sat")}>Satélite</button>
          <button className={base === "calle" ? "on" : ""} onClick={() => setBase("calle")}>Calles</button>
        </div>
      </div>
      </div>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
</script>

<script>
  (function () {
    try {
      var src = document.getElementById("app-src").textContent;
      var code = Babel.transform(src, { presets: [["react", { runtime: "classic" }]] }).code;
      (0, eval)(code);
    } catch (err) {
      console.error("Bootstrap error:", err && err.message);
      document.getElementById("root").innerHTML =
        '<div style="color:#fff;padding:20px;font-family:sans-serif">Error al iniciar: ' +
        (err && err.message) + "</div>";
    }
  })();
</script>
</body>
</html>
```

- [ ] **Step 2: Add a temporary local-preview server config**

Add this entry to `.claude/launch.json` (repo root `Documents/Claude/.claude/launch.json`) in the `configurations` array, so `preview_start` can serve the whole project (needed because `DATA_BASE` on localhost resolves `../data` relative to `visor-web/index.html`, i.e. it needs the *project root*, not just `visor-web/`, as the served directory):

```json
{ "name": "fallas-activas-preview", "runtimeExecutable": "python", "runtimeArgs": ["-m", "http.server", "8781", "--directory", "fallas-activas-chile"], "port": 8781 }
```

- [ ] **Step 3: Load the page and check for console errors (no real data needed for this check)**

Use `preview_start` with name `fallas-activas-preview`, then navigate to `/visor-web/index.html`, then check `preview_console_logs` (level `all`). Expected: no errors. Expected visible content (via `preview_eval` reading `document.getElementById('root').innerText`, since the accessibility snapshot tool has a known staleness bug documented in memory `feedback-preview-mcp-roto` — trust `preview_eval`, not `preview_snapshot`, for this): panel shows "🪨 Fallas Activas (CHAF v1)" with badge `958` and "🏗️ Infraestructura Crítica" with badge `0/26`.

- [ ] **Step 4: Commit**

```bash
git add visor-web/index.html
git commit -m "feat: add static viewer (faults + infrastructure, lazy-loaded layers)"
```

Note: don't commit the `.claude/launch.json` change from Step 2 as part of this repo's commit (it's a file in the *parent* `Documents/Claude` project, not in `fallas-activas-chile` — it's a personal dev-convenience entry, same pattern as the pre-existing `visor-full` entry for `alertas-redes`). Leave it in place for Task 7's use; no need to remove it afterwards (matches the precedent of the permanent `visor-full` entry kept for `alertas-redes`).

---

## Task 7: Full manual verification against real data

**No new files.** This task exercises Tasks 3–6 together with the *real* generated data (not synthetic fixtures) and is the actual acceptance check for this project (matches the "no automated UI tests, manual browser verification" convention already used for `cuencas-chile`/`glaciares` in `alertas-redes`).

- [ ] **Step 1: Start the preview server and open the viewer**

Use `preview_start` with name `fallas-activas-preview` (added in Task 6), navigate to `/visor-web/index.html`.

- [ ] **Step 2: Verify the fault layer against real data**

Via `preview_eval`: click the "🪨 Fallas Activas (CHAF v1)" section header to expand it, then click its checkbox, wait ~1s, then read `document.getElementById('root').innerText`.
Expected: badge changes to `958` (same number, now backed by real data instead of the hardcoded fallback), no `⚠` error line, and the "Proved (confirmada)" / "Probable" / "Possible" legend rows are still visible.

- [ ] **Step 3: Verify a representative infrastructure layer of each geometry kind**

Expand "🏗️ Infraestructura Crítica" → "💧 Agua", toggle "Bocatomas" on. Expected count: `8707` (matches the real shapefile feature count from Task 5's table).
Expand "⚡ Energía", toggle "Gasoductos" on. Expected count: `58` (includes the 13 multi-segment features, each counted once — confirms `MultiGeometry` parsing works against the real file, not just the synthetic fixture).
Expand "🚦 Transporte", toggle "Red Vial" on (labelled "(capa pesada)"). Expected count: `12609`, may take a few seconds to load (≈20 MB fetch + parse) — this is expected and acceptable per the spec's explicit decision to warn rather than exclude.

- [ ] **Step 4: Check for console errors after all the above toggles**

`preview_console_logs` with level `all`. Expected: no errors.

- [ ] **Step 5: Check a popup renders real attributes**

`preferCanvas: true` means markers/lines are drawn on a `<canvas>`, not as individually
clickable DOM nodes, so `preview_click` with a CSS selector won't hit them. Use
`preview_eval` to open a popup directly by walking Leaflet's internal layer group instead
of clicking blind:

```js
(() => {
  const btn = document.querySelector('.leaflet-popup-pane'); // sanity: pane exists
  const map = window.__debugMap; // see note below
  return !!btn;
})()
```

Since `map` and `groups` are React refs (not on `window`), the simplest reliable check is:
temporarily add `window.__debugGroups = groups.current;` right after the line
`groups.current[def.id] = group;` inside `toggleLayer` (Task 6's code), reload, toggle
"Bocatomas" on, then run:

```js
(() => {
  const g = window.__debugGroups.bocatomas;
  let layer = null;
  g.eachLayer(l => { if (!layer) layer = l; });
  layer.openPopup();
  return document.querySelector('.leaflet-popup-content').innerText;
})()
```

Expected: a popup HTML dump starting with the placemark's title, followed by a table of
its non-empty attributes (e.g. `NOMCAN`, `REGION` for bocatomas) — confirms
`tablaAtributos`/`tituloPopup` work against the real file, not just Task 6's synthetic
fixtures. **Remove the temporary `window.__debugGroups` line before publishing (Task 9)**
(it's a debug aid, not part of the shipped file).

- [ ] **Step 6: No commit needed for this task** (verification only, no file changes)

---

## Task 8: Replace outdated relaves layer with the Oct-2025 SERNAGEOMIN catastro

**Context:** the `relaves_sernageomin_2018.kml` layer (742 features, sourced from `infraestructura-critica-chile/relaves/`) is outdated. The user provided a newer, official, more complete catastro directly: `Fallas Activas/Info/CATASTRO_RELAVES_CHILE_OCT2025.xlsx` (a sibling directory to this repo, same as `infraestructura-critica-chile/`), sheet `CDR_CHILE`, 836 records with real `LATITUD`/`LONGITUD` in WGS84 decimal degrees (columns verified during planning: no missing coordinates, lat range -46.86 to -20.61, lon range -72.67 to -68.44 — plausible for Chile). Data starts at row index 6 (0-indexed header row; rows 0-5 are title/metadata). `ESTADO_INSTALACION` breakdown: ABANDONADO=455, INACTIVO=223, ACTIVO=129, EN CONSTRUCCION=19, ELIMINADO=8, EN REVISION=2 (sums to 836).

**Files:**
- Create: `fallas-activas-chile/tools/convertir_catastro_relaves.py`
- Test: `fallas-activas-chile/tools/tests/test_convertir_catastro_relaves.py`
- Modify: `fallas-activas-chile/tools/extraer_kmls_infra.py` (add `"relaves_sernageomin_2018"` to `EXCLUIR`, so future re-runs against the sibling `infraestructura-critica-chile/` don't resurrect the superseded file)
- Modify: `fallas-activas-chile/tools/tests/test_extraer_kmls_infra.py` (extend the exclusion test to cover both excluded names)
- Modify: `fallas-activas-chile/visor-web/index.html` (swap the `relaves_sernageomin_2018` entry in `LAYER_DEFS` for `relaves_sernageomin_2025`)
- Produces: `fallas-activas-chile/data/relaves/relaves_sernageomin_2025.kml`
- Delete: `fallas-activas-chile/data/relaves/relaves_sernageomin_2018.kml` (superseded)

- [ ] **Step 1: Write the failing tests**

`tools/tests/test_convertir_catastro_relaves.py`:
```python
import pandas as pd

from convertir_catastro_relaves import construir_geodataframe


def _df_prueba():
    return pd.DataFrame({
        "NOMBRE_FAENA": ["FAENA A", "FAENA B", "FAENA C"],
        "NOMBRE_INSTALACION": ["DEPOSITO 1", "DEPOSITO 2", "SIN COORDENADAS"],
        "LATITUD": [-33.5, -20.9, None],
        "LONGITUD": [-70.6, -68.6, None],
        "ESTADO_INSTALACION": ["ACTIVO", "ABANDONADO", "ACTIVO"],
        "FECHA_RES_APRUEBA": pd.to_datetime(["2022-12-05", None, "2019-01-01"]),
        "RES_PDC_APRUEBA": [None, 123, None],
    })


def test_construir_geodataframe_arma_geometria_desde_lat_lon():
    gdf = construir_geodataframe(_df_prueba())
    assert len(gdf) == 2  # la fila sin coordenadas se descarta
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.iloc[0].x == -70.6
    assert gdf.geometry.iloc[0].y == -33.5


def test_construir_geodataframe_arma_nombre_legible():
    gdf = construir_geodataframe(_df_prueba())
    assert gdf["Name"].iloc[0] == "FAENA A - DEPOSITO 1"
    assert gdf["Name"].iloc[1] == "FAENA B - DEPOSITO 2"


def test_construir_geodataframe_convierte_fechas_y_vacios_a_texto():
    gdf = construir_geodataframe(_df_prueba())
    # fila 0 (FAENA A): tiene fecha real -> queda como texto ISO, no Timestamp
    assert gdf["FECHA_RES_APRUEBA"].iloc[0] == "2022-12-05"
    # fila 1 (FAENA B): NaT/None -> cadena vacia (no "NaT"/"None"), para que el
    # filtro esValorVacio() del visor la descarte igual que un campo -99
    assert gdf["FECHA_RES_APRUEBA"].iloc[1] == ""
    assert gdf["RES_PDC_APRUEBA"].iloc[0] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_convertir_catastro_relaves.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'convertir_catastro_relaves'`

- [ ] **Step 3: Write `tools/convertir_catastro_relaves.py`**

```python
"""Convierte el catastro SERNAGEOMIN de depositos de relaves (Oct-2025, Excel) a KML.

Reemplaza relaves_sernageomin_2018.kml (742 registros, sourced from
infraestructura-critica-chile/) por un catastro mas reciente y completo (836 registros,
Octubre 2025) que el usuario aporto directamente como planilla Excel. Fuente:
SERNAGEOMIN, "Catastro de Depositos de Relaves" (DS 248/2007).
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

ORIGEN_XLSX = (
    Path(__file__).resolve().parent.parent.parent
    / "Fallas Activas" / "Info" / "CATASTRO_RELAVES_CHILE_OCT2025.xlsx"
)
DESTINO_KML = Path(__file__).resolve().parent.parent / "data" / "relaves" / "relaves_sernageomin_2025.kml"
HOJA = "CDR_CHILE"
FILA_ENCABEZADO = 6  # 0-indexed: las primeras 6 filas del Excel son titulo/metadata


def leer_catastro(ruta_xlsx: Path, hoja: str = HOJA, fila_encabezado: int = FILA_ENCABEZADO) -> pd.DataFrame:
    """Lee la hoja de datos del catastro, saltando las filas de titulo/metadata iniciales."""
    return pd.read_excel(ruta_xlsx, sheet_name=hoja, header=fila_encabezado)


def construir_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Arma un GeoDataFrame EPSG:4326 desde las columnas LATITUD/LONGITUD.

    - Descarta filas sin coordenadas.
    - Arma 'Name' = NOMBRE_FAENA + " - " + NOMBRE_INSTALACION (mismo patron que
      shp_a_kmz.py: un campo 'Name' legible es lo que el driver KML de geopandas
      usa como <name> del Placemark).
    - Convierte columnas de fecha a texto ISO (el driver KML no serializa
      datetime64 de forma confiable) y reemplaza NaN/None por cadena vacia en
      TODOS los atributos, para que el filtro esValorVacio() del visor los
      descarte igual que un campo -99 (en vez de mostrar literalmente "NaT"/"None").
    """
    df = df.dropna(subset=["LATITUD", "LONGITUD"]).copy()
    geometry = [Point(lon, lat) for lat, lon in zip(df["LATITUD"], df["LONGITUD"])]
    df["Name"] = (
        df["NOMBRE_FAENA"].astype(str).str.strip() + " - " + df["NOMBRE_INSTALACION"].astype(str).str.strip()
    )
    atributos = df.drop(columns=["LATITUD", "LONGITUD"]).copy()
    for col in atributos.columns:
        if pd.api.types.is_datetime64_any_dtype(atributos[col]):
            atributos[col] = atributos[col].dt.strftime("%Y-%m-%d")
        atributos[col] = atributos[col].where(atributos[col].notna(), "")
    return gpd.GeoDataFrame(atributos, geometry=geometry, crs="EPSG:4326")


def main() -> None:
    if not ORIGEN_XLSX.exists():
        raise FileNotFoundError(
            f"No se encontro {ORIGEN_XLSX}. Se espera la planilla del catastro de relaves "
            "en 'Fallas Activas/Info/' (directorio hermano de este repo)."
        )
    print(f"Leyendo {ORIGEN_XLSX} (hoja '{HOJA}') ...")
    df = leer_catastro(ORIGEN_XLSX)
    print(f"  {len(df)} filas leidas")
    gdf = construir_geodataframe(df)
    print(f"  {len(gdf)} depositos con coordenadas validas")
    DESTINO_KML.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(DESTINO_KML, driver="KML")
    print(f"Escrito: {DESTINO_KML} ({DESTINO_KML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd fallas-activas-chile/tools && python -m pytest tests/test_convertir_catastro_relaves.py -v`
Expected: 3 passed

- [ ] **Step 5: Add `openpyxl` to `tools/requirements.txt`** (needed by `pandas.read_excel` for `.xlsx`)

Append a line: `openpyxl==3.1.5`

- [ ] **Step 6: Run it for real**

Run: `cd fallas-activas-chile && python tools/convertir_catastro_relaves.py`
Expected: prints `836 filas leidas`, `836 depositos con coordenadas validas` (all rows had valid coordinates, verified during planning), then `Escrito: .../data/relaves/relaves_sernageomin_2025.kml (...)`.

- [ ] **Step 7: Remove the superseded file and update `tools/extraer_kmls_infra.py`**

```bash
git rm fallas-activas-chile/data/relaves/relaves_sernageomin_2018.kml
```
(run from the `Documents/Claude` root, or `git rm data/relaves/relaves_sernageomin_2018.kml` from inside `fallas-activas-chile/`)

In `tools/extraer_kmls_infra.py`, change:
```python
EXCLUIR = {"red_vial"}
```
to:
```python
EXCLUIR = {"red_vial", "relaves_sernageomin_2018"}
```
(so a future re-run of this script against the sibling `infraestructura-critica-chile/` doesn't resurrect the superseded 2018 file).

In `tools/tests/test_extraer_kmls_infra.py`, extend `test_rutas_kmz_excluye_red_vial` (or add a new test) to also cover the `relaves_sernageomin_2018` exclusion, e.g.:
```python
def test_rutas_kmz_excluye_ambos_nombres(tmp_path):
    _tocar(tmp_path / "transporte" / "red_vial.kmz")
    _tocar(tmp_path / "transporte" / "red_ferrea.kmz")
    _tocar(tmp_path / "relaves" / "relaves_sernageomin_2018.kmz")
    _tocar(tmp_path / "relaves" / "otra_capa.kmz")

    encontrados = rutas_kmz(tmp_path)

    assert sorted(p.name for p in encontrados) == ["otra_capa.kmz", "red_ferrea.kmz"]
```
Run `cd tools && python -m pytest tests/test_extraer_kmls_infra.py -v` — expected: all tests (old + new) pass.

- [ ] **Step 8: Update `visor-web/index.html`'s `LAYER_DEFS`**

Replace:
```js
  { id: "relaves_sernageomin_2018", sector: "relaves", label: "Relaves (SERNAGEOMIN 2018)", file: "relaves/relaves_sernageomin_2018.kml", kind: "points" },
```
with:
```js
  { id: "relaves_sernageomin_2025", sector: "relaves", label: "Relaves (SERNAGEOMIN, oct. 2025)", file: "relaves/relaves_sernageomin_2025.kml", kind: "points" },
```
(same sector/kind, only `id`/`label`/`file` change — `INFRA_DEFS.length` stays 26, this is a swap not an addition.)

- [ ] **Step 9: Verify in the browser**

Use `preview_start` with `fallas-activas-preview`, navigate to `/visor-web/index.html`, expand "🏗️ Infraestructura Crítica" → "⛏️ Relaves", toggle the relaves checkbox on. Expected count: `836`. No console errors. Toggle the popup content check same way as Task 7 (calling `window.buildLayerGroup`/`window.fetchKml` directly is a valid, already-proven verification method for this file) — confirm a real feature shows attributes like `ESTADO_INSTALACION`, `NOMBRE_EMPRESA_O_PRODUCTOR_MINERO`, `REGION`.

- [ ] **Step 10: Commit**

```bash
git add tools/convertir_catastro_relaves.py tools/tests/test_convertir_catastro_relaves.py tools/extraer_kmls_infra.py tools/tests/test_extraer_kmls_infra.py tools/requirements.txt visor-web/index.html data/relaves/relaves_sernageomin_2025.kml
git commit -m "feat: replace outdated relaves layer with Oct-2025 SERNAGEOMIN catastro (742->836)"
```

---

## Task 9: Publish to GitHub Pages

**This task creates a public GitHub repository and pushes code — confirm with the user before running it if that confirmation hasn't already happened.**

**Files:** none new; this is deployment only.

- [ ] **Step 1: Create the GitHub repository**

Run: `gh repo create cvenegas-sernageomin/fallas-activas-chile --public --source=. --remote=origin` (run from inside `fallas-activas-chile/`).

- [ ] **Step 2: Push `main`**

```bash
git branch -M main
git push -u origin main
```

- [ ] **Step 3: Create the orphan `gh-pages` branch serving the viewer**

```bash
git checkout --orphan gh-pages
git rm -rf .
cp visor-web/index.html index.html
git add index.html
git commit -m "deploy: publish viewer to gh-pages"
git push origin gh-pages
git checkout main
```

- [ ] **Step 4: Verify the deploy succeeded**

Run: `gh api repos/cvenegas-sernageomin/fallas-activas-chile/pages` (after enabling Pages for the repo if not already enabled via `gh api -X POST repos/cvenegas-sernageomin/fallas-activas-chile/pages -f "source[branch]=gh-pages" -f "source[path]=/"`).
Then check the Actions run for "pages build and deployment" completes with `"conclusion": "success"` — same gotcha as documented for `alertas-redes` (deploy can silently fail; verify, don't assume).

- [ ] **Step 5: Open the published URL and repeat Task 7's Steps 2–4 against it**

`https://cvenegas-sernageomin.github.io/fallas-activas-chile/` — confirm the fault layer badge shows `958` and at least one infrastructure layer loads with the expected count, fetching from `raw.githubusercontent.com/cvenegas-sernageomin/fallas-activas-chile/main/data/...` (not `../data`, since `location.hostname` is no longer `localhost`).

---

## Plan self-review notes

- **Spec coverage:** every section of the design spec maps to a task — data pipeline (Tasks 2–5), viewer (Task 6), lazy-loading + generic attributes + line support + color scheme (all in Task 6's code), deployment (Task 9), validation approach (Task 7, matches spec's "no automated UI tests" decision). Task 8 (added after initial planning) swaps the outdated 2018 relaves source for a newer Oct-2025 SERNAGEOMIN catastro the user provided directly — same pattern as Tasks 3–5, not a design change.
- **Layer count consistency:** 26 infrastructure layers = 25 (Task 5) + 1 (`red_vial`, Task 4); + 1 fault layer (Task 3) = 27 total `LAYER_DEFS` entries, matching the corrected count in the spec.
- **Type/name consistency check:** `fetchKml(file, kind)`, `parsePlacemarks(text, kind)`, `buildLayerGroup(def, feats)`, `LAYER_DEFS`/`INFRA_DEFS`/`FALLAS_DEF`, `layerState[def.id]` shape (`{on, loading, error, total}`) are used identically across Task 6's code — verified by literally running this code in a browser during planning (see "Context already established").
