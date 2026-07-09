# Guía: Descargar e integrar nuevas capas de infraestructura crítica

**Estado:** 4 scripts de conversión creados. Falta descargar los shapefiles.

---

## Paso 1: Descargar shapefiles

### Carabineros de Chile (929+ cuarteles, comisarías, tenencias)
1. Ir a: https://www.plataformadedatos.cl/datasets/es/60d196b8fe2d206e
2. Descargar shapefile (.zip)
3. Guardar en: `fallas-activas-chile/data/raw/carabineros.zip`

### Bomberos de Chile (parques)
1. Ir a: https://geoportal.cl/geoportal/catalog/31850/Bomberos
2. Buscar botón "Descargar" o "Download"
3. Descargar shapefile (.zip)
4. Guardar en: `fallas-activas-chile/data/raw/bomberos.zip`

### Puentes (MOP - Red Vial)
1. Ir a: https://www.plataformadedatos.cl/datasets/es/342f459b50db60f4
2. Descargar shapefile (.zip)
3. Guardar en: `fallas-activas-chile/data/raw/puentes.zip`

### Establecimientos Educacionales (MINEDUC)
1. Ir a: https://www.plataformadedatos.cl/datasets/es/925766D40B2366D
2. Descargar shapefile (.zip)
3. Guardar en: `fallas-activas-chile/data/raw/educacion.zip`

---

## Paso 2: Procesar shapefiles a KML

Una vez descargados los `.zip`, ejecutar desde `fallas-activas-chile/`:

```powershell
# Carabineros → data/seguridad/carabineros.kml
python tools/descargar_carabineros.py

# Bomberos → data/seguridad/bomberos.kml
python tools/descargar_bomberos.py

# Puentes → data/transporte/puentes.kml
python tools/descargar_puentes.py

# Educación → data/educacion/establecimientos_educacion.kml
python tools/descargar_educacion.py
```

Si todo funciona, verás:
```
  ✓ Conversión completada: NNN registros
```

---

## Paso 3: Integrar al visor

Una vez generados los KML, actualizar `visor-web/index.html`:

### 3.1: Agregar sectores nuevos
En el array `SECTORES` (línea ~121), agregar:
```javascript
{ id: "seguridad", label: "Seguridad", icon: "🚨", color: "#ef4444" },
{ id: "educacion", label: "Educación", icon: "📚", color: "#06b6d4" },
```

### 3.2: Agregar capas a LAYER_DEFS
En el array `LAYER_DEFS` (línea ~134), agregar estas entradas:

```javascript
// SEGURIDAD
{ id: "carabineros", sector: "seguridad", label: "Cuarteles de Carabineros", file: "seguridad/carabineros.kml", kind: "points" },
{ id: "bomberos", sector: "seguridad", label: "Parques de Bomberos", file: "seguridad/bomberos.kml", kind: "points" },

// TRANSPORTE (agregar a sección existente, o crear nueva entrada)
{ id: "puentes", sector: "transporte", label: "Puentes", file: "transporte/puentes.kml", kind: "points" },

// EDUCACIÓN (nueva sección)
{ id: "establecimientos_educacion", sector: "educacion", label: "Establecimientos Educacionales", file: "educacion/establecimientos_educacion.kml", kind: "points" },
```

### 3.3: Verificar que colorDeCapa() funciona
En la función `colorDeCapa()` (línea ~171), la lógica actual ya soporta cualquier sector:
```javascript
function colorDeCapa(def, attrs) {
  if (def.id === "fallas") return COLOR_ACTIVIDAD[attrs.activity] || COLOR_ACTIVIDAD_DEFAULT;
  return COLOR_SECTOR[def.sector] || "#3388ff";  // ← Funciona para nuevos sectores
}
```

---

## Paso 4: Probar localmente

```powershell
# Desde fallas-activas-chile/
python -m http.server 8000

# Abrir en navegador: http://localhost:8000/visor-web/
```

Verificar:
- ✓ Nuevos sectores aparecen en el panel izquierdo
- ✓ Checkboxes cargan capas cuando se activan
- ✓ Popups muestran información (nombres, direcciones, etc.)
- ✓ Puntos están georeferenciados correctamente

---

## Paso 5: Desplegar a GitHub

```bash
cd fallas-activas-chile/

# Commit en main
git add -A
git commit -m "feat: agregar capas seguridad/educacion/puentes

- Cuarteles Carabineros (929 instalaciones)
- Parques Bomberos (nacional)
- Puentes MOP (red vial)
- Establecimientos Educación MINEDUC"

# Sincronizar rama gh-pages
git checkout gh-pages
git show main:visor-web/index.html > index.html
git add index.html
git commit -m "sync: visor con nuevas capas"
git checkout main
```

---

## Notas técnicas

### Estructura de carpetas esperada
```
fallas-activas-chile/
├── data/
│   ├── raw/
│   │   ├── carabineros.zip
│   │   ├── bomberos.zip
│   │   ├── puentes.zip
│   │   └── educacion.zip
│   ├── seguridad/
│   │   ├── carabineros.kml
│   │   └── bomberos.kml
│   ├── transporte/
│   │   └── puentes.kml
│   └── educacion/
│       └── establecimientos_educacion.kml
├── tools/
│   ├── descargar_carabineros.py
│   ├── descargar_bomberos.py
│   ├── descargar_puentes.py
│   └── descargar_educacion.py
└── visor-web/
    └── index.html
```

### Validaciones en los scripts
- Detectan automáticamente columnas de "nombre" (case-insensitive)
- Convierten floats enteros a int (sin ".0" espurio)
- Sanitizan NaN → "" para que filtro visor las descarte
- Reproyectan a EPSG:4326 (WGS84)

### Si un shapefile tiene estructura diferente
Editar la función `procesar_[capa]()` en el script correspondiente:
- Cambiar búsqueda de `nombre_cols` si la columna tiene otro nombre
- Agregar lógica para `tipo_cols` si quieres combinar nombre + tipo en popup

---

## Capas NO disponibles (SKIP)
- ❌ Infraestructura TIC (torres) — operadas por privados, sin catálogo público
- ❌ Instalaciones nucleares — información limitada, no vectorial

---

## Referencias
- [Workflow completo](../workflows/descargar_infraestructura_critica.md)
- [Fuentes y portales](../.claude/projects/C--Users-carlos-venegas-Documents-Claude/memory/reference-infraestructura-critica-chile-fuentes.md)
- [Proyecto fallas-activas-chile](../.claude/projects/C--Users-carlos-venegas-Documents-Claude/memory/proyecto-fallas-activas-chile.md)
