# Visor de Fallas Activas + Infraestructura Crítica de Chile

Fecha: 2026-07-08

## Contexto y propósito

SERNAGEOMIN necesita un visor web que combine dos capas de información nacional:

1. **Fallas activas y potencialmente activas** — catálogo CHAF v1 (Melnick, Maldonado &
   Contreras, 2020; *Database of active and potentially-active continental faults in
   Chile at 1:25,000 scale*; PANGAEA, doi:10.1594/PANGAEA.922241; CC-BY 4.0;
   [fallasactivas.cl](https://fallasactivas.cl/)). 958 trazas de falla agrupadas en 17
   sistemas, clasificadas por confiabilidad (78 Proved, 592 Probable, 288 Possible).
2. **Infraestructura crítica de Chile** — 26 capas ya descargadas y convertidas a KMZ en
   `infraestructura-critica-chile/`, repartidas en 5 sectores: agua, energía, relaves,
   salud, transporte.

El proyecto reutiliza el visor de `alertas-redes` (Leaflet + React UMD + Babel standalone,
un solo archivo HTML) como plantilla, despojado de toda la lógica de cron/backend — a
diferencia de alertas-redes, aquí **todos los datos son estáticos** (no cambian entre
visitas, no hay actualización periódica).

## Fuente de datos: CHAF v1 (fallas)

- Ya existe en el equipo un subset regional filtrado: `sernageomin_maule/repo/capas/fallas/CHAF_v1_maule.kmz`
  (42 fallas, solo Región del Maule) — **no se usa como fuente**, solo confirma el
  esquema de atributos.
- El dataset **nacional completo** se descarga directo (sin autenticación, acceso público
  CC-BY 4.0) desde:
  `https://download.pangaea.de/dataset/922241/files/CHAF_Pangaea_v1.kmz` (~311 KB).
- Esquema de atributos por falla (`ExtendedData/SchemaData/SimpleData`): `F_id`,
  `F_system`, `F_name`, `FT_name`, `type` (observed/inferred), `strike`, `dip`, `dipdir`,
  `rake`, `sense` (Normal/Reverse/...), `length_km`, `age`, **`activity`** (Proved /
  Probable / Possible — criterio de clasificación del propio paper), `recent_act`,
  `ass_seism`, `Mmax_r`, `Mmax_e`, `rec_int`, `notes`, `source`, `refs`, entre otros.
- **Gotcha de nomenclatura:** el `<name>` del Placemark en el KML original es el nivel de
  `activity` (ej. "Proved"), **no** el nombre de la falla — el nombre real está en
  `F_name`/`FT_name`. El visor debe armar el título del popup a partir de estos dos
  campos, no del `<name>` crudo.
- Geometría: `LineString` (trazas de falla).

## Fuente de datos: infraestructura crítica

- Ya generada en `infraestructura-critica-chile/{agua,energia,relaves,salud,transporte}/*.kmz`
  vía `descargar_capa.py` (ArcGIS REST → shapefile) + `shp_a_kmz.py` (shapefile → KMZ con
  geopandas/fiona).
- Estructura KML: `ExtendedData/SchemaData/SimpleData` (mismo patrón que CHAF, generado
  por geopandas) — un esquema de columnas distinto por capa (no hay campos comunes entre
  las 26 capas, salvo geometría).
- El `<name>` de cada Placemark ya viene resuelto por `shp_a_kmz.py` al campo más
  descriptivo disponible (`NOMBRE`, `ESTABLECIM`, etc.) — se usa tal cual para el título
  del popup, sin lógica adicional.
- El `<Style>` embebido en estos KML (color por defecto de geopandas, ej. `ff0000ff` en
  todas las líneas) **no tiene significado de categoría** — se ignora. El color en el
  visor se asigna por sector (ver sección Visor web).
- Geometrías mixtas: puntos (bocatomas, centrales, subestaciones, salud, puertos,
  aeropuertos) y líneas (gasoductos, oleoductos, líneas eléctricas, red férrea, red vial).
- **Excepción de tamaño — `red_vial.kmz` (72 MB comprimido):** la red vial nacional
  completa es demasiado pesada para cargar/parsear en el navegador tal cual. Se
  re-exporta desde el `.shp` original con `geopandas.simplify(tolerance≈0.001,
  preserve_topology=True)` (mismo criterio que se usó para simplificar 26.180 glaciares
  en `Catastro Glaciares/generar_kmz_glaciares.py`, de 3.3M a ~370k vértices). Objetivo:
  bajar a un orden de magnitud comparable a las otras capas de transporte (~1-5 MB). Si
  tras simplificar sigue siendo inmanejable, la capa queda con una advertencia visible en
  el panel ("capa pesada, puede tardar en cargar") en vez de excluirse — decisión: no
  excluir contenido, solo advertir.

## Estructura del proyecto

```
fallas-activas-chile/
  docs/superpowers/specs/2026-07-08-fallas-activas-chile-design.md
  data/
    red_fallas.kml                  # CHAF nacional, extraído del KMZ de PANGAEA
    agua/*.kml                      # 2 capas
    energia/*.kml                   # 18 capas
    relaves/*.kml                   # 1 capa
    salud/*.kml                     # 1 capa
    transporte/*.kml                # 4 capas (red_vial simplificada)
  tools/
    descargar_chaf.py               # descarga+extrae CHAF_Pangaea_v1.kmz -> red_fallas.kml
    simplificar_red_vial.py         # re-exporta red_vial.shp con simplify()
  visor-web/
    index.html                      # visor (adaptado de alertas-redes/visor-web/index.html)
```

## Visor web

**Base:** copia de `alertas-redes/visor-web/index.html`, con la siguiente poda/adaptación:

- **Se elimina:** todo lo relacionado a vismet, DMC directo, pronóstico Open-Meteo, sismos
  CSN/USGS, notificaciones Telegram, auto-refresh cada 15 min, botón "actualizar ahora".
  No hay backend ni cron — es un visor 100% estático.
- **Se conserva:** mapa Leaflet + ESRI World Imagery (satelital, sin token) + toggle a
  calles, patrón de parseo de KML en Web Worker con fallback a hilo principal,
  `preferCanvas: true`, sanitización de popups (`sanitizePopup`), panel lateral en
  acordeón (componente `Section`).

**Nuevo: soporte de líneas (`kind:"lines"`)**

El parser actual solo soporta `kind:"polygons"` (cuencas/glaciares) y puntos (default).
Se agrega un tercer `kind:"lines"`, análogo a `parsePolygons` pero leyendo
`<LineString><coordinates>` en vez de `<Polygon><outerBoundaryIs><LinearRing>`. Mismo
patrón dual (Worker + fallback main-thread `parseLinesMain`).

**Parseo genérico de atributos**

En vez de construir el HTML de cada popup a mano (inviable con 27 esquemas de columnas
distintos), se agrega una función genérica que:
1. Lee todos los pares `<SimpleData name="X">valor</SimpleData>` de la `ExtendedData` del
   Placemark, sin necesidad de conocer los nombres de campo de antemano.
2. Descarta campos vacíos o con valores centinela sin información (`-99`, cadena vacía).
3. Renderiza una tabla HTML `<table>` genérica con los pares campo/valor restantes.
4. El título del popup usa una función configurable por capa (`tituloPopup`): para fallas,
   `F_name + " — " + FT_name` (con fallback a `F_name` solo, o a `activity` si ambos
   faltan); para infraestructura, el `<name>` ya resuelto por `shp_a_kmz.py`.

**Color**

- Fallas: color por `activity` — Proved = rojo, Probable = naranja, Possible = amarillo
  (mismo criterio de confiabilidad que reporta el paper).
- Infraestructura: color fijo por sector, no por el `<Style>` del KML (sin significado
  real, ver arriba). Un color por sector: agua, energía, relaves, salud, transporte.

**Carga perezosa**

A diferencia de cuencas/glaciares en `alertas-redes` (que se cargan siempre al montar,
porque son solo 2 capas estáticas adicionales a las 3 dinámicas), aquí hay 27 datasets
estáticos — cargarlos todos de entrada sería lento e innecesario. Cada capa se
descarga y parsea la primera vez que el usuario la activa desde el panel, y el resultado
queda cacheado en memoria (no se vuelve a pedir si se desactiva/reactiva la misma capa).

**Panel lateral (acordeón)**

- Sección "🪨 Fallas Activas (CHAF v1)" — badge = 958, leyenda de color por actividad,
  checkbox único para mostrar/ocultar toda la capa.
- Sección "🏗️ Infraestructura Crítica" — con 5 subsecciones anidadas (una por sector:
  agua, energía, relaves, salud, transporte), cada una con checkboxes individuales por
  capa (26 en total). `red_vial` lleva una nota "(capa pesada)" junto a su checkbox.
- Todas las secciones y subsecciones arrancan **cerradas** al abrir el visor (mismo
  criterio ya usado en alertas-redes).

## Despliegue

- Repo público nuevo en GitHub: `fallas-activas-chile`.
- Rama `gh-pages` sirve `visor-web/index.html` (mismo patrón que alertas-redes/cuencas-chile:
  rama separada, huérfana, sincronizada manualmente tras cada cambio al visor).
- Los datos (`data/*.kml`) viven en `main` — son estáticos, no necesitan rama `live` ni
  workflow de actualización periódica. Si una fuente cambia en el futuro (nueva versión
  de CHAF, actualización de infraestructura), se re-corren los scripts de `tools/` y se
  commitea el `.kml` actualizado manualmente.

## Validación

- Sin tests automatizados de UI — mismo criterio que cuencas/glaciares en alertas-redes:
  el juicio del usuario (geólogo) sobre la visualización es la validación real.
- Verificación manual antes de dar por terminado: badges de conteo coinciden con las
  fuentes (958 fallas, conteo real de features por capa de infraestructura), click en al
  menos un elemento de cada tipo de geometría (punto, línea, y la propia falla) muestra su
  popup con datos coherentes, sin errores en consola del navegador.
- Si se agrega test automatizado para el nuevo parser de líneas, va en Python simple
  (o Pester si se prefiere consistencia con el resto del repo) contra un fixture KML
  pequeño con un `<LineString>` real extraído de los datos.

## Fuera de alcance (explícitamente)

- Análisis espacial de proximidad falla↔infraestructura (buffers, distancias) — el visor
  es solo de superposición visual, el cruce lo hace el geólogo a ojo.
- Actualización automática/cron de los datos — son estáticos, se regeneran manualmente.
- Filtrado por confiabilidad/actividad más allá del color (ej. slider u ocultar
  "Possible") — puede agregarse después si se pide explícitamente.
- Clustering de marcadores para capas de puntos densas (ej. bocatomas) — se deja para una
  iteración futura si el rendimiento real resulta insuficiente (el precedente de 26.180
  glaciares con `preferCanvas` sugiere que no hará falta, pero no se ha probado con puntos).
